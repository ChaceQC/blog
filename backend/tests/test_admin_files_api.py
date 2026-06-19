from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.admin.dependencies import get_current_admin_user
from app.api.dependencies import (
    get_content_service,
    get_encryption_session_manager,
    get_file_service,
    get_log_service,
)
from app.core.config import get_settings
from app.core.encryption import EncryptionProfile
from app.main import app
from app.schemas.encryption import EncryptedApiResponse
from app.services.auth import AuthenticatedUser
from app.services.content_read_models import PublicPostDetailRead
from app.services.file_read_models import PublicFileRead
from app.services.files import (
    FileAccessDeniedError,
    FileDownload,
    InvalidFileAccessTokenError,
    UploadFileCommand,
    create_admin_file_preview_token,
    create_article_render_token,
)


class FakeFileService:
    async def list_admin_files(self, *, limit: int, offset: int) -> list[object]:
        return await self.list_files(limit=limit, offset=offset)

    async def list_files(self, *, limit: int, offset: int) -> list[object]:
        assert limit == 1
        assert offset == 0
        return [_file_item()]

    async def upload_file(self, command: UploadFileCommand) -> object:
        assert command.original_name == "cover.png"
        assert command.content_type == "image/png"
        assert command.data.startswith(b"\x89PNG")
        assert command.visibility == "public"
        assert command.public_listed is True
        assert command.alt_text == "封面图"
        assert command.uploader_id == 1
        return _file_item(public_listed=True)

    async def list_public_files(self, *, limit: int, offset: int) -> list[object]:
        assert limit == 1
        assert offset == 0
        return [
            PublicFileRead(
                id=1,
                original_name="cover.png",
                mime_type="image/png",
                extension="png",
                size_bytes=1024,
                width=640,
                height=360,
                alt_text="封面图",
                created_at=datetime(2026, 6, 16, tzinfo=UTC),
                updated_at=datetime(2026, 6, 16, tzinfo=UTC),
            ),
        ]

    async def count_public_files(self) -> int:
        return 1

    async def delete_file(self, file_id: int) -> object:
        assert file_id == 1
        return _file_item(status="deleted")

    def admin_file_response(self, file: object) -> object:
        return file

    async def create_temporary_access(
        self,
        *,
        file_id: int,
        secret_key: str,
        expires_seconds: int,
    ) -> object:
        assert file_id == 1
        assert secret_key
        assert expires_seconds > 0
        return SimpleNamespace(
            file=_file_item(),
            token="signed-token-value",
            expires_at=datetime(2026, 6, 16, tzinfo=UTC),
        )

    async def create_public_temporary_access(
        self,
        *,
        file_id: int,
        secret_key: str,
        expires_seconds: int,
    ) -> object:
        assert file_id == 1
        assert secret_key
        assert expires_seconds > 0
        return SimpleNamespace(
            file=_file_item(public_listed=True),
            token="public-signed-token",
            expires_at=datetime(2026, 6, 16, tzinfo=UTC),
        )


class FailIfUploadCalledFileService(FakeFileService):
    async def upload_file(self, command: UploadFileCommand) -> object:
        raise AssertionError("upload service should not be called")


