from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.admin.dependencies import (
    get_content_service,
    get_current_admin_user,
    get_encryption_session_manager,
)
from app.core.encryption import EncryptionProfile
from app.main import app
from app.schemas.encryption import EncryptedApiResponse
from app.services.auth import AuthenticatedUser


class FakeContentService:
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
                author_id=1,
                word_count=1,
                seo_title=None,
                seo_description=None,
                published_at=None,
                created_at=datetime(2026, 6, 16, tzinfo=UTC),
                updated_at=datetime(2026, 6, 16, tzinfo=UTC),
            ),
        ]


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
        self.payload = payload
        return EncryptedApiResponse(
            session_id=session_id,
            profile=profile,
            algorithm="AES-256-GCM-HKDF-SHA256",
            nonce="test-nonce",
            ciphertext="test-ciphertext",
        )


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
    app.dependency_overrides[get_content_service] = lambda: FakeContentService()
    app.dependency_overrides[get_encryption_session_manager] = (
        lambda: FakeEncryptionSessionManager()
    )

    try:
        response = client.get("/api/admin/posts?limit=1")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "missing encryption session"
