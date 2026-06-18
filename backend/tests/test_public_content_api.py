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
from app.services.encryption import ActiveEncryptionSessionLimitExceeded
from app.services.links import CreateFriendLinkCommand, SiteNavItemNotFoundError
from app.services.rate_limit import RateLimitRule, RateLimitService


class FakeEncryptionSessionManager:
    def __init__(
        self,
        decrypted_payload: dict[str, object] | None = None,
        *,
        raise_active_limit: bool = False,
    ) -> None:
        self.decrypted_payload = decrypted_payload or {}
        self.raise_active_limit = raise_active_limit
        self.payload: dict[str, object] | None = None
        self.request_payload: EncryptedApiRequest | None = None

    async def encrypt_response(
        self,
        *,
        session_id: str,
        scope: str,
        profile: EncryptionProfile,
        payload: dict[str, object],
    ) -> EncryptedApiResponse:
        assert session_id == "public-session"
        assert scope == "public"
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
        client_ip: str | None = None,
        active_session_limit: int | None = None,
    ) -> CreateEncryptionSessionResponse:
        assert client_public_key.kty == "EC"
        assert scope == "public"
        assert client_ip == "testclient"
        assert active_session_limit == 10
        if self.raise_active_limit:
            raise ActiveEncryptionSessionLimitExceeded(
                "too many active encryption sessions",
            )
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
        scope: str,
        profile: EncryptionProfile,
        payload: EncryptedApiRequest,
    ) -> dict[str, object]:
        assert session_id == "public-session"
        assert scope == "public"
        assert profile == EncryptionProfile.CONTENT
        self.request_payload = payload
        return self.decrypted_payload

    async def validate_session(
        self,
        *,
        session_id: str,
        scope: str,
        profile: EncryptionProfile,
    ) -> None:
        assert session_id == "public-session"
        assert scope == "public"
        assert profile == EncryptionProfile.CONTENT


class FakeLogService:
    def __init__(self) -> None:
        self.items: list[dict[str, object]] = []
        self.events: list[dict[str, object]] = []

    async def record_access_log(self, **kwargs: object) -> None:
        self.items.append(dict(kwargs))

    async def record_security_event(self, **kwargs: object) -> None:
        self.events.append(dict(kwargs))


class RejectingRateLimitService(RateLimitService):
    def check(
        self,
        *,
        key: str,
        rule: RateLimitRule,
        now=None,
    ) -> None:
        from app.services.rate_limit import RateLimitExceeded

        raise RateLimitExceeded(9)


class FakePublicContentService:
    async def list_public_posts(
        self,
        *,
        limit: int,
        offset: int,
        category_slug: str | None = None,
        tag_slug: str | None = None,
    ) -> list[object]:
        assert limit in {1, 2}
        assert offset == 0
        if limit == 1:
            assert category_slug is None
            assert tag_slug is None
        if limit == 2:
            assert category_slug == "category-a"
            assert tag_slug == "fastapi"
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

    async def count_public_posts(
        self,
        *,
        category_slug: str | None = None,
        tag_slug: str | None = None,
    ) -> int:
        if category_slug is not None or tag_slug is not None:
            assert category_slug == "category-a"
            assert tag_slug == "fastapi"
        return 1

    async def list_public_categories(
        self,
        *,
        limit: int,
        offset: int,
    ) -> list[dict[str, object]]:
        assert limit in {2, 1000}
        assert offset == 0
        return [
            {"id": 1, "name": "技术", "slug": "category-a", "post_count": 3},
            {"id": 2, "name": "随笔", "slug": "category-b", "post_count": 1},
        ]

    async def get_public_category_by_slug(self, slug: str) -> dict[str, object]:
        if slug != "category-a":
            raise ContentNotFoundError("category not found")
        return {"id": 1, "name": "技术", "slug": "category-a", "post_count": 3}

    async def list_public_tags(
        self,
        *,
        limit: int,
        offset: int,
    ) -> list[dict[str, object]]:
        assert limit in {2, 1000}
        assert offset == 0
        return [
            {"id": 1, "name": "FastAPI", "slug": "fastapi", "post_count": 2},
            {"id": 2, "name": "React", "slug": "react", "post_count": 1},
        ]

    async def get_public_tag_by_slug(self, slug: str) -> dict[str, object]:
        if slug != "fastapi":
            raise ContentNotFoundError("tag not found")
        return {"id": 1, "name": "FastAPI", "slug": "fastapi", "post_count": 2}

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

    async def get_public_page_by_slug(self, slug: str) -> object:
        if slug != "about":
            raise ContentNotFoundError("page not found")
        return SimpleNamespace(
            id=3,
            title="关于",
            slug="about",
            content_html="<p>这里是关于页面。</p>",
            seo_title="关于静默书房",
            seo_description="关于这个长期写作空间",
            updated_at=datetime(2026, 6, 17, tzinfo=UTC),
        )


