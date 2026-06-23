from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.admin.dependencies import get_current_admin_user
from app.api.dependencies import (
    get_encryption_session_manager,
    get_log_service,
    get_setting_service,
)
from app.core.encryption import EncryptionProfile
from app.main import app
from app.schemas.encryption import EncryptedApiRequest, EncryptedApiResponse
from app.services.auth import AuthenticatedUser
from app.services.settings import DEFAULT_SITE_PROFILE, SITE_PROFILE_KEY


class FakeSettingService:
    async def list_settings(self) -> list[object]:
        return [
            SimpleNamespace(
                id=None,
                key_name=SITE_PROFILE_KEY,
                value_json=DEFAULT_SITE_PROFILE,
                group_name="site",
                is_public=True,
                updated_by=None,
                updated_at=None,
            ),
        ]

    async def update_setting(
        self,
        *,
        key_name: str,
        value_json: dict[str, object],
        group_name: str,
        is_public: bool,
        updated_by: int | None,
    ) -> object:
        return SimpleNamespace(
            id=1,
            key_name=key_name,
            value_json=value_json,
            group_name=group_name,
            is_public=is_public,
            updated_by=updated_by,
            updated_at=None,
        )

    def admin_setting_response(self, setting: object) -> object:
        return setting


class FakeEncryptionSessionManager:
    def __init__(self, decrypted_payload: dict[str, object] | None = None) -> None:
        self.decrypted_payload = decrypted_payload or {}
        self.payload: dict[str, object] | None = None
        self.request_payload: EncryptedApiRequest | None = None

    async def encrypt_response(
        self,
        *,
        session_id: str,
        scope: str,
        profile: EncryptionProfile,
        payload: dict[str, object],
        esid: str | None = None,
        esid_salt_id: str | None = None,
        response_salt_id: str | None = None,
    ) -> EncryptedApiResponse:
        assert scope == "admin"
        assert profile == EncryptionProfile.SENSITIVE
        self.payload = payload
        return EncryptedApiResponse(
            session_id=session_id,
            profile=profile,
            salt_id=response_salt_id or "test-response-salt",
            nonce="test-nonce",
            ciphertext="test-ciphertext",
        )

    async def encrypt_response_for_validated_session(
        self,
        *,
        session_id: str,
        scope: str,
        profile: EncryptionProfile,
        payload: dict[str, object],
        response_salt_id: str,
    ) -> EncryptedApiResponse:
        return await self.encrypt_response(
            session_id=session_id,
            scope=scope,
            profile=profile,
            payload=payload,
            response_salt_id=response_salt_id,
        )

    async def decrypt_request(
        self,
        *,
        session_id: str,
        scope: str,
        profile: EncryptionProfile,
        payload: EncryptedApiRequest,
        esid: str | None = None,
        esid_salt_id: str | None = None,
    ) -> dict[str, object]:
        assert session_id == "sensitive-session"
        assert scope == "admin"
        assert profile == EncryptionProfile.SENSITIVE
        self.request_payload = payload
        return self.decrypted_payload

    async def validate_session(
        self,
        *,
        session_id: str,
        scope: str,
        profile: EncryptionProfile,
        esid: str | None = None,
        esid_salt_id: str | None = None,
    ) -> None:
        assert session_id == "sensitive-session"
        assert scope == "admin"
        assert profile == EncryptionProfile.SENSITIVE


class FakeLogService:
    def __init__(self) -> None:
        self.audit_items: list[dict[str, object]] = []

    async def record_audit_log(self, **kwargs: object) -> None:
        self.audit_items.append(dict(kwargs))


def override_admin_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        id=1,
        username="admin",
        display_name="管理员",
        roles=["super_admin"],
        permissions=["*"],
    )


def test_admin_settings_use_sensitive_encryption_profile() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_setting_service] = lambda: FakeSettingService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager

    try:
        response = client.get(
            "/api/admin/settings",
            headers={
                "X-Encryption-Session": "sensitive-session",
                "X-Encryption-Response-Salt": "test-response-salt",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "sensitive-v1"
    assert manager.payload is not None
    assert manager.payload["items"][0]["key_name"] == SITE_PROFILE_KEY


def test_update_admin_setting_decrypts_sensitive_request() -> None:
    client = TestClient(app)
    client.cookies.set("blog_admin_csrf", "csrf-token")
    logs = FakeLogService()
    manager = FakeEncryptionSessionManager(
        decrypted_payload={
            "value_json": {"title": "静默书房"},
            "group_name": "site",
            "is_public": True,
        },
    )
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_setting_service] = lambda: FakeSettingService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.patch(
            f"/api/admin/settings/{SITE_PROFILE_KEY}",
            headers={
                "X-CSRF-Token": "csrf-token",
                "X-Encryption-Session": "sensitive-session",
                "X-Encryption-Response-Salt": "test-response-salt",
            },
            json={
                "session_id": "sensitive-session",
                "profile": "sensitive-v1",
                "salt_id": "test-request-salt",
                "nonce": "test-nonce",
                "ciphertext": "test-ciphertext",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "sensitive-v1"
    assert manager.request_payload is not None
    assert manager.payload is not None
    assert manager.payload["key_name"] == SITE_PROFILE_KEY
    assert manager.payload["updated_by"] == 1
    assert logs.audit_items[0]["action"] == "setting.update"
    assert logs.audit_items[0]["entity_type"] == "setting"
    assert logs.audit_items[0]["after_json"] == {
        "changed_fields": ["group_name", "is_public", "value_json"],
        "is_public": True,
    }
    assert "key_name" not in logs.audit_items[0]["after_json"]
    assert "group_name" not in logs.audit_items[0]["after_json"]


def test_update_admin_setting_rejects_invalid_key_name_before_decrypt() -> None:
    client = TestClient(app)
    client.cookies.set("blog_admin_csrf", "csrf-token")
    manager = FakeEncryptionSessionManager(
        decrypted_payload={
            "value_json": {"title": "静默书房"},
            "group_name": "site",
            "is_public": True,
        },
    )
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_setting_service] = lambda: FakeSettingService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: FakeLogService()

    try:
        response = client.patch(
            "/api/admin/settings/bad.key",
            headers={
                "X-CSRF-Token": "csrf-token",
                "X-Encryption-Session": "sensitive-session",
            },
            json={
                "session_id": "sensitive-session",
                "profile": "sensitive-v1",
                "salt_id": "test-request-salt",
                "nonce": "test-nonce",
                "ciphertext": "test-ciphertext",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert manager.request_payload is None


def test_update_admin_setting_rejects_oversized_value_json() -> None:
    client = TestClient(app)
    client.cookies.set("blog_admin_csrf", "csrf-token")
    manager = FakeEncryptionSessionManager(
        decrypted_payload={
            "value_json": {"content": "字" * 40_000},
            "group_name": "site",
            "is_public": True,
        },
    )
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_setting_service] = lambda: FakeSettingService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: FakeLogService()

    try:
        response = client.patch(
            f"/api/admin/settings/{SITE_PROFILE_KEY}",
            headers={
                "X-CSRF-Token": "csrf-token",
                "X-Encryption-Session": "sensitive-session",
            },
            json={
                "session_id": "sensitive-session",
                "profile": "sensitive-v1",
                "salt_id": "test-request-salt",
                "nonce": "test-nonce",
                "ciphertext": "test-ciphertext",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