class FakeDownloadFileService:
    def __init__(self, path) -> None:
        self.path = path

    async def prepare_public_download(
        self,
        *,
        file_id: int,
        token: str,
        secret_key: str,
        upload_root,
    ) -> FileDownload:
        assert file_id == 1
        assert token == "signed-token-value"
        assert secret_key
        assert upload_root
        return FileDownload(
            path=self.path,
            media_type="image/png",
            filename="cover.png",
        )

    async def prepare_article_render(
        self,
        *,
        file_id: int,
        post_slug: str,
        post_cover_file_id: int | None,
        post_content_md: str,
        post_content_html: str,
        upload_root,
    ) -> FileDownload:
        assert file_id == 1
        assert post_slug == "public-post"
        assert post_cover_file_id == 1
        assert "files/1/render" in post_content_md
        assert upload_root
        return FileDownload(
            path=self.path,
            media_type="image/png",
            filename="cover.png",
        )

    async def prepare_article_thumbnail(
        self,
        *,
        file_id: int,
        post_slug: str,
        post_cover_file_id: int | None,
        post_content_md: str,
        post_content_html: str,
        upload_root,
    ) -> FileDownload:
        assert file_id == 1
        assert post_slug == "public-post"
        assert post_cover_file_id == 1
        assert "files/1/render" in post_content_md
        assert upload_root
        return FileDownload(
            path=self.path,
            media_type="image/jpeg",
            filename="cover-thumb.jpg",
        )

    async def prepare_admin_thumbnail(
        self,
        *,
        file_id: int,
        upload_root,
    ) -> FileDownload:
        assert file_id == 1
        assert upload_root
        return FileDownload(
            path=self.path,
            media_type="image/jpeg",
            filename="cover-thumb.jpg",
        )

    async def prepare_admin_download(
        self,
        *,
        file_id: int,
        upload_root,
    ) -> FileDownload:
        assert file_id == 1
        assert upload_root
        return FileDownload(
            path=self.path,
            media_type="application/pdf",
            filename="private-note.pdf",
        )

    async def prepare_admin_preview(
        self,
        *,
        file_id: int,
        token: str,
        expires: int,
        secret_key: str,
        upload_root,
    ) -> FileDownload:
        assert file_id == 1
        assert token
        assert expires > 0
        assert secret_key
        assert upload_root
        return FileDownload(
            path=self.path,
            media_type="image/png",
            filename="cover.png",
        )


class FakeDeniedDownloadFileService:
    async def prepare_public_download(self, **_: object) -> FileDownload:
        raise InvalidFileAccessTokenError("invalid temporary file token")


class FakeDeniedAdminDownloadFileService:
    async def prepare_admin_download(self, **_: object) -> FileDownload:
        raise FileAccessDeniedError("file is not downloadable")


class FakePublicFileContentService:
    async def get_public_post_by_slug(self, slug: str) -> PublicPostDetailRead:
        assert slug == "public-post"
        return PublicPostDetailRead(
            id=1,
            title="公开文章",
            slug=slug,
            summary="摘要",
            cover_file_id=1,
            word_count=8,
            seo_title=None,
            seo_description="SEO 摘要",
            seo_keywords=None,
            category_names=["技术"],
            tag_names=["FastAPI"],
            published_at=datetime(2026, 6, 16, tzinfo=UTC),
            updated_at=datetime(2026, 6, 16, tzinfo=UTC),
            content_md="![封面](/api/public/posts/public-post/files/1/render)",
            content_html=(
                '<p><img src="/api/public/posts/public-post/files/1/render" '
                'alt="封面"></p>'
            ),
        )


class FakeLogService:
    def __init__(self) -> None:
        self.items: list[dict[str, object]] = []
        self.audit_items: list[dict[str, object]] = []

    async def record_access_log(self, **kwargs: object) -> None:
        self.items.append(dict(kwargs))

    async def record_audit_log(self, **kwargs: object) -> None:
        self.audit_items.append(dict(kwargs))


class FakeEncryptionSessionManager:
    def __init__(self, session_id: str = "content-session") -> None:
        self.session_id = session_id
        self.expected_scope = "public" if session_id == "public-session" else "admin"
        self.payload: dict[str, object] | None = None

    async def encrypt_response(
        self,
        *,
        session_id: str,
        scope: str,
        profile: EncryptionProfile,
        payload: dict[str, object],
    ) -> EncryptedApiResponse:
        assert session_id == self.session_id
        assert scope == self.expected_scope
        assert profile == EncryptionProfile.CONTENT
        self.payload = payload
        return EncryptedApiResponse(
            session_id=session_id,
            profile=profile,
            nonce="test-nonce",
            ciphertext="test-ciphertext",
        )

    async def validate_session(
        self,
        *,
        session_id: str,
        scope: str,
        profile: EncryptionProfile,
    ) -> None:
        assert session_id == self.session_id
        assert scope == self.expected_scope
        assert profile == EncryptionProfile.CONTENT


