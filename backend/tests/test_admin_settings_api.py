from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.admin.dependencies import (
    get_current_admin_user,
    get_encryption_session_manager,
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


class FakeEncryptionSessionManager:
    def __init__(self, decrypted_payload: dict[str, object] | None = None) -> None:
        self.decrypted_payload = decrypted_payload or {}
        self.payload: dict[str, object] | None = None
        self.request_payload: EncryptedApiRequest | None = None

    async def encrypt_response(
        self,
        *,
        session_id: str,
        profile: EncryptionProfile,
        payload: dict[str, object],
    ) -> EncryptedApiResponse:
        assert profile == EncryptionProfile.SENSITIVE
        self.payload = payload
        return EncryptedApiResponse(
            session_id=session_id,
            profile=profile,
            nonce="test-nonce",
            ciphertext="test-ciphertext",
        )

    async def decrypt_request(
        self,
        *,
        session_id: str,
        profile: EncryptionProfile,
        payload: EncryptedApiRequest,
    ) -> dict[str, object]:
        assert session_id == "sensitive-session"
        assert profile == EncryptionProfile.SENSITIVE
        self.request_payload = payload
        return self.decrypted_payload


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
            headers={"X-Encryption-Session": "sensitive-session"},
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
