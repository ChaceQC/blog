from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.admin.dependencies import (
    get_current_admin_user,
    get_encryption_session_manager,
    get_file_service,
)
from app.core.encryption import EncryptionProfile
from app.main import app
from app.schemas.encryption import EncryptedApiResponse
from app.services.auth import AuthenticatedUser
from app.services.files import UploadFileCommand


class FakeFileService:
    async def list_files(self, *, limit: int, offset: int) -> list[object]:
        assert limit == 1
        assert offset == 0
        return [_file_item()]

    async def upload_file(self, command: UploadFileCommand) -> object:
        assert command.original_name == "cover.png"
        assert command.content_type == "image/png"
        assert command.data.startswith(b"\x89PNG")
        assert command.visibility == "public"
        assert command.alt_text == "封面图"
        assert command.uploader_id == 1
        return _file_item()

    async def delete_file(self, file_id: int) -> object:
        assert file_id == 1
        return _file_item(status="deleted")


class FakeEncryptionSessionManager:
    def __init__(self) -> None:
        self.payload: dict[str, object] | None = None

    async def encrypt_response(
        self,
        *,
        session_id: str,
        profile: EncryptionProfile,
        payload: dict[str, object],
    ) -> EncryptedApiResponse:
        assert session_id == "content-session"
        assert profile == EncryptionProfile.CONTENT
        self.payload = payload
        return EncryptedApiResponse(
            session_id=session_id,
            profile=profile,
            algorithm="AES-256-GCM-HKDF-SHA256",
            nonce="test-nonce",
            ciphertext="test-ciphertext",
        )


def override_admin_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        id=1,
        username="admin",
        display_name="管理员",
        roles=["super_admin"],
        permissions=["*"],
    )


def override_file_service() -> FakeFileService:
    return FakeFileService()


def test_admin_files_use_content_encryption_profile() -> None:
    manager = FakeEncryptionSessionManager()
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_file_service] = override_file_service
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    client = TestClient(app)

    try:
        response = client.get(
            "/api/admin/files?limit=1&offset=0",
            headers={"X-Encryption-Session": "content-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert manager.payload["items"][0]["original_name"] == "cover.png"


def test_admin_file_upload_accepts_multipart_and_csrf() -> None:
    manager = FakeEncryptionSessionManager()
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_file_service] = override_file_service
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    client = TestClient(app)

    try:
        response = client.post(
            "/api/admin/files",
            headers={
                "X-CSRF-Token": "csrf-token",
                "X-Encryption-Session": "content-session",
            },
            cookies={"blog_admin_csrf": "csrf-token"},
            data={"visibility": "public", "alt_text": "封面图"},
            files={"file": ("cover.png", _png_bytes(), "image/png")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert manager.payload["object_key"] == "public/2026/06/cover.png"


def test_admin_file_delete_requires_csrf() -> None:
    manager = FakeEncryptionSessionManager()
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_file_service] = override_file_service
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    client = TestClient(app)

    try:
        response = client.delete(
            "/api/admin/files/1",
            headers={
                "X-CSRF-Token": "csrf-token",
                "X-Encryption-Session": "content-session",
            },
            cookies={"blog_admin_csrf": "csrf-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert manager.payload["status"] == "deleted"


def _file_item(status: str = "active") -> object:
    return SimpleNamespace(
        id=1,
        storage="local",
        bucket=None,
        object_key="public/2026/06/cover.png",
        public_url="/uploads/2026/06/cover.png",
        original_name="cover.png",
        mime_type="image/png",
        extension="png",
        size_bytes=68,
        sha256="a" * 64,
        width=1,
        height=1,
        alt_text="封面图",
        uploader_id=1,
        visibility="public",
        status=status,
        usage_count=0,
        created_at=datetime(2026, 6, 16, tzinfo=UTC),
        updated_at=datetime(2026, 6, 16, tzinfo=UTC),
    )


def _png_bytes() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00"
        b"\x90wS\xde"
    )
