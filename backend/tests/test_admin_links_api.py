from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.admin.dependencies import (
    get_current_admin_user,
    get_encryption_session_manager,
    get_link_group_service,
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
)
from app.services.links import CreateFriendLinkCommand, CreateSiteNavItemCommand


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
        changes: dict[str, object],
    ) -> object:
        assert link_id == 1
        assert changes["name"] == "更新后的友链"
        return SimpleNamespace(
            id=1,
            group_id=1,
            group_name=None,
            name=changes["name"],
            url=changes.get("url", "https://blog.example.test"),
            avatar_url=None,
            description=changes.get("description"),
            rss_url=None,
            status=changes.get("status", "pending"),
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
        changes: dict[str, object],
    ) -> object:
        assert item_id == 1
        assert changes["title"] == "更新后的导航"
        return SimpleNamespace(
            id=1,
            group_id=1,
            group_name=None,
            group_slug=None,
            title=changes["title"],
            url=changes.get("url", "https://github.com/ChaceQC/blog"),
            icon_url=changes.get("icon_url"),
            description=changes.get("description"),
            tags_json=changes.get("tags_json"),
            open_target=changes.get("open_target", "blank"),
            visibility=changes.get("visibility", "public"),
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
        changes: dict[str, object],
    ) -> object:
        assert group_id == 1
        assert changes["name"] == "更新后的友链分组"
        return SimpleNamespace(
            id=1,
            name=changes["name"],
            slug=changes.get("slug", "friends"),
            sort_order=changes.get("sort_order", 0),
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
        changes: dict[str, object],
    ) -> object:
        assert group_id == 1
        assert changes["name"] == "更新后的导航分组"
        return SimpleNamespace(
            id=1,
            name=changes["name"],
            slug=changes.get("slug", "projects"),
            description=changes.get("description"),
            visibility=changes.get("visibility", "public"),
            sort_order=changes.get("sort_order", 0),
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
    ) -> EncryptedApiResponse:
        assert session_id == "content-session"
        assert scope == "admin"
        assert profile == EncryptionProfile.CONTENT
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
    ) -> dict[str, object]:
        assert session_id == "content-session"
        assert scope == "admin"
        assert profile == EncryptionProfile.CONTENT
        self.request_payload = payload
        return self.decrypted_payload


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


