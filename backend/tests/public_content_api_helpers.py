from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_access_log_dedupe_backend,
    get_content_service,
    get_encryption_session_manager,
    get_link_service,
    get_log_service,
    get_post_interaction_service,
    get_rate_limit_service,
    get_setting_service,
)
from app.core.encryption import EncryptionProfile
from app.main import app
from app.schemas.content import PublicPostInteractionState
from app.schemas.encryption import (
    BrowserPublicKey,
    CreateEncryptionSessionResponse,
    EncryptedApiRequest,
    EncryptedApiResponse,
)
from app.services.content import ContentNotFoundError
from app.services.content_read_models import (
    PublicPageDetailRead,
    PublicPostDetailRead,
    PublicPostRead,
    PublicTaxonomyRead,
)
from app.services.encryption import ActiveEncryptionSessionLimitExceeded
from app.services.links import (
    CreateFriendLinkCommand,
    DuplicateFriendLinkApplicationError,
    FriendLinkApplicationLimitExceededError,
    SiteNavItemNotFoundError,
)
from app.services.logs import InMemoryAccessLogDedupeBackend
from app.services.rate_limit import RateLimitRule, RateLimitService
from app.services.settings import SettingService


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
        esid: str | None = None,
        esid_salt_id: str | None = None,
        response_salt_id: str | None = None,
    ) -> EncryptedApiResponse:
        assert session_id == "public-session"
        assert scope == "public"
        assert profile == EncryptionProfile.CONTENT
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
        assert active_session_limit == 60
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
            context_seed="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
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
        esid: str | None = None,
        esid_salt_id: str | None = None,
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
        esid: str | None = None,
        esid_salt_id: str | None = None,
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
            PublicPostRead(
                id=1,
                title="公开文章",
                slug="public-post",
                summary="摘要",
                cover_file_id=1,
                word_count=8,
                view_count=649,
                like_count=11,
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
                view_count=649,
                like_count=11,
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
    ) -> list[PublicTaxonomyRead]:
        assert limit in {2, 1000}
        assert offset == 0
        return [
            PublicTaxonomyRead(id=1, name="技术", slug="category-a", post_count=3),
            PublicTaxonomyRead(id=2, name="随笔", slug="category-b", post_count=1),
        ]

    async def get_public_category_by_slug(self, slug: str) -> PublicTaxonomyRead:
        if slug != "category-a":
            raise ContentNotFoundError("category not found")
        return PublicTaxonomyRead(id=1, name="技术", slug="category-a", post_count=3)

    async def list_public_tags(
        self,
        *,
        limit: int,
        offset: int,
    ) -> list[PublicTaxonomyRead]:
        assert limit in {2, 1000}
        assert offset == 0
        return [
            PublicTaxonomyRead(id=1, name="FastAPI", slug="fastapi", post_count=2),
            PublicTaxonomyRead(id=2, name="React", slug="react", post_count=1),
        ]

    async def get_public_tag_by_slug(self, slug: str) -> PublicTaxonomyRead:
        if slug != "fastapi":
            raise ContentNotFoundError("tag not found")
        return PublicTaxonomyRead(id=1, name="FastAPI", slug="fastapi", post_count=2)

    async def get_public_post_by_slug(self, slug: str) -> PublicPostDetailRead:
        if slug != "public-post":
            raise ContentNotFoundError("post not found")
        return PublicPostDetailRead(
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
            word_count=8,
            view_count=649,
            like_count=11,
            seo_title=None,
            seo_description="SEO 摘要",
            seo_keywords="博客,验证",
            category_names=["技术"],
            tag_names=["FastAPI", "React"],
            published_at=datetime(2026, 6, 16, tzinfo=UTC),
            updated_at=datetime(2026, 6, 16, tzinfo=UTC),
        )

    async def get_public_page_by_slug(self, slug: str) -> PublicPageDetailRead:
        if slug != "about":
            raise ContentNotFoundError("page not found")
        return PublicPageDetailRead(
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


class FakePostInteractionService:
    def __init__(
        self,
        *,
        risk_limited: bool = False,
        missing: bool = False,
    ) -> None:
        self.risk_limited = risk_limited
        self.missing = missing
        self.views: list[dict[str, object]] = []
        self.likes: list[dict[str, object]] = []

    async def record_view(self, **kwargs: object) -> PublicPostInteractionState:
        if self.missing:
            raise ContentNotFoundError("post not found")
        self.views.append(dict(kwargs))
        return PublicPostInteractionState(
            view_count=650,
            like_count=11,
            liked=False,
        )

    async def set_like(self, **kwargs: object) -> PublicPostInteractionState:
        from app.services.post_interactions import PostInteractionRiskLimited

        if self.missing:
            raise ContentNotFoundError("post not found")
        if self.risk_limited:
            raise PostInteractionRiskLimited("risk limited")
        self.likes.append(dict(kwargs))
        return PublicPostInteractionState(
            view_count=650,
            like_count=12 if kwargs.get("liked") else 11,
            liked=bool(kwargs.get("liked")),
        )


class ExplodingFeedContentService:
    async def list_public_feed_posts(self, **_: object) -> list[object]:
        raise AssertionError("feed content service should not be called")

    async def list_public_categories(self, **_: object) -> list[object]:
        raise AssertionError("feed category service should not be called")

    async def list_public_tags(self, **_: object) -> list[object]:
        raise AssertionError("feed tag service should not be called")


class FakePublicLinkService:
    def __init__(
        self,
        *,
        duplicate_application: bool = False,
        application_limit_exceeded: bool = False,
    ) -> None:
        self.site_nav_click_count = 0
        self.duplicate_application = duplicate_application
        self.application_limit_exceeded = application_limit_exceeded

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
                avatar_url="https://example.com/friend-avatar.png",
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

    async def get_public_site_nav_item(self, *, item_id: int) -> object:
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
            click_count=8 + self.site_nav_click_count,
            sort_order=0,
            created_at=datetime(2026, 6, 16, tzinfo=UTC),
            updated_at=datetime(2026, 6, 16, tzinfo=UTC),
        )

    async def record_public_site_nav_click(self, *, item_id: int) -> object:
        self.site_nav_click_count += 1
        return await self.get_public_site_nav_item(item_id=item_id)

    async def create_public_friend_link_application(
        self,
        command: CreateFriendLinkCommand,
    ) -> object:
        assert command.group_id is None
        assert command.name == "新朋友"
        assert command.url == "https://friend.example.test"
        assert command.status == "pending"
        assert command.sort_order == 1000
        if self.duplicate_application:
            raise DuplicateFriendLinkApplicationError("duplicate")
        if self.application_limit_exceeded:
            raise FriendLinkApplicationLimitExceededError("too many pending")
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

    async def get_public_site_profile(self) -> object:
        setting = await self.get_site_profile()
        return _site_profile_response(setting)


