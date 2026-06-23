from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.admin.dependencies import get_current_admin_user
from app.api.dependencies import (
    get_content_service,
    get_encryption_session_manager,
    get_log_service,
)
from app.core.encryption import EncryptionProfile
from app.main import app
from app.schemas.encryption import EncryptedApiRequest, EncryptedApiResponse
from app.services.auth import AuthenticatedUser
from app.services.content import CreatePostCommand


class FakeContentService:
    async def list_admin_posts(self, *, limit: int, offset: int) -> list[object]:
        return await self.list_posts(limit=limit, offset=offset)

    async def list_posts(self, *, limit: int, offset: int) -> list[object]:
        assert limit == 1
        assert offset == 0
        return [
            SimpleNamespace(
                id=1,
                title="第一篇文章",
                slug="first-post",
                summary="摘要",
                content_md="正文",
                content_html="<p>正文</p>",
                status="draft",
                visibility="public",
                cover_file_id=None,
                author_id=1,
                word_count=1,
                seo_title=None,
                seo_description=None,
                seo_keywords=None,
                category_names=[],
                tag_names=[],
                published_at=None,
                created_at=datetime(2026, 6, 16, tzinfo=UTC),
                updated_at=datetime(2026, 6, 16, tzinfo=UTC),
            ),
        ]

    async def create_post(self, command: CreatePostCommand) -> object:
        return SimpleNamespace(
            id=2,
            title=command.title,
            slug=command.slug,
            summary=command.summary,
            content_md=command.content_md,
            content_html="<p>正文</p>",
            status=command.status,
            visibility=command.visibility,
            cover_file_id=command.cover_file_id,
            author_id=command.author_id,
            word_count=1,
            seo_title=command.seo_title,
            seo_description=command.seo_description,
            seo_keywords=command.seo_keywords,
            category_names=list(command.category_names),
            tag_names=list(command.tag_names),
            published_at=None,
            created_at=datetime(2026, 6, 16, tzinfo=UTC),
            updated_at=datetime(2026, 6, 16, tzinfo=UTC),
        )

    def admin_post_response(self, post: object) -> object:
        return post

    def render_preview(self, content_md: str) -> str:
        assert content_md
        return (
            '<p><img src="/api/public/posts/second-post/files/1/render" '
            'alt="封面"></p>'
        )


class FailIfListCalledContentService(FakeContentService):
    async def list_admin_posts(self, *, limit: int, offset: int) -> list[object]:
        raise AssertionError("post list service should not be called")


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
    ) -> EncryptedApiResponse:
        assert scope == "admin"
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
        scope: str,
        profile: EncryptionProfile,
        payload: EncryptedApiRequest,
        esid: str | None = None,
    ) -> dict[str, object]:
        assert session_id == "content-session"
        assert scope == "admin"
        assert profile == EncryptionProfile.CONTENT
        self.request_payload = payload
        return self.decrypted_payload

    async def validate_session(
        self,
        *,
        session_id: str,
        scope: str,
        profile: EncryptionProfile,
        esid: str | None = None,
    ) -> None:
        assert session_id == "content-session"
        assert scope == "admin"
        assert profile == EncryptionProfile.CONTENT


class FakeLogService:
    def __init__(self) -> None:
        self.audit_items: list[dict[str, object]] = []

    async def record_audit_log(self, **kwargs: object) -> None:
        self.audit_items.append(dict(kwargs))


def test_admin_posts_use_content_encryption_profile() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    app.dependency_overrides[get_current_admin_user] = lambda: AuthenticatedUser(
        id=1,
        username="admin",
        display_name="管理员",
        roles=["super_admin"],
        permissions=["*"],
    )
    app.dependency_overrides[get_content_service] = lambda: FakeContentService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager

    try:
        response = client.get(
            "/api/admin/posts?limit=1",
            headers={"X-Encryption-Session": "content-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert manager.payload["items"][0]["slug"] == "first-post"


def test_admin_posts_reject_missing_encryption_session() -> None:
    client = TestClient(app)
    app.dependency_overrides[get_current_admin_user] = lambda: AuthenticatedUser(
        id=1,
        username="admin",
        display_name="管理员",
        roles=["super_admin"],
        permissions=["*"],
    )
    app.dependency_overrides[get_content_service] = lambda: (
        FailIfListCalledContentService()
    )
    app.dependency_overrides[get_encryption_session_manager] = (
        lambda: FakeEncryptionSessionManager()
    )

    try:
        response = client.get("/api/admin/posts?limit=1")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "missing encryption session"


def test_create_admin_post_decrypts_content_request() -> None:
    client = TestClient(app)
    client.cookies.set("blog_admin_csrf", "csrf-token")
    logs = FakeLogService()
    manager = FakeEncryptionSessionManager(
        decrypted_payload={
            "title": "第二篇文章",
            "slug": "second-post",
            "summary": "摘要",
            "content_md": "正文",
            "status": "draft",
            "visibility": "public",
            "seo_keywords": "博客,发布",
            "category_names": ["技术"],
            "tag_names": ["FastAPI", "React"],
        },
    )
    app.dependency_overrides[get_current_admin_user] = lambda: AuthenticatedUser(
        id=1,
        username="admin",
        display_name="管理员",
        roles=["super_admin"],
        permissions=["*"],
    )
    app.dependency_overrides[get_content_service] = lambda: FakeContentService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.post(
            "/api/admin/posts",
            headers={
                "X-CSRF-Token": "csrf-token",
                "X-Encryption-Session": "content-session",
            },
            json={
                "session_id": "content-session",
                "profile": "content-v1",
                "nonce": "test-nonce",
                "ciphertext": "test-ciphertext",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.request_payload is not None
    assert manager.payload is not None
    assert manager.payload["slug"] == "second-post"
    assert manager.payload["seo_keywords"] == "博客,发布"
    assert manager.payload["category_names"] == ["技术"]
    assert manager.payload["tag_names"] == ["FastAPI", "React"]
    assert logs.audit_items[0]["action"] == "post.create"
    assert logs.audit_items[0]["entity_type"] == "post"
    assert logs.audit_items[0]["entity_id"] == 2
    assert logs.audit_items[0]["after_json"] == {
        "status": "draft",
        "visibility": "public",
        "published_at_set": False,
    }
    assert "title" not in logs.audit_items[0]["after_json"]
    assert "slug" not in logs.audit_items[0]["after_json"]


def test_preview_admin_post_renders_current_markdown() -> None:
    client = TestClient(app)
    client.cookies.set("blog_admin_csrf", "csrf-token")
    manager = FakeEncryptionSessionManager(
        decrypted_payload={
            "slug": "second-post",
            "content_md": "![封面](/api/public/posts/second-post/files/1/render)",
        },
    )
    app.dependency_overrides[get_current_admin_user] = lambda: AuthenticatedUser(
        id=1,
        username="admin",
        display_name="管理员",
        roles=["super_admin"],
        permissions=["*"],
    )
    app.dependency_overrides[get_content_service] = lambda: FakeContentService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager

    try:
        response = client.post(
            "/api/admin/posts/preview",
            headers={
                "X-CSRF-Token": "csrf-token",
                "X-Encryption-Session": "content-session",
            },
            json={
                "session_id": "content-session",
                "profile": "content-v1",
                "nonce": "test-nonce",
                "ciphertext": "test-ciphertext",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    content_html = str(manager.payload["content_html"])
    assert "/api/admin/files/1/preview?expires=" in content_html
    assert "token=" in content_html
