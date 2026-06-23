from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.admin.dependencies import get_current_admin_user
from app.api.dependencies import get_encryption_session_manager, get_log_service
from app.core.encryption import EncryptionProfile
from app.main import app
from app.schemas.encryption import EncryptedApiResponse
from app.services.auth import AuthenticatedUser


class FakeLogService:
    async def list_audit_logs(self, *, limit: int, offset: int) -> list[object]:
        assert limit == 1
        assert offset == 0
        return [
            SimpleNamespace(
                id=1,
                actor_id=1,
                action="post.publish",
                entity_type="post",
                entity_id=2,
                before_json=None,
                after_json={"status": "published"},
                ip="127.0.0.1",
                user_agent="pytest",
                created_at=datetime(2026, 6, 16, tzinfo=UTC),
            ),
        ]

    async def count_audit_logs(self) -> int:
        return 23

    async def list_access_logs(self, *, limit: int, offset: int) -> list[object]:
        assert limit == 1
        assert offset == 0
        return [
            SimpleNamespace(
                id=1,
                access_type="post_image_render",
                method="GET",
                path="/api/public/posts/public-post/files/1/render",
                status_code=200,
                entity_type="file",
                entity_id=1,
                ip="127.0.0.1",
                user_agent="pytest",
                detail_json=None,
                created_at=datetime(2026, 6, 16, tzinfo=UTC),
            ),
        ]

    async def count_access_logs(self) -> int:
        return 17

    async def list_login_logs(self, *, limit: int, offset: int) -> list[object]:
        assert limit == 1
        assert offset == 0
        return [
            SimpleNamespace(
                id=1,
                user_id=1,
                username="admin",
                success=False,
                ip="127.0.0.1",
                user_agent="pytest",
                reason="invalid_credentials",
                created_at=datetime(2026, 6, 16, tzinfo=UTC),
            ),
        ]

    async def count_login_logs(self) -> int:
        return 11

    async def list_security_events(self, *, limit: int, offset: int) -> list[object]:
        return []

    async def count_security_events(self) -> int:
        return 0


class FakeEncryptionSessionManager:
    def __init__(self) -> None:
        self.payload: dict[str, object] | None = None

    async def encrypt_response(
        self,
        *,
        session_id: str,
        scope: str,
        profile: EncryptionProfile,
        payload: dict[str, object],
        esid: str | None = None,
    ) -> EncryptedApiResponse:
        assert session_id == "sensitive-session"
        assert scope == "admin"
        assert profile == EncryptionProfile.SENSITIVE
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
        esid: str | None = None,
    ) -> None:
        assert session_id == "sensitive-session"
        assert scope == "admin"
        assert profile == EncryptionProfile.SENSITIVE


def test_login_logs_require_admin_permission() -> None:
    client = TestClient(app)
    app.dependency_overrides[get_current_admin_user] = lambda: AuthenticatedUser(
        id=1,
        username="viewer",
        display_name="访客",
        roles=["viewer"],
        permissions=["post:read"],
    )
    app.dependency_overrides[get_log_service] = lambda: FakeLogService()

    try:
        response = client.get("/api/admin/login-logs")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_admin_logs_reject_oversized_offset() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    app.dependency_overrides[get_current_admin_user] = lambda: AuthenticatedUser(
        id=1,
        username="admin",
        display_name="管理员",
        roles=["super_admin"],
        permissions=["*"],
    )
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager

    try:
        response = client.get(
            "/api/admin/login-logs?offset=10001",
            headers={"X-Encryption-Session": "sensitive-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_login_logs_return_items_for_audit_reader() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    app.dependency_overrides[get_current_admin_user] = lambda: AuthenticatedUser(
        id=1,
        username="admin",
        display_name="管理员",
        roles=["super_admin"],
        permissions=["*"],
    )
    app.dependency_overrides[get_log_service] = lambda: FakeLogService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager

    try:
        response = client.get(
            "/api/admin/login-logs?limit=1",
            headers={"X-Encryption-Session": "sensitive-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "sensitive-v1"
    assert manager.payload == {
        "items": [
            {
                "id": 1,
                "user_id": 1,
                "username": "admin",
                "success": False,
                "ip": "127.0.0.1",
                "user_agent": "pytest",
                "reason": "invalid_credentials",
                "created_at": "2026-06-16T00:00:00Z",
            },
        ],
        "total": 11,
    }


def test_audit_logs_return_items_for_audit_reader() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    app.dependency_overrides[get_current_admin_user] = lambda: AuthenticatedUser(
        id=1,
        username="admin",
        display_name="管理员",
        roles=["super_admin"],
        permissions=["*"],
    )
    app.dependency_overrides[get_log_service] = lambda: FakeLogService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager

    try:
        response = client.get(
            "/api/admin/audit-logs?limit=1",
            headers={"X-Encryption-Session": "sensitive-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "sensitive-v1"
    assert manager.payload == {
        "items": [
            {
                "id": 1,
                "actor_id": 1,
                "action": "post.publish",
                "entity_type": "post",
                "entity_id": 2,
                "before_json": None,
                "after_json": {"status": "published"},
                "ip": "127.0.0.1",
                "user_agent": "pytest",
                "created_at": "2026-06-16T00:00:00Z",
            },
        ],
        "total": 23,
    }


def test_access_logs_return_detail_for_audit_reader() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    app.dependency_overrides[get_current_admin_user] = lambda: AuthenticatedUser(
        id=1,
        username="admin",
        display_name="管理员",
        roles=["super_admin"],
        permissions=["*"],
    )
    app.dependency_overrides[get_log_service] = lambda: FakeLogService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager

    try:
        response = client.get(
            "/api/admin/access-logs?limit=1",
            headers={"X-Encryption-Session": "sensitive-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "sensitive-v1"
    assert manager.payload == {
        "items": [
            {
                "id": 1,
                "access_type": "post_image_render",
                "method": "GET",
                "path": "/api/public/posts/public-post/files/1/render",
                "status_code": 200,
                "entity_type": "file",
                "entity_id": 1,
                "ip": "127.0.0.1",
                "user_agent": "pytest",
                "detail_json": None,
                "created_at": "2026-06-16T00:00:00Z",
            },
        ],
        "total": 17,
    }