class ExplodingPublicContentService:
    async def list_public_posts(self, **_: object) -> list[object]:
        raise AssertionError("public content service should not be called")

    async def count_public_posts(self, **_: object) -> int:
        raise AssertionError("public content service should not be called")


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

    async def count_public_friend_links(self) -> int:
        return 1

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

    async def count_public_site_nav_items(self) -> int:
        return 1

    async def record_public_site_nav_click(self, *, item_id: int) -> object:
        if item_id != 1:
            raise SiteNavItemNotFoundError("site nav item not found")
        return SimpleNamespace(
            id=1,
            group_name="项目",
            group_slug="projects",
            title="GitHub 仓库",
            url="https://github.com/ChaceQC/blog",
            icon_url=None,
            description="源码与提交记录",
            tags_json={"tags": ["blog"]},
            open_target="blank",
            visibility="public",
            click_count=8,
            sort_order=0,
            created_at=datetime(2026, 6, 16, tzinfo=UTC),
            updated_at=datetime(2026, 6, 16, tzinfo=UTC),
        )

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
    app.dependency_overrides[get_log_service] = lambda: FakeLogService()
    app.dependency_overrides[get_rate_limit_service] = lambda: RateLimitService()

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


def test_public_encryption_session_records_rate_limit_hit() -> None:
    client = TestClient(app)
    logs = FakeLogService()
    app.dependency_overrides[get_encryption_session_manager] = (
        lambda: FakeEncryptionSessionManager()
    )
    app.dependency_overrides[get_log_service] = lambda: logs
    app.dependency_overrides[get_rate_limit_service] = (
        lambda: RejectingRateLimitService()
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

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "9"
    assert logs.events[0]["event_type"] == "rate_limit.public_encryption_session"


def test_public_encryption_session_rejects_active_session_overflow() -> None:
    client = TestClient(app)
    logs = FakeLogService()
    app.dependency_overrides[get_encryption_session_manager] = (
        lambda: FakeEncryptionSessionManager(raise_active_limit=True)
    )
    app.dependency_overrides[get_log_service] = lambda: logs
    app.dependency_overrides[get_rate_limit_service] = lambda: RateLimitService()

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

    assert response.status_code == 429
    assert response.json()["detail"] == "too many active encryption sessions"
    assert logs.events[0]["event_type"] == "rate_limit.public_encryption_session_active"


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
    assert response.headers["cache-control"] == (
        "public, max-age=300, stale-while-revalidate=60"
    )
    assert response.headers["etag"]
    assert "<title>恬妡的小屋</title>" in response.text
    assert "<title>SEO 标题</title>" in response.text
    assert "http://127.0.0.1:15173/posts/public-post" in response.text
    assert "SEO &lt;摘要&gt;" in response.text
    assert "<category>FastAPI</category>" in response.text
    assert logs.items[0]["access_type"] == "public_rss"
    assert logs.items[0]["detail_json"] == {"count": 1}


def test_rss_feed_returns_304_without_access_log_for_matching_etag() -> None:
    client = TestClient(app)
    logs = FakeLogService()
    app.dependency_overrides[get_public_content_service] = (
        lambda: FakePublicContentService()
    )
    app.dependency_overrides[get_setting_service] = lambda: FakeSettingService()
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        first = client.get("/rss.xml")
        logs.items.clear()
        second = client.get(
            "/rss.xml",
            headers={"If-None-Match": first.headers["etag"]},
        )
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 200
    assert second.status_code == 304
    assert second.content == b""
    assert second.headers["etag"] == first.headers["etag"]
    assert logs.items == []


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
    assert response.headers["etag"]
    assert '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' in (
        response.text
    )
    assert "<loc>http://127.0.0.1:15173/</loc>" in response.text
    assert "<loc>http://127.0.0.1:15173/posts</loc>" in response.text
    assert (
        "<loc>http://127.0.0.1:15173/posts/public-post</loc>" in response.text
    )
    assert (
        "<loc>http://127.0.0.1:15173/categories/category-a</loc>" in response.text
    )
    assert "<loc>http://127.0.0.1:15173/tags/fastapi</loc>" in response.text
    assert "<lastmod>2026-06-17</lastmod>" in response.text
    assert logs.items[0]["access_type"] == "public_sitemap"
    assert logs.items[0]["detail_json"] == {"count": 5}


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
    assert manager.payload["total"] == 1
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
    assert logs.items[0]["path"] == "/api/public/posts"


def test_public_posts_validate_session_before_query() -> None:
    client = TestClient(app)
    app.dependency_overrides[get_public_content_service] = (
        lambda: ExplodingPublicContentService()
    )
    app.dependency_overrides[get_encryption_session_manager] = (
        lambda: FakeEncryptionSessionManager()
    )
    app.dependency_overrides[get_log_service] = lambda: FakeLogService()

    try:
        response = client.get("/api/public/posts?limit=1")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "missing encryption session"


def test_public_posts_rejects_oversized_offset() -> None:
    client = TestClient(app)

    response = client.get(
        "/api/public/posts?limit=1&offset=10001",
        headers={"X-Encryption-Session": "public-session"},
    )

    assert response.status_code == 422


def test_public_posts_accept_category_and_tag_filters() -> None:
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
            "/api/public/posts?limit=2&category=category-a&tag=fastapi",
            headers={"X-Encryption-Session": "public-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert manager.payload["total"] == 1
    assert manager.payload["items"][0]["slug"] == "public-post"
    assert logs.items[0]["access_type"] == "public_posts_list"
    assert logs.items[0]["path"] == "/api/public/posts"


def test_public_categories_return_encrypted_list() -> None:
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
            "/api/public/categories?limit=2",
            headers={"X-Encryption-Session": "public-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert manager.payload["items"][0] == {
        "id": 1,
        "name": "技术",
        "slug": "category-a",
        "post_count": 3,
    }
    assert logs.items[0]["access_type"] == "public_categories_list"
    assert logs.items[0]["path"] == "/api/public/categories"


def test_public_category_detail_returns_encrypted_item() -> None:
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
            "/api/public/categories/category-a",
            headers={"X-Encryption-Session": "public-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload == {
        "id": 1,
        "name": "技术",
        "slug": "category-a",
        "post_count": 3,
    }
    assert logs.items[0]["access_type"] == "public_category_detail"
    assert logs.items[0]["path"] == "/api/public/categories/category-a"


def test_public_category_detail_returns_404_for_missing_category() -> None:
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
            "/api/public/categories/missing-category",
            headers={"X-Encryption-Session": "public-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "category not found"
    assert logs.items[0]["status_code"] == 404


def test_public_tags_return_encrypted_list() -> None:
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
            "/api/public/tags?limit=2",
            headers={"X-Encryption-Session": "public-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert manager.payload["items"][0] == {
        "id": 1,
        "name": "FastAPI",
        "slug": "fastapi",
        "post_count": 2,
    }
    assert logs.items[0]["access_type"] == "public_tags_list"
    assert logs.items[0]["path"] == "/api/public/tags"


def test_public_tag_detail_returns_encrypted_item() -> None:
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
            "/api/public/tags/fastapi",
            headers={"X-Encryption-Session": "public-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload == {
        "id": 1,
        "name": "FastAPI",
        "slug": "fastapi",
        "post_count": 2,
    }
    assert logs.items[0]["access_type"] == "public_tag_detail"
    assert logs.items[0]["path"] == "/api/public/tags/fastapi"


def test_public_tag_detail_returns_404_for_missing_tag() -> None:
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
            "/api/public/tags/missing-tag",
            headers={"X-Encryption-Session": "public-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "tag not found"
    assert logs.items[0]["status_code"] == 404


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
    assert logs.items[0]["path"] == "/api/public/posts/public-post"


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
    assert logs.items[0]["path"] == "/api/public/settings/site-profile"


def test_public_site_profile_filters_unsafe_social_href() -> None:
    class UnsafeSettingService:
        async def get_site_profile(self) -> object:
            return SimpleNamespace(
                key_name="site_profile",
                value_json={
                    "title": "静默书房",
                    "owner": "ChaceQC",
                    "avatar_url": "mailto:avatar@example.com",
                    "description": "描述",
                    "quote": "引文",
                    "social_links": [
                        {"label": "RSS", "url": "/rss.xml"},
                        {"label": "坏链接", "url": "javascript:alert(1)"},
                    ],
                },
            )

    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    logs = FakeLogService()
    app.dependency_overrides[get_setting_service] = lambda: UnsafeSettingService()
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
    assert manager.payload is not None
    assert manager.payload["avatar_url"] == "https://github.com/ChaceQC.png"
    assert manager.payload["social_links"] == [{"label": "RSS", "url": "/rss.xml"}]


def test_public_site_profile_bounds_legacy_oversized_values() -> None:
    class OversizedSettingService:
        async def get_site_profile(self) -> object:
            return SimpleNamespace(
                key_name="site_profile",
                value_json={
                    "title": "站" * 100,
                    "owner": "主人" * 100,
                    "avatar_url": "https://example.com/" + "a" * 1200,
                    "description": "描述" * 400,
                    "quote": "引文" * 400,
                    "musings": [
                        {"content": "碎念" * 400, "date": "日期" * 80},
                        {"content": "第二条", "date": "2026"},
                        {"content": "第三条", "date": "2026"},
                        {"content": "第四条", "date": "2026"},
                    ],
                    "social_links": [
                        {"label": f"链接{i}", "url": f"https://example.com/{i}"}
                        for i in range(20)
                    ],
                },
            )

    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    logs = FakeLogService()
    app.dependency_overrides[get_setting_service] = lambda: OversizedSettingService()
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
    assert manager.payload is not None
    assert len(manager.payload["title"]) == 80
    assert len(manager.payload["owner"]) == 80
    assert len(manager.payload["description"]) == 500
    assert len(manager.payload["quote"]) == 500
    assert len(manager.payload["musings"]) == 3
    assert len(manager.payload["musings"][0]["content"]) == 500
    assert len(manager.payload["musings"][0]["date"]) == 80
    assert len(manager.payload["social_links"]) == 12


def test_public_post_detail_returns_404_for_missing_post() -> None:
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
            "/api/public/posts/missing-post",
            headers={"X-Encryption-Session": "public-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "post not found"
    assert logs.items[0]["status_code"] == 404


def test_public_page_detail_returns_html_content() -> None:
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
            "/api/public/pages/about",
            headers={"X-Encryption-Session": "public-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload == {
        "id": 3,
        "title": "关于",
        "slug": "about",
        "content_html": "<p>这里是关于页面。</p>",
        "seo_title": "关于静默书房",
        "seo_description": "关于这个长期写作空间",
        "updated_at": "2026-06-17T00:00:00Z",
    }
    assert logs.items[0]["access_type"] == "public_page_detail"
    assert logs.items[0]["path"] == "/api/public/pages/about"


def test_public_page_detail_returns_404_for_missing_page() -> None:
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
            "/api/public/pages/missing-page",
            headers={"X-Encryption-Session": "public-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "page not found"
    assert logs.items[0]["access_type"] == "public_page_detail"
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
    assert manager.payload["total"] == 1
    assert manager.payload["items"][0]["name"] == "ChaceQC"
    assert logs.items[0]["access_type"] == "public_friend_links_list"
    assert logs.items[0]["path"] == "/api/public/friend-links"


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
    assert manager.payload["total"] == 1
    assert manager.payload["items"][0]["title"] == "GitHub 仓库"
    assert logs.items[0]["access_type"] == "public_site_items_list"
    assert logs.items[0]["path"] == "/api/public/site-items"


def test_public_site_item_visit_records_click_and_redirects() -> None:
    client = TestClient(app)
    logs = FakeLogService()
    app.dependency_overrides[get_public_link_service] = lambda: FakePublicLinkService()
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.get("/api/public/site-items/1/visit", follow_redirects=False)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 302
    assert response.headers["location"] == "https://github.com/ChaceQC/blog"
    assert logs.items[0]["access_type"] == "public_site_item_visit"
    assert logs.items[0]["entity_id"] == 1
    assert logs.items[0]["detail_json"] == {
        "click_count": 8,
        "open_target": "blank",
    }


def test_public_site_item_visit_returns_404_for_missing_item() -> None:
    client = TestClient(app)
    logs = FakeLogService()
    app.dependency_overrides[get_public_link_service] = lambda: FakePublicLinkService()
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.get("/api/public/site-items/404/visit")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "site nav item not found"
    assert logs.items[0]["access_type"] == "public_site_item_visit"
    assert logs.items[0]["status_code"] == 404
