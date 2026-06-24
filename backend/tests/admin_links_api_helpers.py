from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.admin.dependencies import (
    get_current_admin_user,
    get_link_group_service,
)
from app.api.dependencies import (
    get_encryption_session_manager,
    get_link_service,
    get_log_service,
)
from app.core.encryption import EncryptionProfile
from app.main import app
from app.schemas.encryption import EncryptedApiRequest, EncryptedApiResponse
from app.services.auth import AuthenticatedUser
from app.services.link_groups import (
    CreateFriendLinkGroupCommand,
    CreateSiteNavGroupCommand,
    UpdateFriendLinkGroupCommand,
    UpdateSiteNavGroupCommand,
)
from app.services.links import (
    CreateFriendLinkCommand,
    CreateSiteNavItemCommand,
    UpdateFriendLinkCommand,
    UpdateSiteNavItemCommand,
)


class FakeLinkService:
    async def list_friend_links(self, *, limit: int, offset: int) -> list[object]:
        assert limit == 1
        assert offset == 0
        return [
            SimpleNamespace(
                id=1,
                group_id=1,
                group_name="朋友",
                name="静默书房",
                url="https://blog.example.test",
                avatar_url=None,
                description="长期写作入口",
                rss_url=None,
                status="pending",
                sort_order=0,
                last_checked_at=None,
                last_status_code=None,
                created_at=datetime(2026, 6, 16, tzinfo=UTC),
                updated_at=datetime(2026, 6, 16, tzinfo=UTC),
            ),
        ]

    async def review_friend_link(self, *, link_id: int, status: str) -> object:
        assert link_id == 1
        assert status == "healthy"
        return SimpleNamespace(
            id=1,
            group_id=1,
            group_name=None,
            name="静默书房",
            url="https://blog.example.test",
            avatar_url=None,
            description="长期写作入口",
            rss_url=None,
            status=status,
            sort_order=0,
            last_checked_at=None,
            last_status_code=None,
            created_at=datetime(2026, 6, 16, tzinfo=UTC),
            updated_at=datetime(2026, 6, 16, tzinfo=UTC),
        )

    async def create_friend_link(self, command: CreateFriendLinkCommand) -> object:
        assert command.name == "新友链"
        assert command.url == "https://new-link.example.test"
        return SimpleNamespace(
            id=2,
            group_id=command.group_id,
            group_name=None,
            name=command.name,
            url=command.url,
            avatar_url=command.avatar_url,
            description=command.description,
            rss_url=command.rss_url,
            status=command.status,
            sort_order=command.sort_order,
            last_checked_at=None,
            last_status_code=None,
            created_at=datetime(2026, 6, 16, tzinfo=UTC),
            updated_at=datetime(2026, 6, 16, tzinfo=UTC),
        )

    async def update_friend_link(
        self,
        *,
        link_id: int,
        command: UpdateFriendLinkCommand,
    ) -> object:
        assert link_id == 1
        assert command.name == "更新后的友链"
        return SimpleNamespace(
            id=1,
            group_id=1,
            group_name=None,
            name=command.name,
            url=(
                command.url
                if isinstance(command.url, str)
                else "https://blog.example.test"
            ),
            avatar_url=None,
            description=(
                command.description if isinstance(command.description, str) else None
            ),
            rss_url=None,
            status=command.status if isinstance(command.status, str) else "pending",
            sort_order=0,
            last_checked_at=None,
            last_status_code=None,
            created_at=datetime(2026, 6, 16, tzinfo=UTC),
            updated_at=datetime(2026, 6, 16, tzinfo=UTC),
        )

    async def delete_friend_link(self, link_id: int) -> object:
        assert link_id == 1
        return SimpleNamespace(
            id=1,
            group_id=1,
            group_name=None,
            name="静默书房",
            url="https://blog.example.test",
            avatar_url=None,
            description="长期写作入口",
            rss_url=None,
            status="pending",
            sort_order=0,
            last_checked_at=None,
            last_status_code=None,
            created_at=datetime(2026, 6, 16, tzinfo=UTC),
            updated_at=datetime(2026, 6, 16, tzinfo=UTC),
        )

    async def list_site_nav_items(self, *, limit: int, offset: int) -> list[object]:
        assert limit == 1
        assert offset == 0
        return [
            SimpleNamespace(
                id=1,
                group_id=1,
                group_name="项目",
                group_slug="projects",
                title="博客源码",
                url="https://github.com/ChaceQC/blog",
                icon_url=None,
                description="源码和提交记录",
                tags_json={"items": ["blog"]},
                open_target="blank",
                visibility="public",
                click_count=0,
                sort_order=0,
                created_at=datetime(2026, 6, 16, tzinfo=UTC),
                updated_at=datetime(2026, 6, 16, tzinfo=UTC),
            ),
        ]

    async def create_site_nav_item(self, command: CreateSiteNavItemCommand) -> object:
        assert command.title == "新导航"
        assert command.url == "https://nav.example.test"
        assert command.tags_json == {"items": ["工具", "博客"]}
        assert command.open_target == "self"
        return SimpleNamespace(
            id=2,
            group_id=command.group_id,
            group_name=None,
            group_slug=None,
            title=command.title,
            url=command.url,
            icon_url=command.icon_url,
            description=command.description,
            tags_json=command.tags_json,
            open_target=command.open_target,
            visibility=command.visibility,
            click_count=0,
            sort_order=command.sort_order,
            created_at=datetime(2026, 6, 16, tzinfo=UTC),
            updated_at=datetime(2026, 6, 16, tzinfo=UTC),
        )

    async def update_site_nav_item(
        self,
        *,
        item_id: int,
        command: UpdateSiteNavItemCommand,
    ) -> object:
        assert item_id == 1
        assert command.title == "更新后的导航"
        return SimpleNamespace(
            id=1,
            group_id=1,
            group_name=None,
            group_slug=None,
            title=command.title,
            url=(
                command.url
                if isinstance(command.url, str)
                else "https://github.com/ChaceQC/blog"
            ),
            icon_url=command.icon_url if isinstance(command.icon_url, str) else None,
            description=(
                command.description if isinstance(command.description, str) else None
            ),
            tags_json=(
                command.tags_json if isinstance(command.tags_json, dict) else None
            ),
            open_target=(
                command.open_target if isinstance(command.open_target, str) else "blank"
            ),
            visibility=(
                command.visibility if isinstance(command.visibility, str) else "public"
            ),
            click_count=0,
            sort_order=0,
            created_at=datetime(2026, 6, 16, tzinfo=UTC),
            updated_at=datetime(2026, 6, 16, tzinfo=UTC),
        )

    async def delete_site_nav_item(self, item_id: int) -> object:
        assert item_id == 1
        return SimpleNamespace(
            id=1,
            group_id=1,
            group_name=None,
            group_slug=None,
            title="博客源码",
            url="https://github.com/ChaceQC/blog",
            icon_url=None,
            description="源码和提交记录",
            tags_json={"items": ["blog"]},
            open_target="blank",
            visibility="public",
            click_count=0,
            sort_order=0,
            created_at=datetime(2026, 6, 16, tzinfo=UTC),
            updated_at=datetime(2026, 6, 16, tzinfo=UTC),
        )


