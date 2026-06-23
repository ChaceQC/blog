import asyncio
import json
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import UTC, datetime, timedelta
from hmac import digest
from os import urandom
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from fastapi.testclient import TestClient

from app.api.admin.dependencies import get_auth_service
from app.api.dependencies import (
    get_encryption_session_manager,
    get_log_service,
    get_rate_limit_service,
)
from app.core.config import get_settings
from app.core.encryption import (
    EncryptedEnvelope,
    EncryptionProfile,
    decrypt_json_payload_with_key_material,
)
from app.core.encryption_sid import ESID_COOKIE_NAME, create_encryption_sid
from app.core.login_capsule import derive_login_capsule_keys
from app.main import app
from app.schemas.encryption import BrowserPublicKey
from app.services.auth import AuthenticatedUser, TokenPair
from app.services.encryption import (
    ActiveEncryptionSessionLimitExceeded,
    EncryptionSessionManager,
)
from app.services.encryption_salts import InMemorySaltLeaseStore, SaltLeaseService
from app.services.rate_limit import RateLimitService


class FakeEncryptionSessionRepository:
    def __init__(self) -> None:
        self.sessions: dict[str, SimpleNamespace] = {}
        self.commit_count = 0

    async def create_session(
        self,
        *,
        session_id: str,
        scope: str,
        client_ip: str | None,
        key_material: bytes,
        expires_at: datetime,
        login_challenge_id: str | None = None,
        login_challenge_salt: bytes | None = None,
        login_challenge_expires_at: datetime | None = None,
    ) -> SimpleNamespace:
        session = SimpleNamespace(
            session_id=session_id,
            scope=scope,
            client_ip=client_ip,
            key_material=key_material,
            login_challenge_id=login_challenge_id,
            login_challenge_salt=login_challenge_salt,
            login_challenge_expires_at=(
                _as_utc_naive(login_challenge_expires_at)
                if login_challenge_expires_at is not None
                else None
            ),
            login_challenge_used_at=None,
            expires_at=_as_utc_naive(expires_at),
        )
        self.sessions[session_id] = session
        return session

    async def count_active_sessions_by_client(
        self,
        *,
        scope: str,
        client_ip: str,
        now: datetime,
    ) -> int:
        current_time = _as_utc_naive(now)
        return sum(
            1
            for session in self.sessions.values()
            if session.scope == scope
            and session.client_ip == client_ip
            and _as_utc_naive(session.expires_at) > current_time
        )

    async def get_active_session(
        self,
        *,
        session_id: str,
        now: datetime,
    ) -> SimpleNamespace | None:
        current_time = _as_utc_naive(now)
        session = self.sessions.get(session_id)
        if session is None or _as_utc_naive(session.expires_at) <= current_time:
            return None
        return session

    async def consume_login_challenge(
        self,
        *,
        session_id: str,
        challenge_id: str,
        now: datetime,
    ) -> bool:
        current_time = _as_utc_naive(now)
        session = self.sessions.get(session_id)
        challenge_expires_at = (
            _as_utc_naive(session.login_challenge_expires_at)
            if session is not None and session.login_challenge_expires_at is not None
            else None
        )
        if (
            session is None
            or session.login_challenge_id != challenge_id
            or session.login_challenge_used_at is not None
            or challenge_expires_at is None
            or challenge_expires_at <= current_time
            or _as_utc_naive(session.expires_at) <= current_time
        ):
            return False
        session.login_challenge_used_at = current_time
        return True

    async def delete_expired_sessions(self, *, now: datetime) -> int:
        current_time = _as_utc_naive(now)
        expired_ids = [
            session_id
            for session_id, session in self.sessions.items()
            if _as_utc_naive(session.expires_at) <= current_time
        ]
        for session_id in expired_ids:
            self.sessions.pop(session_id)
        return len(expired_ids)

    async def commit(self) -> None:
        self.commit_count += 1


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
            access_token="test-access-token",
            refresh_token="test-refresh-token",
            expires_in=900,
            user=AuthenticatedUser(
                id=1,
                username=username,
                display_name="管理员",
                roles=["editor"],
                permissions=["post:read"],
            ),
        )


