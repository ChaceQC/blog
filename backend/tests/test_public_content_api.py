from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.admin.dependencies import (
    get_encryption_session_manager,
    get_log_service,
    get_setting_service,
)
from app.api.public.router import get_public_content_service, get_public_link_service
from app.core.encryption import EncryptionProfile
from app.main import app
from app.schemas.encryption import (
    BrowserPublicKey,
    CreateEncryptionSessionResponse,
    EncryptedApiResponse,
)
from app.services.content import ContentNotFoundError


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
        assert session_id == "public-session"
        assert profile == EncryptionProfile.CONTENT
        self.payload = payload
        return EncryptedApiResponse(
            session_id=session_id,
            profile=profile,
            nonce="test-nonce",
            ciphertext="test-ciphertext",
        )

    async def create_session(
        self,
        *,
        client_public_key: BrowserPublicKey,
        scope: str = "admin",
    ) -> CreateEncryptionSessionResponse:
        assert client_public_key.kty == "EC"
        assert scope == "public"
        return CreateEncryptionSessionResponse(
            session_id="public-session",
            scope="public",
            server_public_key=BrowserPublicKey(
                kty="EC",
                crv="P-256",
                x="server-x",
                y="server-y",
            ),
            profiles=[EncryptionProfile.CONTENT],
            expires_at=datetime(2026, 6, 16, tzinfo=UTC),
        )


class FakeLogService:
    def __init__(self) -> None:
        self.items: list[dict[str, object]] = []

    async def record_access_log(self, **kwargs: object) -> None:
        self.items.append(dict(kwargs))


class FakePublicContentService:
    async def list_public_posts(self, *, limit: int, offset: int) -> list[object]:
        assert limit == 1
        assert offset == 0
        return [
            SimpleNamespace(
                id=1,
                title="公开文章",
                slug="public-post",
                summary="摘要",
                word_count=3,
                seo_title=None,
                seo_description="SEO 摘要",
                published_at=datetime(2026, 6, 16, tzinfo=UTC),
                updated_at=datetime(2026, 6, 16, tzinfo=UTC),
            ),
        ]

    async def get_public_post_by_slug(self, slug: str) -> object:
        if slug != "public-post":
            raise ContentNotFoundError("post not found")
        return SimpleNamespace(
            id=1,
            title="公开文章",
            slug="public-post",
            summary="摘要",
            content_html=(
                '<p><img src="/api/public/posts/public-post/files/1/render" '
                'alt="封面"></p>'
            ),
            word_count=3,
            seo_title=None,
            seo_description="SEO 摘要",
            published_at=datetime(2026, 6, 16, tzinfo=UTC),
            updated_at=datetime(2026, 6, 16, tzinfo=UTC),
        )


class FakePublicLinkService:
    async def list_public_friend_links(
        self,
        *,
        limit: int,
        offset: int,
    ) -> list[object]:
        assert limit == 1
        assert offset == 0
        return [
            SimpleNamespace(
                id=1,
                group_name="朋友",
                name="ChaceQC",
                url="https://github.com/ChaceQC",
                avatar_url=None,
                description="项目记录",
                sort_order=0,
            ),
        ]

    async def list_public_site_nav_items(
        self,
        *,
        limit: int,
        offset: int,
    ) -> list[object]:
        assert limit == 1
        assert offset == 0
        return [
            SimpleNamespace(
                id=1,
                group_name="项目",
                group_slug="projects",
                title="GitHub 仓库",
                url="https://github.com/ChaceQC/blog",
                icon_url=None,
                description="源码与提交记录",
                tags_json={"tags": ["blog"]},
                open_target="blank",
                sort_order=0,
            ),
        ]


class FakeSettingService:
    async def get_site_profile(self) -> object:
        return SimpleNamespace(
            key_name="site_profile",
            value_json={
                "title": "恬妡的小屋",
                "owner": "恬妡",
                "avatar_url": "https://example.com/avatar.png",
                "description": "新的首页描述",
                "quote": "新的引文",
            },
        )


def test_public_encryption_session_uses_public_scope() -> None:
    client = TestClient(app)
    app.dependency_overrides[get_encryption_session_manager] = (
        lambda: FakeEncryptionSessionManager()
    )

    try:
        response = client.post(
            "/api/public/encryption/sessions",
            json={
                "client_public_key": {
                    "kty": "EC",
                    "crv": "P-256",
                    "x": "client-x",
                    "y": "client-y",
                },
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["scope"] == "public"


def test_public_posts_returns_published_post_list() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    logs = FakeLogService()
    app.dependency_overrides[get_public_content_service] = (
        lambda: FakePublicContentService()
    )
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.get(
            "/api/public/posts?limit=1",
            headers={"X-Encryption-Session": "public-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert manager.payload["items"][0]["slug"] == "public-post"
    assert "content_html" not in manager.payload["items"][0]
    assert logs.items[0]["access_type"] == "public_posts_list"


def test_public_post_detail_returns_html_content() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    logs = FakeLogService()
    app.dependency_overrides[get_public_content_service] = (
        lambda: FakePublicContentService()
    )
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.get(
            "/api/public/posts/public-post",
            headers={"X-Encryption-Session": "public-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert (
        'src="/api/public/posts/public-post/files/1/render?expires='
        in str(manager.payload["content_html"])
    )
    assert "token=" in str(manager.payload["content_html"])
    assert logs.items[0]["access_type"] == "public_post_detail"
    assert logs.items[0]["entity_id"] == 1


def test_public_site_profile_returns_encrypted_setting() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    logs = FakeLogService()
    app.dependency_overrides[get_setting_service] = lambda: FakeSettingService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.get(
            "/api/public/settings/site-profile",
            headers={"X-Encryption-Session": "public-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert manager.payload["title"] == "恬妡的小屋"
    assert manager.payload["owner"] == "恬妡"
    assert logs.items[0]["access_type"] == "public_site_profile"


def test_public_post_detail_returns_404_for_missing_post() -> None:
    client = TestClient(app)
    logs = FakeLogService()
    app.dependency_overrides[get_public_content_service] = (
        lambda: FakePublicContentService()
    )
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.get("/api/public/posts/missing-post")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "post not found"
    assert logs.items[0]["status_code"] == 404


def test_public_friend_links_return_encrypted_list() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    logs = FakeLogService()
    app.dependency_overrides[get_public_link_service] = lambda: FakePublicLinkService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.get(
            "/api/public/friend-links?limit=1",
            headers={"X-Encryption-Session": "public-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert manager.payload["items"][0]["name"] == "ChaceQC"
    assert logs.items[0]["access_type"] == "public_friend_links_list"


def test_public_site_items_return_encrypted_list() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    logs = FakeLogService()
    app.dependency_overrides[get_public_link_service] = lambda: FakePublicLinkService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.get(
            "/api/public/site-items?limit=1",
            headers={"X-Encryption-Session": "public-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert manager.payload["items"][0]["title"] == "GitHub 仓库"
    assert logs.items[0]["access_type"] == "public_site_items_list"