class SmallUploadSettings:
    upload_max_size_bytes = 8


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
    logs = FakeLogService()
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_file_service] = override_file_service
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs
    client = TestClient(app)

    try:
        response = client.post(
            "/api/admin/files",
            headers={
                "X-CSRF-Token": "csrf-token",
                "X-Encryption-Session": "content-session",
            },
            cookies={"blog_admin_csrf": "csrf-token"},
            data={
                "visibility": "public",
                "alt_text": "封面图",
                "public_listed": "true",
            },
            files={"file": ("cover.png", _png_bytes(), "image/png")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert manager.payload["object_key"] == "public/2026/06/cover.png"
    assert logs.audit_items[0]["action"] == "file.upload"
    assert logs.audit_items[0]["entity_type"] == "file"
    assert logs.audit_items[0]["after_json"] == {
        "original_name": "cover.png",
        "mime_type": "image/png",
        "visibility": "public",
        "public_listed": True,
        "status": "active",
    }


def test_admin_file_upload_rejects_oversized_body_before_service() -> None:
    manager = FakeEncryptionSessionManager()
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_file_service] = lambda: FailIfUploadCalledFileService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: FakeLogService()
    app.dependency_overrides[get_settings] = lambda: SmallUploadSettings()
    client = TestClient(app)

    try:
        response = client.post(
            "/api/admin/files",
            headers={
                "X-CSRF-Token": "csrf-token",
                "X-Encryption-Session": "content-session",
            },
            cookies={"blog_admin_csrf": "csrf-token"},
            data={
                "visibility": "public",
                "alt_text": "封面图",
                "public_listed": "true",
            },
            files={"file": ("cover.png", b"012345678", "image/png")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 413
    assert response.json()["detail"] == "file is too large"
    assert manager.payload is None


def test_admin_file_delete_requires_csrf() -> None:
    manager = FakeEncryptionSessionManager()
    logs = FakeLogService()
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_file_service] = override_file_service
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs
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
    assert logs.audit_items[0]["action"] == "file.delete"
    assert logs.audit_items[0]["entity_id"] == 1
    assert logs.audit_items[0]["after_json"]["status"] == "deleted"


def test_admin_file_temporary_url_uses_encrypted_response() -> None:
    manager = FakeEncryptionSessionManager()
    logs = FakeLogService()
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_file_service] = override_file_service
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs
    client = TestClient(app)

    try:
        response = client.get(
            "/api/admin/files/1/temporary-url",
            headers={"X-Encryption-Session": "content-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert (
        manager.payload["url"]
        == "/api/public/files/1/download?token=signed-token-value"
    )
    assert manager.payload["expires_at"] == "2026-06-16T00:00:00Z"
    assert logs.items[0]["access_type"] == "admin_file_temporary_url"


def test_public_file_list_uses_public_encryption_session() -> None:
    manager = FakeEncryptionSessionManager(session_id="public-session")
    logs = FakeLogService()
    app.dependency_overrides[get_file_service] = override_file_service
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs
    client = TestClient(app)

    try:
        response = client.get(
            "/api/public/files?limit=1",
            headers={"X-Encryption-Session": "public-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert manager.payload["total"] == 1
    assert manager.payload["items"][0]["original_name"] == "cover.png"
    assert "object_key" not in manager.payload["items"][0]
    assert logs.items[0]["access_type"] == "public_files_list"
    assert logs.items[0]["path"] == "/api/public/files"


def test_public_file_temporary_url_requires_public_session() -> None:
    manager = FakeEncryptionSessionManager(session_id="public-session")
    logs = FakeLogService()
    app.dependency_overrides[get_file_service] = override_file_service
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs
    client = TestClient(app)

    try:
        response = client.get(
            "/api/public/files/1/temporary-url",
            headers={"X-Encryption-Session": "public-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert (
        manager.payload["url"]
        == "/api/public/files/1/download?token=public-signed-token"
    )
    assert logs.items[0]["access_type"] == "public_file_temporary_url"


def test_public_file_download_uses_temporary_token(tmp_path) -> None:
    file_path = tmp_path / "cover.png"
    file_path.write_bytes(_png_bytes())
    logs = FakeLogService()
    app.dependency_overrides[get_file_service] = (
        lambda: FakeDownloadFileService(file_path)
    )
    app.dependency_overrides[get_log_service] = lambda: logs
    client = TestClient(app)

    try:
        response = client.get(
            "/api/public/files/1/download?token=signed-token-value",
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == _png_bytes()
    assert logs.items[0]["access_type"] == "public_file_download"
    assert logs.items[0]["path"] == "/api/public/files/1/download"


def test_admin_file_download_allows_private_file_with_admin_auth(tmp_path) -> None:
    file_path = tmp_path / "private-note.pdf"
    file_path.write_bytes(b"%PDF-1.7\n")
    logs = FakeLogService()
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_file_service] = (
        lambda: FakeDownloadFileService(file_path)
    )
    app.dependency_overrides[get_log_service] = lambda: logs
    client = TestClient(app)

    try:
        response = client.get("/api/admin/files/1/download")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == b"%PDF-1.7\n"
    assert logs.items[0]["access_type"] == "admin_file_download"
    assert logs.items[0]["entity_id"] == 1
    assert logs.items[0]["detail_json"] == {
        "filename": "private-note.pdf",
        "media_type": "application/pdf",
    }


def test_admin_file_download_records_denied_access() -> None:
    logs = FakeLogService()
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_file_service] = (
        lambda: FakeDeniedAdminDownloadFileService()
    )
    app.dependency_overrides[get_log_service] = lambda: logs
    client = TestClient(app)

    try:
        response = client.get("/api/admin/files/1/download")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["detail"] == "file is not downloadable"
    assert logs.items[0]["access_type"] == "admin_file_download"
    assert logs.items[0]["status_code"] == 403


def test_admin_file_thumbnail_returns_small_preview(tmp_path) -> None:
    file_path = tmp_path / "cover.jpg"
    file_path.write_bytes(_png_bytes())
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_file_service] = (
        lambda: FakeDownloadFileService(file_path)
    )
    client = TestClient(app)

    try:
        response = client.get("/api/admin/files/1/thumbnail")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.content == _png_bytes()


def test_admin_file_preview_uses_signed_cache_headers(tmp_path) -> None:
    file_path = tmp_path / "cover.png"
    file_path.write_bytes(_png_bytes())
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_file_service] = (
        lambda: FakeDownloadFileService(file_path)
    )
    client = TestClient(app)
    settings = get_settings()
    access = create_admin_file_preview_token(
        file_id=1,
        expires_seconds=settings.file_temporary_url_expire_seconds,
        secret_key=settings.secret_key,
    )

    try:
        response = client.get(
            "/api/admin/files/1/preview",
            params={"expires": access.expires, "token": access.token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == _png_bytes()
    _assert_signed_cache_headers(response)


def test_public_file_download_rejects_invalid_token() -> None:
    logs = FakeLogService()
    app.dependency_overrides[get_file_service] = lambda: FakeDeniedDownloadFileService()
    app.dependency_overrides[get_log_service] = lambda: logs
    client = TestClient(app)

    try:
        response = client.get(
            "/api/public/files/1/download?token=signed-token-value",
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["detail"] == "invalid file access"
    assert logs.items[0]["status_code"] == 403


def test_post_file_render_uses_article_image_endpoint(tmp_path) -> None:
    file_path = tmp_path / "cover.png"
    file_path.write_bytes(_png_bytes())
    logs = FakeLogService()
    app.dependency_overrides[get_file_service] = (
        lambda: FakeDownloadFileService(file_path)
    )
    app.dependency_overrides[get_content_service] = (
        lambda: FakePublicFileContentService()
    )
    app.dependency_overrides[get_log_service] = lambda: logs
    client = TestClient(app)
    settings = get_settings()
    access = create_article_render_token(
        post_slug="public-post",
        file_id=1,
        expires_seconds=settings.file_temporary_url_expire_seconds,
        secret_key=settings.secret_key,
    )

    try:
        response = client.get(
            "/api/public/posts/public-post/files/1/render",
            params={"expires": access.expires, "token": access.token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == _png_bytes()
    _assert_signed_cache_headers(response)
    assert logs.items[0]["access_type"] == "post_image_render"
    assert logs.items[0]["path"] == "/api/public/posts/public-post/files/1/render"


def test_post_file_thumbnail_uses_article_image_endpoint(tmp_path) -> None:
    file_path = tmp_path / "cover.jpg"
    file_path.write_bytes(_png_bytes())
    logs = FakeLogService()
    app.dependency_overrides[get_file_service] = (
        lambda: FakeDownloadFileService(file_path)
    )
    app.dependency_overrides[get_content_service] = (
        lambda: FakePublicFileContentService()
    )
    app.dependency_overrides[get_log_service] = lambda: logs
    client = TestClient(app)
    settings = get_settings()
    access = create_article_render_token(
        post_slug="public-post",
        file_id=1,
        expires_seconds=settings.file_temporary_url_expire_seconds,
        secret_key=settings.secret_key,
    )

    try:
        response = client.get(
            "/api/public/posts/public-post/files/1/thumbnail",
            params={"expires": access.expires, "token": access.token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.content == _png_bytes()
    _assert_signed_cache_headers(response)
    assert logs.items[0]["access_type"] == "post_image_thumbnail"
    assert logs.items[0]["path"] == "/api/public/posts/public-post/files/1/thumbnail"


def test_article_render_token_is_stable_inside_cache_window(monkeypatch) -> None:
    settings = get_settings()
    first_now = datetime.fromtimestamp(1_800_000_010, UTC)
    monkeypatch.setattr(
        "app.services.file_tokens.utc_now",
        lambda: first_now,
    )
    first = create_article_render_token(
        post_slug="public-post",
        file_id=1,
        expires_seconds=settings.file_temporary_url_expire_seconds,
        secret_key=settings.secret_key,
    )

    monkeypatch.setattr(
        "app.services.file_tokens.utc_now",
        lambda: datetime.fromtimestamp(1_800_000_040, UTC),
    )
    second = create_article_render_token(
        post_slug="public-post",
        file_id=1,
        expires_seconds=settings.file_temporary_url_expire_seconds,
        secret_key=settings.secret_key,
    )

    monkeypatch.setattr(
        "app.services.file_tokens.utc_now",
        lambda: datetime.fromtimestamp(1_800_000_170, UTC),
    )
    third = create_article_render_token(
        post_slug="public-post",
        file_id=1,
        expires_seconds=settings.file_temporary_url_expire_seconds,
        secret_key=settings.secret_key,
    )

    assert second == first
    assert third.expires > first.expires
    assert third.token != first.token


def test_post_file_render_rejects_missing_image_token(tmp_path) -> None:
    file_path = tmp_path / "cover.png"
    file_path.write_bytes(_png_bytes())
    logs = FakeLogService()
    app.dependency_overrides[get_file_service] = (
        lambda: FakeDownloadFileService(file_path)
    )
    app.dependency_overrides[get_content_service] = (
        lambda: FakePublicFileContentService()
    )
    app.dependency_overrides[get_log_service] = lambda: logs
    client = TestClient(app)

    try:
        response = client.get("/api/public/posts/public-post/files/1/render")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["detail"] == "invalid image access"
    assert logs.items[0]["access_type"] == "post_image_render"
    assert logs.items[0]["status_code"] == 403


def _assert_signed_cache_headers(response) -> None:
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["etag"]
    assert response.headers["cache-control"].startswith("private, max-age=")
    assert response.headers["cache-control"].endswith(", immutable")


def _file_item(status: str = "active", public_listed: bool = False) -> object:
    return SimpleNamespace(
        id=1,
        storage="local",
        bucket=None,
        object_key="public/2026/06/cover.png",
        public_url=None,
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
        public_listed=public_listed,
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
