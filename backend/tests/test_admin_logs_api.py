from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.admin.dependencies import get_current_admin_user, get_log_service
from app.main import app
from app.services.auth import AuthenticatedUser


class FakeLogService:
    async def list_audit_logs(self, *, limit: int, offset: int) -> list[object]:
        return []

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

    async def list_security_events(self, *, limit: int, offset: int) -> list[object]:
        return []


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


def test_login_logs_return_items_for_audit_reader() -> None:
    client = TestClient(app)
    app.dependency_overrides[get_current_admin_user] = lambda: AuthenticatedUser(
        id=1,
        username="admin",
        display_name="管理员",
        roles=["super_admin"],
        permissions=["*"],
    )
    app.dependency_overrides[get_log_service] = lambda: FakeLogService()

    try:
        response = client.get("/api/admin/login-logs?limit=1")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
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
    }