def _site_profile_response(setting: object) -> object:
    return SettingService(repository=object()).public_site_profile_response(setting)


def _clear_feed_response_cache() -> None:
    if hasattr(app.state, "feed_response_cache"):
        app.state.feed_response_cache.clear()


__all__ = (
    "ActiveEncryptionSessionLimitExceeded",
    "BrowserPublicKey",
    "ContentNotFoundError",
    "CreateEncryptionSessionResponse",
    "CreateFriendLinkCommand",
    "DuplicateFriendLinkApplicationError",
    "EncryptedApiRequest",
    "EncryptedApiResponse",
    "EncryptionProfile",
    "ExplodingFeedContentService",
    "ExplodingPublicContentService",
    "FakeEncryptionSessionManager",
    "FakeLogService",
    "FakePostInteractionService",
    "FakePublicContentService",
    "FakePublicLinkService",
    "FakeSettingService",
    "FriendLinkApplicationLimitExceededError",
    "InMemoryAccessLogDedupeBackend",
    "PublicPageDetailRead",
    "PublicPostInteractionState",
    "PublicPostDetailRead",
    "PublicPostRead",
    "PublicTaxonomyRead",
    "RateLimitRule",
    "RateLimitService",
    "RejectingRateLimitService",
    "SettingService",
    "SimpleNamespace",
    "SiteNavItemNotFoundError",
    "TestClient",
    "UTC",
    "_clear_feed_response_cache",
    "_site_profile_response",
    "app",
    "datetime",
    "get_access_log_dedupe_backend",
    "get_content_service",
    "get_encryption_session_manager",
    "get_link_service",
    "get_log_service",
    "get_post_interaction_service",
    "get_rate_limit_service",
    "get_setting_service",
)