def test_admin_friend_link_groups_use_content_encryption_profile() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_link_group_service] = lambda: FakeLinkGroupService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager

    try:
        response = client.get(
            "/api/admin/friend-link-groups?limit=1",
            headers={"X-Encryption-Session": "content-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert manager.payload["items"][0]["slug"] == "friends"


def test_create_admin_friend_link_group_decrypts_content_request() -> None:
    client = TestClient(app)
    client.cookies.set("blog_admin_csrf", "csrf-token")
    logs = FakeLogService()
    manager = FakeEncryptionSessionManager(
        decrypted_payload={
            "name": "新友链分组",
            "slug": "new-friends",
            "sort_order": 0,
        },
    )
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_link_group_service] = lambda: FakeLinkGroupService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.post(
            "/api/admin/friend-link-groups",
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
    assert manager.payload["name"] == "新友链分组"
    assert logs.audit_items[0]["action"] == "friend_link_group.create"


def test_update_admin_friend_link_group_decrypts_content_request() -> None:
    client = TestClient(app)
    client.cookies.set("blog_admin_csrf", "csrf-token")
    logs = FakeLogService()
    manager = FakeEncryptionSessionManager(
        decrypted_payload={
            "name": "更新后的友链分组",
            "slug": "friends-updated",
            "sort_order": 1,
        },
    )
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_link_group_service] = lambda: FakeLinkGroupService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.patch(
            "/api/admin/friend-link-groups/1",
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
    assert manager.payload["name"] == "更新后的友链分组"
    assert logs.audit_items[0]["action"] == "friend_link_group.update"


def test_admin_site_nav_groups_use_content_encryption_profile() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_link_group_service] = lambda: FakeLinkGroupService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager

    try:
        response = client.get(
            "/api/admin/site-groups?limit=1",
            headers={"X-Encryption-Session": "content-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert manager.payload["items"][0]["slug"] == "projects"


def test_create_admin_site_nav_group_decrypts_content_request() -> None:
    client = TestClient(app)
    client.cookies.set("blog_admin_csrf", "csrf-token")
    logs = FakeLogService()
    manager = FakeEncryptionSessionManager(
        decrypted_payload={
            "name": "新导航分组",
            "slug": "new-sites",
            "description": "新的导航入口集合",
            "visibility": "public",
            "sort_order": 0,
        },
    )
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_link_group_service] = lambda: FakeLinkGroupService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.post(
            "/api/admin/site-groups",
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
    assert manager.payload["name"] == "新导航分组"
    assert logs.audit_items[0]["action"] == "site_nav_group.create"


def test_update_admin_site_nav_group_decrypts_content_request() -> None:
    client = TestClient(app)
    client.cookies.set("blog_admin_csrf", "csrf-token")
    logs = FakeLogService()
    manager = FakeEncryptionSessionManager(
        decrypted_payload={
            "name": "更新后的导航分组",
            "description": "更新后的入口集合",
            "visibility": "hidden",
        },
    )
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_link_group_service] = lambda: FakeLinkGroupService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.patch(
            "/api/admin/site-groups/1",
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
    assert manager.payload["name"] == "更新后的导航分组"
    assert logs.audit_items[0]["action"] == "site_nav_group.update"


def test_admin_friend_links_use_content_encryption_profile() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_link_service] = lambda: FakeLinkService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager

    try:
        response = client.get(
            "/api/admin/friend-links?limit=1",
            headers={"X-Encryption-Session": "content-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert manager.payload["items"][0]["name"] == "静默书房"


def test_review_admin_friend_link_decrypts_content_request() -> None:
    client = TestClient(app)
    client.cookies.set("blog_admin_csrf", "csrf-token")
    logs = FakeLogService()
    manager = FakeEncryptionSessionManager(decrypted_payload={"status": "healthy"})
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_link_service] = lambda: FakeLinkService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.patch(
            "/api/admin/friend-links/1/review",
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
    assert manager.payload["status"] == "healthy"
    assert logs.audit_items[0]["action"] == "friend_link.review"
    assert logs.audit_items[0]["entity_type"] == "friend_link"
    assert logs.audit_items[0]["after_json"]["review_status"] == "healthy"


def test_create_admin_friend_link_decrypts_content_request() -> None:
    client = TestClient(app)
    client.cookies.set("blog_admin_csrf", "csrf-token")
    logs = FakeLogService()
    manager = FakeEncryptionSessionManager(
        decrypted_payload={
            "name": "新友链",
            "url": "https://new-link.example.test",
            "description": "新的长期入口",
            "status": "pending",
            "sort_order": 0,
        },
    )
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_link_service] = lambda: FakeLinkService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.post(
            "/api/admin/friend-links",
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
    assert manager.payload["name"] == "新友链"
    assert logs.audit_items[0]["action"] == "friend_link.create"


def test_update_admin_friend_link_decrypts_content_request() -> None:
    client = TestClient(app)
    client.cookies.set("blog_admin_csrf", "csrf-token")
    logs = FakeLogService()
    manager = FakeEncryptionSessionManager(
        decrypted_payload={
            "name": "更新后的友链",
            "description": "更新后的描述",
            "status": "healthy",
        },
    )
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_link_service] = lambda: FakeLinkService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.patch(
            "/api/admin/friend-links/1",
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
    assert manager.payload["name"] == "更新后的友链"
    assert logs.audit_items[0]["action"] == "friend_link.update"


def test_admin_site_items_use_content_encryption_profile() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_link_service] = lambda: FakeLinkService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager

    try:
        response = client.get(
            "/api/admin/site-items?limit=1",
            headers={"X-Encryption-Session": "content-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert manager.payload["items"][0]["title"] == "博客源码"


def test_create_admin_site_item_decrypts_content_request() -> None:
    client = TestClient(app)
    client.cookies.set("blog_admin_csrf", "csrf-token")
    logs = FakeLogService()
    manager = FakeEncryptionSessionManager(
        decrypted_payload={
            "title": "新导航",
            "url": "https://nav.example.test",
            "icon_url": "https://nav.example.test/icon.svg",
            "description": "新的导航入口",
            "tags_json": {"items": [" 工具 ", "博客", "工具"]},
            "open_target": "self",
            "visibility": "public",
            "sort_order": 0,
        },
    )
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_link_service] = lambda: FakeLinkService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.post(
            "/api/admin/site-items",
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
    assert manager.payload["title"] == "新导航"
    assert manager.payload["icon_url"] == "https://nav.example.test/icon.svg"
    assert manager.payload["tags_json"] == {"items": ["工具", "博客"]}
    assert manager.payload["open_target"] == "self"
    assert logs.audit_items[0]["action"] == "site_nav.create"
    assert logs.audit_items[0]["after_json"]["tags_json"] == {
        "items": ["工具", "博客"],
    }


def test_update_admin_site_item_decrypts_content_request() -> None:
    client = TestClient(app)
    client.cookies.set("blog_admin_csrf", "csrf-token")
    logs = FakeLogService()
    manager = FakeEncryptionSessionManager(
        decrypted_payload={
            "title": "更新后的导航",
            "description": "更新后的导航描述",
            "tags_json": {"tags": ["项目", "Demo"]},
            "visibility": "hidden",
        },
    )
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_link_service] = lambda: FakeLinkService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.patch(
            "/api/admin/site-items/1",
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
    assert manager.payload["title"] == "更新后的导航"
    assert manager.payload["tags_json"] == {"items": ["项目", "Demo"]}
    assert logs.audit_items[0]["action"] == "site_nav.update"
    assert "tags_json" in logs.audit_items[0]["after_json"]["changed_fields"]


def test_create_admin_site_item_rejects_invalid_tags() -> None:
    client = TestClient(app)
    client.cookies.set("blog_admin_csrf", "csrf-token")
    manager = FakeEncryptionSessionManager(
        decrypted_payload={
            "title": "新导航",
            "url": "https://nav.example.test",
            "tags_json": {"items": ["x" * 25]},
            "open_target": "blank",
            "visibility": "public",
            "sort_order": 0,
        },
    )
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_link_service] = lambda: FakeLinkService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: FakeLogService()

    try:
        response = client.post(
            "/api/admin/site-items",
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

    assert response.status_code == 422
    assert response.json()["detail"] == "invalid encrypted request payload"