class FakeRefreshAuthService:
    def __init__(self) -> None:
        self.refresh_token: str | None = None

    async def refresh(self, *, refresh_token: str) -> TokenPair:
        self.refresh_token = refresh_token
        return TokenPair(
            access_token="new-test-access-token",
            refresh_token="new-test-refresh-token",
            expires_in=900,
            user=AuthenticatedUser(
                id=1,
                username="admin",
                display_name="管理员",
                roles=["editor"],
                permissions=["post:read"],
            ),
        )


class RaisingAuthService:
    async def login(
        self,
        *,
        username: str,
        password: str,
        ip: str | None,
        user_agent: str | None,
    ) -> TokenPair:
        raise AssertionError("login service should not be called")

    async def authenticate_access_token(
        self,
        *,
        access_token: str,
    ) -> AuthenticatedUser:
        raise AssertionError("auth service should not be called")


class FakeLogService:
    async def record_security_event(self, **_: object) -> None:
        raise AssertionError("security event should not be recorded")


class CollectingLogService:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    async def record_security_event(self, **payload: object) -> None:
        self.events.append(dict(payload))


class ActiveLimitExceededManager:
    async def create_session(self, **_: object) -> object:
        raise ActiveEncryptionSessionLimitExceeded("too many active sessions")


def test_login_response_can_use_sensitive_encryption_session() -> None:
    client_private_key = ec.generate_private_key(ec.SECP256R1())
    client = TestClient(app)
    encryption_repository = FakeEncryptionSessionRepository()
    salt_leases = SaltLeaseService(store=InMemorySaltLeaseStore())
    encryption_manager = EncryptionSessionManager(
        repository=encryption_repository,
        settings=get_settings(),
        salt_leases=salt_leases,
    )
    app.dependency_overrides[get_encryption_session_manager] = lambda: (
        encryption_manager
    )
    app.dependency_overrides[get_log_service] = lambda: FakeLogService()
    app.dependency_overrides[get_rate_limit_service] = lambda: RateLimitService()

    try:
        session_response = client.post(
            "/api/admin/encryption/sessions",
            json={
                "client_public_key": _export_public_key(
                    client_private_key.public_key(),
                ),
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert session_response.status_code == 200
    assert encryption_repository.commit_count == 1
    session_payload = session_response.json()
    shared_key = client_private_key.exchange(
        ec.ECDH(),
        _load_public_key(session_payload["server_public_key"]),
    )
    esid_salt = _set_esid_cookie(
        client,
        session_id=session_payload["session_id"],
        scope="admin",
        key_material=shared_key,
        expires_at=_parse_api_datetime(session_payload["expires_at"]),
        salt_leases=salt_leases,
    )
    response_salt = _issue_salt(
        salt_leases,
        session_id=session_payload["session_id"],
        scope="admin",
        purpose="response",
        profile=EncryptionProfile.SENSITIVE,
    )

    app.dependency_overrides[get_auth_service] = lambda: FakeAuthService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: (
        encryption_manager
    )
    app.dependency_overrides[get_log_service] = lambda: FakeLogService()
    app.dependency_overrides[get_rate_limit_service] = lambda: RateLimitService()
    try:
        login_response = client.post(
            "/api/admin/auth/login",
            headers={
                "X-Encryption-Session": session_payload["session_id"],
                "X-Encryption-Esid-Salt": esid_salt.lease_id,
                "X-Encryption-Response-Salt": response_salt.lease_id,
            },
            json=_make_login_capsule(
                session_payload=session_payload,
                shared_key=shared_key,
                salt_leases=salt_leases,
            ),
        )
    finally:
        app.dependency_overrides.clear()

    assert login_response.status_code == 200
    envelope_payload = login_response.json()
    assert envelope_payload["profile"] == EncryptionProfile.SENSITIVE
    decrypted = decrypt_json_payload_with_key_material(
        EncryptedEnvelope(
            profile=EncryptionProfile(envelope_payload["profile"]),
            nonce=envelope_payload["nonce"],
            ciphertext=envelope_payload["ciphertext"],
        ),
        key_material=shared_key,
        expected_profile=EncryptionProfile.SENSITIVE,
        salt=response_salt.salt,
    )

    assert decrypted["user"]["username"] == "admin"
    assert decrypted["user"]["display_name"] == "管理员"
    assert decrypted["csrf_token"]


def test_login_rejects_missing_encryption_session_header() -> None:
    client = TestClient(app)
    app.dependency_overrides[get_auth_service] = lambda: RaisingAuthService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: (
        EncryptionSessionManager(
            repository=FakeEncryptionSessionRepository(),
            settings=get_settings(),
        )
    )
    app.dependency_overrides[get_log_service] = lambda: FakeLogService()
    app.dependency_overrides[get_rate_limit_service] = lambda: RateLimitService()
    try:
        response = client.post(
            "/api/admin/auth/login",
            json=_dummy_login_capsule(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "missing encryption session"


def test_login_rejects_missing_encryption_session_sid() -> None:
    client_private_key = ec.generate_private_key(ec.SECP256R1())
    client = TestClient(app)
    encryption_repository = FakeEncryptionSessionRepository()
    salt_leases = SaltLeaseService(store=InMemorySaltLeaseStore())
    encryption_manager = EncryptionSessionManager(
        repository=encryption_repository,
        settings=get_settings(),
        salt_leases=salt_leases,
    )
    app.dependency_overrides[get_encryption_session_manager] = lambda: (
        encryption_manager
    )
    app.dependency_overrides[get_log_service] = lambda: FakeLogService()
    app.dependency_overrides[get_rate_limit_service] = lambda: RateLimitService()

    try:
        session_response = client.post(
            "/api/admin/encryption/sessions",
            json={
                "client_public_key": _export_public_key(
                    client_private_key.public_key(),
                ),
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert session_response.status_code == 200
    session_payload = session_response.json()
    shared_key = client_private_key.exchange(
        ec.ECDH(),
        _load_public_key(session_payload["server_public_key"]),
    )

    app.dependency_overrides[get_auth_service] = lambda: RaisingAuthService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: (
        encryption_manager
    )
    app.dependency_overrides[get_log_service] = lambda: FakeLogService()
    app.dependency_overrides[get_rate_limit_service] = lambda: RateLimitService()
    try:
        response = client.post(
            "/api/admin/auth/login",
            headers={"X-Encryption-Session": session_payload["session_id"]},
            json=_make_login_capsule(
                session_payload=session_payload,
                shared_key=shared_key,
                salt_leases=salt_leases,
            ),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid login capsule"


def test_login_rejects_tampered_encryption_session_sid() -> None:
    client_private_key = ec.generate_private_key(ec.SECP256R1())
    client = TestClient(app)
    encryption_repository = FakeEncryptionSessionRepository()
    salt_leases = SaltLeaseService(store=InMemorySaltLeaseStore())
    encryption_manager = EncryptionSessionManager(
        repository=encryption_repository,
        settings=get_settings(),
        salt_leases=salt_leases,
    )
    app.dependency_overrides[get_encryption_session_manager] = lambda: (
        encryption_manager
    )
    app.dependency_overrides[get_log_service] = lambda: FakeLogService()
    app.dependency_overrides[get_rate_limit_service] = lambda: RateLimitService()

    try:
        session_response = client.post(
            "/api/admin/encryption/sessions",
            json={
                "client_public_key": _export_public_key(
                    client_private_key.public_key(),
                ),
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert session_response.status_code == 200
    session_payload = session_response.json()
    shared_key = client_private_key.exchange(
        ec.ECDH(),
        _load_public_key(session_payload["server_public_key"]),
    )
    esid_salt = _set_esid_cookie(
        client,
        session_id=session_payload["session_id"],
        scope="admin",
        key_material=shared_key,
        expires_at=_parse_api_datetime(session_payload["expires_at"]),
        salt_leases=salt_leases,
        suffix="x",
    )

    app.dependency_overrides[get_auth_service] = lambda: RaisingAuthService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: (
        encryption_manager
    )
    app.dependency_overrides[get_log_service] = lambda: FakeLogService()
    app.dependency_overrides[get_rate_limit_service] = lambda: RateLimitService()
    try:
        response = client.post(
            "/api/admin/auth/login",
            headers={
                "X-Encryption-Session": session_payload["session_id"],
                "X-Encryption-Esid-Salt": esid_salt.lease_id,
            },
            json=_make_login_capsule(
                session_payload=session_payload,
                shared_key=shared_key,
                salt_leases=salt_leases,
            ),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid login capsule"


def test_login_rejects_oversized_encryption_session_header() -> None:
    client = TestClient(app)
    app.dependency_overrides[get_auth_service] = lambda: RaisingAuthService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: (
        EncryptionSessionManager(
            repository=FakeEncryptionSessionRepository(),
            settings=get_settings(),
        )
    )
    app.dependency_overrides[get_log_service] = lambda: FakeLogService()
    app.dependency_overrides[get_rate_limit_service] = lambda: RateLimitService()
    try:
        response = client.post(
            "/api/admin/auth/login",
            headers={"X-Encryption-Session": "s" * 129},
            json=_dummy_login_capsule(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid encryption session"


def test_login_rejects_public_encryption_session_before_authentication() -> None:
    client_private_key = ec.generate_private_key(ec.SECP256R1())
    client = TestClient(app)
    encryption_repository = FakeEncryptionSessionRepository()
    salt_leases = SaltLeaseService(store=InMemorySaltLeaseStore())
    encryption_manager = EncryptionSessionManager(
        repository=encryption_repository,
        settings=get_settings(),
        salt_leases=salt_leases,
    )
    app.dependency_overrides[get_encryption_session_manager] = lambda: (
        encryption_manager
    )
    try:
        session_response = client.post(
            "/api/public/encryption/sessions",
            json={
                "client_public_key": _export_public_key(
                    client_private_key.public_key(),
                ),
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert session_response.status_code == 200
    session_payload = session_response.json()
    assert session_payload["scope"] == "public"

    app.dependency_overrides[get_auth_service] = lambda: RaisingAuthService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: (
        encryption_manager
    )
    app.dependency_overrides[get_log_service] = lambda: FakeLogService()
    app.dependency_overrides[get_rate_limit_service] = lambda: RateLimitService()
    try:
        response = client.post(
            "/api/admin/auth/login",
            headers={"X-Encryption-Session": session_payload["session_id"]},
            json=_dummy_login_capsule(session_payload["session_id"]),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid login capsule"


def test_admin_login_ip_rate_limit_blocks_rotating_usernames() -> None:
    settings = get_settings().model_copy(
        update={
            "admin_login_rate_limit_max_attempts": 1,
            "admin_login_rate_limit_window_seconds": 60,
        },
    )
    client = TestClient(app)
    encryption_repository = FakeEncryptionSessionRepository()
    salt_leases = SaltLeaseService(store=InMemorySaltLeaseStore())
    encryption_manager = EncryptionSessionManager(
        repository=encryption_repository,
        settings=settings,
        salt_leases=salt_leases,
    )
    logs = CollectingLogService()
    rate_limiter = RateLimitService()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_auth_service] = lambda: FakeAuthService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: (
        encryption_manager
    )
    app.dependency_overrides[get_log_service] = lambda: logs
    app.dependency_overrides[get_rate_limit_service] = lambda: rate_limiter

    try:
        responses = []
        for index in range(4):
            client_private_key = ec.generate_private_key(ec.SECP256R1())
            session_response = client.post(
                "/api/admin/encryption/sessions",
                json={
                    "client_public_key": _export_public_key(
                        client_private_key.public_key(),
                    ),
                },
            )
            session_payload = session_response.json()
            shared_key = client_private_key.exchange(
                ec.ECDH(),
                _load_public_key(session_payload["server_public_key"]),
            )
            esid_salt = _set_esid_cookie(
                client,
                session_id=session_payload["session_id"],
                scope="admin",
                key_material=shared_key,
                expires_at=_parse_api_datetime(session_payload["expires_at"]),
                salt_leases=salt_leases,
            )
            response_salt = _issue_salt(
                salt_leases,
                session_id=session_payload["session_id"],
                scope="admin",
                purpose="response",
                profile=EncryptionProfile.SENSITIVE,
            )
            responses.append(
                client.post(
                    "/api/admin/auth/login",
                    headers={
                        "X-Encryption-Session": session_payload["session_id"],
                        "X-Encryption-Esid-Salt": esid_salt.lease_id,
                        "X-Encryption-Response-Salt": response_salt.lease_id,
                    },
                    json=_make_login_capsule(
                        session_payload=session_payload,
                        shared_key=shared_key,
                        salt_leases=salt_leases,
                        username=f"missing-{index}",
                        password="wrong-password",
                    ),
                ),
            )
    finally:
        app.dependency_overrides.clear()

    assert session_response.status_code == 200
    assert [response.status_code for response in responses] == [200, 200, 200, 429]
    assert logs.events[-1]["event_type"] == "rate_limit.admin_login"
    assert logs.events[-1]["detail_json"] == {"credential": "ip"}


def test_me_rejects_public_encryption_session_before_authentication() -> None:
    client_private_key = ec.generate_private_key(ec.SECP256R1())
    client = TestClient(app)
    encryption_repository = FakeEncryptionSessionRepository()
    salt_leases = SaltLeaseService(store=InMemorySaltLeaseStore())
    encryption_manager = EncryptionSessionManager(
        repository=encryption_repository,
        settings=get_settings(),
        salt_leases=salt_leases,
    )
    app.dependency_overrides[get_encryption_session_manager] = lambda: (
        encryption_manager
    )
    try:
        session_response = client.post(
            "/api/public/encryption/sessions",
            json={
                "client_public_key": _export_public_key(
                    client_private_key.public_key(),
                ),
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert session_response.status_code == 200
    session_payload = session_response.json()

    app.dependency_overrides[get_auth_service] = lambda: RaisingAuthService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: (
        encryption_manager
    )
    try:
        response = client.get(
            "/api/admin/auth/me",
            headers={
                "X-Encryption-Session": session_payload["session_id"],
                "Authorization": "Bearer token-that-must-not-be-checked",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid encryption session"


def test_refresh_uses_cookie_without_csrf_header() -> None:
    refresh_token = "r" * 32
    client_private_key = ec.generate_private_key(ec.SECP256R1())
    client = TestClient(app)
    encryption_repository = FakeEncryptionSessionRepository()
    salt_leases = SaltLeaseService(store=InMemorySaltLeaseStore())
    encryption_manager = EncryptionSessionManager(
        repository=encryption_repository,
        settings=get_settings(),
        salt_leases=salt_leases,
    )
    app.dependency_overrides[get_encryption_session_manager] = lambda: (
        encryption_manager
    )
    try:
        session_response = client.post(
            "/api/admin/encryption/sessions",
            json={
                "client_public_key": _export_public_key(
                    client_private_key.public_key(),
                ),
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert session_response.status_code == 200
    session_payload = session_response.json()
    shared_key = client_private_key.exchange(
        ec.ECDH(),
        _load_public_key(session_payload["server_public_key"]),
    )
    esid_salt = _set_esid_cookie(
        client,
        session_id=session_payload["session_id"],
        scope="admin",
        key_material=shared_key,
        expires_at=_parse_api_datetime(session_payload["expires_at"]),
        salt_leases=salt_leases,
    )
    response_salt = _issue_salt(
        salt_leases,
        session_id=session_payload["session_id"],
        scope="admin",
        purpose="response",
        profile=EncryptionProfile.SENSITIVE,
    )
    auth_service = FakeRefreshAuthService()
    client.cookies.set("blog_admin_refresh", refresh_token, path="/api/admin")

    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[get_encryption_session_manager] = lambda: (
        encryption_manager
    )
    try:
        response = client.post(
            "/api/admin/auth/refresh",
            headers={
                "X-Encryption-Session": session_payload["session_id"],
                "X-Encryption-Esid-Salt": esid_salt.lease_id,
                "X-Encryption-Response-Salt": response_salt.lease_id,
            },
            json={},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert auth_service.refresh_token == refresh_token
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert any(
        "blog_admin_csrf=" in header and "Path=/api/admin" in header
        for header in set_cookie_headers
    )
    envelope_payload = response.json()
    decrypted = decrypt_json_payload_with_key_material(
        EncryptedEnvelope(
            profile=EncryptionProfile(envelope_payload["profile"]),
            nonce=envelope_payload["nonce"],
            ciphertext=envelope_payload["ciphertext"],
        ),
        key_material=shared_key,
        expected_profile=EncryptionProfile.SENSITIVE,
        salt=response_salt.salt,
    )

    assert decrypted["user"]["username"] == "admin"
    assert decrypted["csrf_token"]


def test_refresh_rejects_body_refresh_token_without_cookie() -> None:
    refresh_token = "r" * 32
    client_private_key = ec.generate_private_key(ec.SECP256R1())
    client = TestClient(app)
    encryption_repository = FakeEncryptionSessionRepository()
    salt_leases = SaltLeaseService(store=InMemorySaltLeaseStore())
    encryption_manager = EncryptionSessionManager(
        repository=encryption_repository,
        settings=get_settings(),
        salt_leases=salt_leases,
    )
    app.dependency_overrides[get_encryption_session_manager] = lambda: (
        encryption_manager
    )
    try:
        session_response = client.post(
            "/api/admin/encryption/sessions",
            json={
                "client_public_key": _export_public_key(
                    client_private_key.public_key(),
                ),
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert session_response.status_code == 200
    session_payload = session_response.json()
    shared_key = client_private_key.exchange(
        ec.ECDH(),
        _load_public_key(session_payload["server_public_key"]),
    )
    esid_salt = _set_esid_cookie(
        client,
        session_id=session_payload["session_id"],
        scope="admin",
        key_material=shared_key,
        expires_at=_parse_api_datetime(session_payload["expires_at"]),
        salt_leases=salt_leases,
    )
    auth_service = FakeRefreshAuthService()

    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[get_encryption_session_manager] = lambda: (
        encryption_manager
    )
    try:
        response = client.post(
            "/api/admin/auth/refresh",
            headers={
                "X-Encryption-Session": session_payload["session_id"],
                "X-Encryption-Esid-Salt": esid_salt.lease_id,
            },
            json={"refresh_token": refresh_token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert auth_service.refresh_token is None


def test_cleanup_expired_encryption_sessions_deletes_only_expired() -> None:
    now = datetime(2026, 6, 17, 12, 0, tzinfo=UTC)
    repository = FakeEncryptionSessionRepository()
    repository.sessions["expired"] = SimpleNamespace(
        session_id="expired",
        scope="admin",
        key_material=b"expired-key",
        expires_at=now - timedelta(seconds=1),
    )
    repository.sessions["active"] = SimpleNamespace(
        session_id="active",
        scope="admin",
        key_material=b"active-key",
        expires_at=now + timedelta(seconds=1),
    )
    manager = EncryptionSessionManager(
        repository=repository,
        settings=get_settings(),
    )

    deleted_count = asyncio.run(manager.cleanup_expired_sessions(now=now))

    assert deleted_count == 1
    assert "expired" not in repository.sessions
    assert "active" in repository.sessions
    assert repository.commit_count == 1


def test_cleanup_expired_encryption_sessions_skips_empty_commit() -> None:
    now = datetime(2026, 6, 17, 12, 0, tzinfo=UTC)
    repository = FakeEncryptionSessionRepository()
    repository.sessions["active"] = SimpleNamespace(
        session_id="active",
        scope="admin",
        key_material=b"active-key",
        expires_at=now + timedelta(seconds=1),
    )
    manager = EncryptionSessionManager(
        repository=repository,
        settings=get_settings(),
    )

    deleted_count = asyncio.run(manager.cleanup_expired_sessions(now=now))

    assert deleted_count == 0
    assert "active" in repository.sessions
    assert repository.commit_count == 0


def test_create_session_rejects_active_session_overflow() -> None:
    client_private_key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(UTC)
    repository = FakeEncryptionSessionRepository()
    repository.sessions["active"] = SimpleNamespace(
        session_id="active",
        scope="public",
        client_ip="203.0.113.9",
        key_material=b"active-key",
        expires_at=now + timedelta(minutes=5),
    )
    manager = EncryptionSessionManager(
        repository=repository,
        settings=get_settings(),
    )

    with pytest.raises(Exception) as exc_info:
        asyncio.run(
            manager.create_session(
                client_public_key=BrowserPublicKey.model_validate(
                    _export_public_key(client_private_key.public_key()),
                ),
                scope="public",
                client_ip="203.0.113.9",
                active_session_limit=1,
            ),
        )

    assert exc_info.value.__class__.__name__ == "ActiveEncryptionSessionLimitExceeded"
    assert len(repository.sessions) == 1


def test_admin_encryption_session_rejects_active_session_overflow() -> None:
    client = TestClient(app)
    logs = CollectingLogService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: (
        ActiveLimitExceededManager()
    )
    app.dependency_overrides[get_log_service] = lambda: logs
    app.dependency_overrides[get_rate_limit_service] = lambda: RateLimitService()

    try:
        response = client.post(
            "/api/admin/encryption/sessions",
            json={
                "client_public_key": {
                    "kty": "EC",
                    "crv": "P-256",
                    "x": "test-x",
                    "y": "test-y",
                },
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 429
    assert response.json()["detail"] == "too many active encryption sessions"
    assert logs.events[0]["event_type"] == "rate_limit.encryption_session_active"
    assert logs.events[0]["detail_json"] == {
        "scope": "admin",
        "profile": "sensitive-v1",
    }


def _make_login_capsule(
    *,
    session_payload: dict[str, object],
    shared_key: bytes,
    salt_leases: SaltLeaseService,
    username: str = "admin",
    password: str = "correct-password",
    path: str = "/api/admin/auth/login",
) -> dict[str, object]:
    challenge = session_payload["login_challenge"]
    assert isinstance(challenge, dict)
    session_id = str(session_payload["session_id"])
    challenge_id = str(challenge["challenge_id"])
    login_salt = _issue_salt(
        salt_leases,
        session_id=session_id,
        scope="admin",
        purpose="login_capsule",
        profile=EncryptionProfile.SENSITIVE,
    )
    keys = derive_login_capsule_keys(
        key_material=shared_key,
        challenge_salt=_base64url_decode(str(challenge["challenge_salt"])),
        transport_salt=login_salt.salt,
        session_id=session_id,
        challenge_id=challenge_id,
    )
    payload = json.dumps(
        {"username": username, "password": password},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    bucket_size = next(
        size for size in (256, 512, 1024, 2048) if size >= len(payload) + 2
    )
    plaintext = len(payload).to_bytes(2, "big") + payload + urandom(
        bucket_size - len(payload) - 2,
    )
    nonce = urandom(16)
    encryptor = Cipher(
        algorithms.AES(keys.encryption_key),
        modes.CTR(nonce),
    ).encryptor()
    ciphertext = encryptor.update(plaintext) + encryptor.finalize()
    capsule = {
        "scheme": "login-capsule-v2",
        "session_id": session_id,
        "challenge_id": challenge_id,
        "salt_id": login_salt.lease_id,
        "nonce": _base64url_encode(nonce),
        "issued_at": int(datetime.now(UTC).timestamp()),
        "ciphertext": _base64url_encode(ciphertext),
    }
    capsule["tag"] = _base64url_encode(
        digest(
            keys.mac_key,
            _login_capsule_signing_input(capsule, path=path),
            "sha256",
        ),
    )
    return capsule


def _dummy_login_capsule(session_id: str = "dummy-session") -> dict[str, object]:
    return {
        "scheme": "login-capsule-v2",
        "session_id": session_id,
        "challenge_id": "dummy-challenge",
        "salt_id": "dummy-salt",
        "nonce": "AA",
        "issued_at": int(datetime.now(UTC).timestamp()),
        "ciphertext": "AA",
        "tag": "AA",
    }


def _login_capsule_signing_input(
    capsule: dict[str, object],
    *,
    path: str,
) -> bytes:
    return "\n".join(
        (
            str(capsule["scheme"]),
            str(capsule["session_id"]),
            str(capsule["challenge_id"]),
            str(capsule["salt_id"]),
            "POST",
            path,
            str(capsule["issued_at"]),
            str(capsule["nonce"]),
            str(capsule["ciphertext"]),
        ),
    ).encode("utf-8")


def _export_public_key(public_key: ec.EllipticCurvePublicKey) -> dict[str, str]:
    numbers = public_key.public_numbers()
    return {
        "kty": "EC",
        "crv": "P-256",
        "x": _base64url_encode(numbers.x.to_bytes(32, "big")),
        "y": _base64url_encode(numbers.y.to_bytes(32, "big")),
    }


def _load_public_key(payload: dict[str, str]) -> ec.EllipticCurvePublicKey:
    return ec.EllipticCurvePublicNumbers(
        x=int.from_bytes(_base64url_decode(payload["x"]), "big"),
        y=int.from_bytes(_base64url_decode(payload["y"]), "big"),
        curve=ec.SECP256R1(),
    ).public_key()


def _base64url_encode(value: bytes) -> str:
    return urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return urlsafe_b64decode(f"{value}{padding}")


def _set_esid_cookie(
    client: TestClient,
    *,
    session_id: str,
    scope: str,
    key_material: bytes,
    expires_at: datetime,
    salt_leases: SaltLeaseService,
    suffix: str = "",
) -> object:
    salt_lease = _issue_salt(
        salt_leases,
        session_id=session_id,
        scope=scope,
        purpose="esid",
        profile=None,
    )
    esid = create_encryption_sid(
        session_id=session_id,
        scope=scope,
        key_material=key_material,
        expires_at=expires_at,
        salt=salt_lease.salt,
    )
    client.cookies.set(ESID_COOKIE_NAME, f"{esid}{suffix}", path="/api")
    return salt_lease


def _parse_api_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _as_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _issue_salt(
    salt_leases: SaltLeaseService,
    *,
    session_id: str,
    scope: str,
    purpose: str,
    profile: EncryptionProfile | None,
):
    return salt_leases.issue(
        session_id=session_id,
        scope=scope,  # type: ignore[arg-type]
        purpose=purpose,  # type: ignore[arg-type]
        profile=profile,
    )
