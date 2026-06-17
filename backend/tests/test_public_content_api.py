from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.admin.dependencies import (
    get_encryption_session_manager,
    get_log_service,
    get_rate_limit_service,
    get_setting_service,
)
from app.api.public.router import get_public_content_service, get_public_link_service
from app.core.encryption import EncryptionProfile
from app.main import app
from app.schemas.encryption import (
    BrowserPublicKey,
    CreateEncryptionSessionResponse,
    EncryptedApiRequest,
    EncryptedApiResponse,
)
from app.services.content import ContentNotFoundError
from app.services.links import CreateFriendLinkCommand
from app.services.rate_limit import RateLimitService


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

    async def decrypt_request(
        self,
        *,
        session_id: str,
        profile: EncryptionProfile,
        payload: EncryptedApiRequest,
    ) -> dict[str, object]:
        assert session_id == "public-session"
        assert profile == EncryptionProfile.CONTENT
        self.request_payload = payload
        return self.decrypted_payload


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
                cover_file_id=1,
                content_md="中文阅读时长 test-article 2026",
                word_count=1,
                seo_title=None,
                seo_description="SEO 摘要",
                seo_keywords="博客,验证",
                category_names=["技术"],
                tag_names=["FastAPI", "React"],
                published_at=datetime(2026, 6, 16, tzinfo=UTC),
                updated_at=datetime(2026, 6, 16, tzinfo=UTC),
            ),
        ]

    async def list_public_feed_posts(self, *, limit: int) -> list[object]:
        assert limit == 1000
        return [
            SimpleNamespace(
                id=1,
                title="公开文章 & RSS",
                slug="public-post",
                summary="摘要 <需要转义>",
                cover_file_id=1,
                content_md="中文阅读时长 test-article 2026",
                word_count=1,
                seo_title="SEO 标题",
                seo_description="SEO <摘要>",
                seo_keywords="博客,验证",
                category_names=["技术"],
                tag_names=["FastAPI", "React"],
                published_at=datetime(2026, 6, 16, 8, 0, tzinfo=UTC),
                updated_at=datetime(2026, 6, 17, 9, 30, tzinfo=UTC),
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
            cover_file_id=1,
            content_html=(
                '<p><img src="/api/public/posts/public-post/files/1/render" '
                'alt="封面"></p>'
            ),
            content_md="中文阅读时长 test-article 2026",
            word_count=1,
            seo_title=None,
            seo_description="SEO 摘要",
            seo_keywords="博客,验证",
            category_names=["技术"],
            tag_names=["FastAPI", "React"],
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

    async def create_friend_link(self, command: CreateFriendLinkCommand) -> object:
        assert command.group_id is None
        assert command.name == "新朋友"
        assert command.url == "https://friend.example.test"
        assert command.status == "pending"
        assert command.sort_order == 1000
        return SimpleNamespace(
            id=2,
            status=command.status,
        )


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
                "musings": [{"content": "后台碎念", "date": "2026年6月17日"}],
                "social_links": [
                    {"label": "GitHub", "url": "https://github.com/ChaceQC"},
                ],
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


def test_rss_feed_returns_public_posts_xml() -> None:
    client = TestClient(app)
    logs = FakeLogService()
    app.dependency_overrides[get_public_content_service] = (
        lambda: FakePublicContentService()
    )
    app.dependency_overrides[get_setting_service] = lambda: FakeSettingService()
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.get("/rss.xml")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/rss+xml")
    assert "<title>恬妡的小屋</title>" in response.text
    assert "<title>SEO 标题</title>" in response.text
    assert "http://127.0.0.1:15173/posts/public-post" in response.text
    assert "SEO &lt;摘要&gt;" in response.text
    assert "<category>FastAPI</category>" in response.text
    assert logs.items[0]["access_type"] == "public_rss"
    assert logs.items[0]["detail_json"] == {"count": 1}


def test_sitemap_returns_public_post_urls_xml() -> None:
    client = TestClient(app)
    logs = FakeLogService()
    app.dependency_overrides[get_public_content_service] = (
        lambda: FakePublicContentService()
    )
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.get("/sitemap.xml")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    assert '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' in (
        response.text
    )
    assert "<loc>http://127.0.0.1:15173/</loc>" in response.text
    assert "<loc>http://127.0.0.1:15173/posts</loc>" in response.text
    assert (
        "<loc>http://127.0.0.1:15173/posts/public-post</loc>" in response.text
    )
    assert "<lastmod>2026-06-17</lastmod>" in response.text
    assert logs.items[0]["access_type"] == "public_sitemap"


def test_robots_txt_points_to_sitemap_and_hides_admin_paths() -> None:
    client = TestClient(app)
    logs = FakeLogService()
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.get("/robots.txt")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "User-agent: *" in response.text
    assert "Allow: /" in response.text
    assert "Disallow: /admin" in response.text
    assert "Disallow: /api/admin/" in response.text
    assert "Sitemap: http://127.0.0.1:15173/sitemap.xml" in response.text
    assert logs.items[0]["access_type"] == "public_robots"


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
    assert manager.payload["items"][0]["word_count"] == 8
    assert manager.payload["items"][0]["seo_keywords"] == "博客,验证"
    assert manager.payload["items"][0]["category_names"] == ["技术"]
    assert manager.payload["items"][0]["tag_names"] == ["FastAPI", "React"]
    assert (
        "/api/public/posts/public-post/files/1/thumbnail?expires="
        in str(manager.payload["items"][0]["cover_image_url"])
    )
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
    assert manager.payload["word_count"] == 8
    assert (
        "/api/public/posts/public-post/files/1/thumbnail?expires="
        in str(manager.payload["cover_image_url"])
    )
    assert manager.payload["seo_keywords"] == "博客,验证"
    assert manager.payload["category_names"] == ["技术"]
    assert manager.payload["tag_names"] == ["FastAPI", "React"]
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
    assert manager.payload["musings"][0]["content"] == "后台碎念"
    assert manager.payload["social_links"][0]["label"] == "GitHub"
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


def test_public_friend_link_application_decrypts_content_request() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager(
        decrypted_payload={
            "name": "新朋友",
            "url": "https://friend.example.test",
            "avatar_url": "",
            "description": "新的个人站点",
        },
    )
    logs = FakeLogService()
    app.dependency_overrides[get_public_link_service] = lambda: FakePublicLinkService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs
    app.dependency_overrides[get_rate_limit_service] = lambda: RateLimitService()

    try:
        response = client.post(
            "/api/public/friend-links/applications",
            headers={"X-Encryption-Session": "public-session"},
            json={
                "session_id": "public-session",
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
    assert manager.payload["status"] == "pending"
    assert logs.items[0]["access_type"] == "public_friend_link_application"
    assert logs.items[0]["entity_id"] == 2


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
