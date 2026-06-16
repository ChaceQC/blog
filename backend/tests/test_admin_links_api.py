from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.admin.dependencies import (
    get_current_admin_user,
    get_encryption_session_manager,
    get_link_service,
)
from app.core.encryption import EncryptionProfile
from app.main import app
from app.schemas.encryption import EncryptedApiRequest, EncryptedApiResponse
from app.services.auth import AuthenticatedUser
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
            icon_url=None,
            description=changes.get("description"),
            tags_json=None,
            open_target=changes.get("open_target", "blank"),
            visibility=changes.get("visibility", "public"),
            click_count=0,
            sort_order=0,
            created_at=datetime(2026, 6, 16, tzinfo=UTC),
            updated_at=datetime(2026, 6, 16, tzinfo=UTC),
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
        profile: EncryptionProfile,
        payload: dict[str, object],
    ) -> EncryptedApiResponse:
        assert session_id == "content-session"
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
        profile: EncryptionProfile,
        payload: EncryptedApiRequest,
    ) -> dict[str, object]:
        assert session_id == "content-session"
        assert profile == EncryptionProfile.CONTENT
        self.request_payload = payload
        return self.decrypted_payload


def override_admin_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        id=1,
        username="admin",
        display_name="管理员",
        roles=["super_admin"],
        permissions=["*"],
    )


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
    manager = FakeEncryptionSessionManager(decrypted_payload={"status": "healthy"})
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_link_service] = lambda: FakeLinkService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager

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


def test_create_admin_friend_link_decrypts_content_request() -> None:
    client = TestClient(app)
    client.cookies.set("blog_admin_csrf", "csrf-token")
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


def test_update_admin_friend_link_decrypts_content_request() -> None:
    client = TestClient(app)
    client.cookies.set("blog_admin_csrf", "csrf-token")
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
    manager = FakeEncryptionSessionManager(
        decrypted_payload={
            "title": "新导航",
            "url": "https://nav.example.test",
            "description": "新的导航入口",
            "open_target": "blank",
            "visibility": "public",
            "sort_order": 0,
        },
    )
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_link_service] = lambda: FakeLinkService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager

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


def test_update_admin_site_item_decrypts_content_request() -> None:
    client = TestClient(app)
    client.cookies.set("blog_admin_csrf", "csrf-token")
    manager = FakeEncryptionSessionManager(
        decrypted_payload={
            "title": "更新后的导航",
            "description": "更新后的导航描述",
            "visibility": "hidden",
        },
    )
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_link_service] = lambda: FakeLinkService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager

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
