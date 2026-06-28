from datetime import UTC, datetime

from app.api.admin.dependencies import get_current_admin_user
from app.api.dependencies import (
    get_comment_service,
    get_encryption_session_manager,
    get_log_service,
)
from app.core.encryption import EncryptionProfile
from app.schemas.comments import AdminCommentItem
from app.schemas.encryption import EncryptedApiRequest, EncryptedApiResponse
from app.services.auth import AuthenticatedUser
from tests.public_content_api_helpers import TestClient, app


class FakeAdminEncryptionSessionManager:
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


class FakeAdminCommentService:
    async def list_admin_comments(
        self,
        *,
        status_filter: str,
        limit: int,
        offset: int,
    ) -> tuple[list[AdminCommentItem], int]:
        assert status_filter == "pending"
        assert limit == 50
        assert offset == 0
        return [admin_comment_item(status="pending")], 1

    async def review_comment(self, **kwargs: object) -> AdminCommentItem:
        assert kwargs["comment_id"] == 1
        assert kwargs["action"] in {"approve", "delete"}
        assert kwargs["reviewer_id"] == 1
        return admin_comment_item(
            status="deleted_by_admin"
            if kwargs["action"] == "delete"
            else "published",
        )


class FakeAdminLogService:
    def __init__(self) -> None:
        self.audit_items: list[dict[str, object]] = []

    async def record_audit_log(self, **kwargs: object) -> None:
        self.audit_items.append(dict(kwargs))


def test_admin_comments_list_uses_content_encryption_profile() -> None:
    client = TestClient(app)
    manager = FakeAdminEncryptionSessionManager()
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_comment_service] = lambda: FakeAdminCommentService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager

    try:
        response = client.get(
            "/api/admin/comments",
            headers={
                "X-Encryption-Session": "content-session",
                "X-Encryption-Response-Salt": "test-response-salt",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["profile"] == "content-v1"
    assert manager.payload is not None
    assert manager.payload["items"][0]["status"] == "pending"


def test_admin_comment_review_requires_csrf_and_records_safe_audit() -> None:
    client = TestClient(app)
    client.cookies.set("blog_admin_csrf", "csrf-token")
    logs = FakeAdminLogService()
    manager = FakeAdminEncryptionSessionManager(
        decrypted_payload={"action": "approve", "reason_class": "ok"},
    )
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_comment_service] = lambda: FakeAdminCommentService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.patch(
            "/api/admin/comments/1/review",
            headers={
                "X-CSRF-Token": "csrf-token",
                "X-Encryption-Session": "content-session",
                "X-Encryption-Response-Salt": "test-response-salt",
            },
            json={
                "session_id": "content-session",
                "profile": "content-v1",
                "salt_id": "test-request-salt",
                "nonce": "test-nonce",
                "ciphertext": "test-ciphertext",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert manager.request_payload is not None
    assert manager.payload is not None
    assert manager.payload["status"] == "published"
    assert logs.audit_items[0]["action"] == "comment.approve"
    assert logs.audit_items[0]["after_json"] == {
        "deleted": False,
        "reason_class": "ok",
        "review_status": "approve",
        "status": "published",
    }
    assert "正文内容" not in str(logs.audit_items[0])


def test_delete_admin_comment_requires_csrf_and_records_audit() -> None:
    client = TestClient(app)
    client.cookies.set("blog_admin_csrf", "csrf-token")
    logs = FakeAdminLogService()
    manager = FakeAdminEncryptionSessionManager()
    app.dependency_overrides[get_current_admin_user] = override_admin_user
    app.dependency_overrides[get_comment_service] = lambda: FakeAdminCommentService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.delete(
            "/api/admin/comments/1",
            headers={
                "X-CSRF-Token": "csrf-token",
                "X-Encryption-Session": "content-session",
                "X-Encryption-Response-Salt": "test-response-salt",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert manager.payload is not None
    assert manager.payload["status"] == "deleted_by_admin"
    assert logs.audit_items[0]["action"] == "comment.delete"
    assert logs.audit_items[0]["after_json"]["deleted"] is True


def override_admin_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        id=1,
        username="admin",
        display_name="管理员",
        roles=["super_admin"],
        permissions=["*"],
    )


def admin_comment_item(*, status: str) -> AdminCommentItem:
    return AdminCommentItem(
        id=1,
        post_id=1,
        post_title="公开文章",
        post_slug="public-post",
        parent_id=None,
        status=status,
        display_name="匿名读者 #A1B2C3",
        author_public_id="A1B2C3",
        body_text="正文内容",
        reply_count=0,
        risk_hash_prefix="abcdef12",
        created_at=datetime(2026, 6, 29, tzinfo=UTC),
        reviewed_at=None,
        reviewed_by=None,
        deleted_at=None,
        deleted_reason=None,
    )