class FakeLinkGroupService:
    async def list_friend_link_groups(
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
                name="朋友",
                slug="friends",
                sort_order=0,
                created_at=datetime(2026, 6, 16, tzinfo=UTC),
            ),
        ]

    async def create_friend_link_group(
        self,
        command: CreateFriendLinkGroupCommand,
    ) -> object:
        assert command.name == "新友链分组"
        assert command.slug == "new-friends"
        return SimpleNamespace(
            id=2,
            name=command.name,
            slug=command.slug,
            sort_order=command.sort_order,
            created_at=datetime(2026, 6, 16, tzinfo=UTC),
        )

    async def update_friend_link_group(
        self,
        *,
        group_id: int,
        command: UpdateFriendLinkGroupCommand,
    ) -> object:
        assert group_id == 1
        assert command.name == "更新后的友链分组"
        return SimpleNamespace(
            id=1,
            name=command.name,
            slug=command.slug if isinstance(command.slug, str) else "friends",
            sort_order=command.sort_order if isinstance(command.sort_order, int) else 0,
            created_at=datetime(2026, 6, 16, tzinfo=UTC),
        )

    async def list_site_nav_groups(
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
                name="项目",
                slug="projects",
                description="个人项目入口",
                visibility="public",
                sort_order=0,
                created_at=datetime(2026, 6, 16, tzinfo=UTC),
            ),
        ]

    async def create_site_nav_group(
        self,
        command: CreateSiteNavGroupCommand,
    ) -> object:
        assert command.name == "新导航分组"
        assert command.slug == "new-sites"
        return SimpleNamespace(
            id=2,
            name=command.name,
            slug=command.slug,
            description=command.description,
            visibility=command.visibility,
            sort_order=command.sort_order,
            created_at=datetime(2026, 6, 16, tzinfo=UTC),
        )

    async def update_site_nav_group(
        self,
        *,
        group_id: int,
        command: UpdateSiteNavGroupCommand,
    ) -> object:
        assert group_id == 1
        assert command.name == "更新后的导航分组"
        return SimpleNamespace(
            id=1,
            name=command.name,
            slug=command.slug if isinstance(command.slug, str) else "projects",
            description=(
                command.description if isinstance(command.description, str) else None
            ),
            visibility=(
                command.visibility if isinstance(command.visibility, str) else "public"
            ),
            sort_order=command.sort_order if isinstance(command.sort_order, int) else 0,
            created_at=datetime(2026, 6, 16, tzinfo=UTC),
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
        scope: str,
        profile: EncryptionProfile,
        payload: dict[str, object],
        esid: str | None = None,
        esid_salt_id: str | None = None,
        response_salt_id: str | None = None,
    ) -> EncryptedApiResponse:
        assert session_id == "content-session"
        assert scope == "admin"
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
        esid_salt_id: str | None = None,
    ) -> None:
        assert session_id == "content-session"
        assert scope == "admin"
        assert profile == EncryptionProfile.CONTENT


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

__all__ = (
    "AuthenticatedUser",
    "CreateFriendLinkCommand",
    "CreateFriendLinkGroupCommand",
    "CreateSiteNavGroupCommand",
    "CreateSiteNavItemCommand",
    "EncryptedApiRequest",
    "EncryptedApiResponse",
    "EncryptionProfile",
    "FakeEncryptionSessionManager",
    "FakeLinkGroupService",
    "FakeLinkService",
    "FakeLogService",
    "SimpleNamespace",
    "TestClient",
    "UTC",
    "UpdateFriendLinkCommand",
    "UpdateFriendLinkGroupCommand",
    "UpdateSiteNavGroupCommand",
    "UpdateSiteNavItemCommand",
    "app",
    "datetime",
    "get_current_admin_user",
    "get_encryption_session_manager",
    "get_link_group_service",
    "get_link_service",
    "get_log_service",
    "override_admin_user",
)
