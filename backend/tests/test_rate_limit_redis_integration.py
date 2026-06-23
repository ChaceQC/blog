from datetime import UTC, datetime, timedelta
from os import environ
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from redis import Redis

from app.api.admin.dependencies import get_auth_service
from app.api.dependencies import (
    get_encryption_session_manager,
    get_log_service,
    get_rate_limit_service,
)
from app.core.config import get_settings
from app.core.encryption import EncryptionProfile
from app.main import app
from app.schemas.auth import LoginRequest
from app.schemas.encryption import (
    BrowserPublicKey,
    CreateEncryptionSessionResponse,
    EncryptedApiResponse,
)
from app.services.auth import AuthenticatedUser, TokenPair
from app.services.rate_limit import create_rate_limit_service


@pytest.fixture
def redis_url() -> str:
    url = environ.get("BLOG_TEST_REDIS_URL")
    if not url:
        pytest.skip("BLOG_TEST_REDIS_URL is not set")
    Redis.from_url(url, decode_responses=True, protocol=2).flushdb()
    return url


def test_admin_encryption_session_rate_limit_uses_real_redis(
    redis_url: str,
) -> None:
    settings = _redis_settings(redis_url)
    logs = FakeLogService()
    rate_limiter = create_rate_limit_service(settings)
    client = TestClient(app)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_encryption_session_manager] = lambda: (
        FakeEncryptionSessionManager()
    )
    app.dependency_overrides[get_log_service] = lambda: logs
    app.dependency_overrides[get_rate_limit_service] = lambda: rate_limiter

    try:
        first = client.post(
            "/api/admin/encryption/sessions",
            json={"client_public_key": _public_key_payload()},
        )
        second = client.post(
            "/api/admin/encryption/sessions",
            json={"client_public_key": _public_key_payload()},
        )
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 200
    assert second.status_code == 429
    assert int(second.headers["Retry-After"]) >= 1
    assert logs.events[-1]["event_type"] == "rate_limit.encryption_session"


def test_admin_login_rate_limit_uses_real_redis(redis_url: str) -> None:
    settings = _redis_settings(redis_url)
    logs = FakeLogService()
    rate_limiter = create_rate_limit_service(settings)
    encryption_manager = FakeEncryptionSessionManager()
    client = TestClient(app)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_auth_service] = lambda: FakeAuthService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: (
        encryption_manager
    )
    app.dependency_overrides[get_log_service] = lambda: logs
    app.dependency_overrides[get_rate_limit_service] = lambda: rate_limiter

    try:
        first = client.post(
            "/api/admin/auth/login",
            headers={"X-Encryption-Session": "redis-test-session"},
            json=_login_capsule_payload(),
        )
        second = client.post(
            "/api/admin/auth/login",
            headers={"X-Encryption-Session": "redis-test-session"},
            json=_login_capsule_payload(),
        )
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 200
    assert second.status_code == 429
    assert int(second.headers["Retry-After"]) >= 1
    assert logs.events[-1]["event_type"] == "rate_limit.admin_login"
    assert logs.events[-1]["detail_json"] == {"credential": "username"}


def _redis_settings(redis_url: str):
    return get_settings().model_copy(
        update={
            "rate_limit_backend": "redis",
            "redis_url": redis_url,
            "redis_key_prefix": f"blog:test-rate-limit:{uuid4().hex}",
            "admin_login_rate_limit_max_attempts": 1,
            "admin_login_rate_limit_window_seconds": 60,
            "encryption_session_rate_limit_max_attempts": 1,
            "encryption_session_rate_limit_window_seconds": 60,
        },
    )


def _public_key_payload() -> dict[str, str]:
    return {"kty": "EC", "crv": "P-256", "x": "test-x", "y": "test-y"}


def _login_capsule_payload() -> dict[str, object]:
    return {
        "scheme": "login-capsule-v2",
        "session_id": "redis-test-session",
        "challenge_id": "redis-test-challenge",
        "nonce": "redis-test-nonce",
        "issued_at": int(datetime.now(UTC).timestamp()),
        "ciphertext": "redis-test-ciphertext",
        "tag": "redis-test-tag",
    }


class FakeEncryptionSessionManager:
    async def create_session(
        self,
        *,
        client_public_key: BrowserPublicKey,
        scope: str = "admin",
        client_ip: str | None = None,
        active_session_limit: int | None = None,
    ) -> CreateEncryptionSessionResponse:
        assert client_ip == "testclient"
        assert active_session_limit == 10
        return CreateEncryptionSessionResponse(
            session_id="redis-test-session",
            scope="admin",
            server_public_key=client_public_key,
            profiles=[EncryptionProfile.SENSITIVE, EncryptionProfile.CONTENT],
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )

    async def encrypt_response(
        self,
        *,
        session_id: str,
        scope: str,
        profile: EncryptionProfile,
        payload: dict[str, object],
        esid: str | None = None,
    ) -> EncryptedApiResponse:
        return EncryptedApiResponse(
            session_id=session_id,
            profile=profile,
            nonce="redis-test-nonce",
            ciphertext="redis-test-ciphertext",
        )

    async def validate_session(
        self,
        *,
        session_id: str,
        scope: str,
        profile: EncryptionProfile,
        esid: str | None = None,
    ) -> None:
        assert session_id == "redis-test-session"
        assert scope == "admin"
        assert profile == EncryptionProfile.SENSITIVE

    async def decrypt_login_capsule(
        self,
        *,
        session_id: str,
        esid: str | None,
        payload: object,
        method: str,
        path: str,
    ) -> LoginRequest:
        assert session_id == "redis-test-session"
        assert esid is None
        assert method == "POST"
        assert path == "/api/admin/auth/login"
        assert payload.scheme == "login-capsule-v2"
        return LoginRequest(username="admin", password="correct-password")


class FakeAuthService:
    async def login(
        self,
        *,
        username: str,
        password: str,
        ip: str | None,
        user_agent: str | None,
    ) -> TokenPair:
        return TokenPair(
            access_token="redis-test-access-token",
            refresh_token="redis-test-refresh-token",
            expires_in=900,
            user=AuthenticatedUser(
                id=1,
                username=username,
                display_name="管理员",
                roles=["editor"],
                permissions=["post:read"],
            ),
        )


class FakeLogService:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    async def record_security_event(self, **payload: object) -> None:
        self.events.append(payload)
