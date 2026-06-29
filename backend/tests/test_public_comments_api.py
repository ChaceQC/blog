from datetime import UTC, datetime

from app.api.dependencies import (
    get_comment_service,
    get_encryption_session_manager,
    get_log_service,
)
from app.schemas.comments import PublicCommentItem
from app.services.comments import CommentNotFoundError, CreatedComment
from tests.public_content_api_helpers import (
    FakeEncryptionSessionManager,
    FakeLogService,
    TestClient,
    app,
)


class FakeCommentService:
    def __init__(self) -> None:
        self.created_payloads: list[dict[str, object]] = []
        self.owned_receipts: list[object] = []
        self.deleted_tokens: list[str] = []

    async def list_public_comments(
        self,
        *,
        slug: str,
        limit: int,
        offset: int,
    ) -> tuple[list[PublicCommentItem], int]:
        assert slug == "public-post"
        assert limit == 50
        assert offset == 0
        return [
            comment_item(
                comment_id=1,
                status="published",
                body_text="公开评论",
            ),
        ], 1

    async def create_public_comment(self, **kwargs: object) -> CreatedComment:
        self.created_payloads.append(dict(kwargs))
        return CreatedComment(
            comment=comment_item(
                comment_id=2,
                status="pending",
                body_text="<script>alert(1)</script>",
            ),
            delete_token="delete-token-value-with-enough-length-123456",
        )

    async def list_owned_comments(
        self,
        *,
        slug: str,
        receipts: list[object],
    ) -> list[PublicCommentItem]:
        assert slug == "public-post"
        self.owned_receipts.extend(receipts)
        return [
            comment_item(
                comment_id=2,
                status="pending",
                body_text="待审核评论",
            ),
        ]

    async def delete_public_comment(
        self,
        *,
        slug: str,
        comment_id: int,
        delete_token: str,
    ) -> PublicCommentItem:
        assert slug == "public-post"
        assert comment_id == 2
        self.deleted_tokens.append(delete_token)
        return comment_item(
            comment_id=2,
            status="deleted_by_author",
            body_text="评论已删除",
        )


class MissingCommentService(FakeCommentService):
    async def list_public_comments(self, **_: object):
        raise CommentNotFoundError("post not found")


def test_public_comments_list_returns_encrypted_comments() -> None:
    client = TestClient(app)
    manager = FakeEncryptionSessionManager()
    logs = FakeLogService()
    app.dependency_overrides[get_comment_service] = lambda: FakeCommentService()
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.get(
            "/api/public/posts/public-post/comments",
            headers={
                "X-Encryption-Session": "public-session",
                "X-Encryption-Response-Salt": "test-response-salt",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert manager.payload is not None
    assert manager.payload["total"] == 1
    assert manager.payload["items"][0]["body_text"] == "公开评论"
    assert logs.items[0]["access_type"] == "public_comments_list"


def test_public_comments_validate_session_before_query() -> None:
    client = TestClient(app)
    app.dependency_overrides[get_comment_service] = lambda: MissingCommentService()
    app.dependency_overrides[get_encryption_session_manager] = (
        lambda: FakeEncryptionSessionManager()
    )
    app.dependency_overrides[get_log_service] = lambda: FakeLogService()

    try:
        response = client.get("/api/public/posts/public-post/comments")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "missing encryption session"


def test_public_comment_create_decrypts_payload_and_returns_pending_receipt() -> None:
    client = TestClient(app)
    service = FakeCommentService()
    logs = FakeLogService()
    manager = FakeEncryptionSessionManager(
        {
            **fingerprint_payload(),
            "display_name": None,
            "body_text": "<script>alert(1)</script>",
            "author_secret_proof": "a" * 64,
        },
    )
    app.dependency_overrides[get_comment_service] = lambda: service
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.post(
            "/api/public/posts/public-post/comments",
            json=encrypted_body(),
            headers={
                "X-Encryption-Session": "public-session",
                "X-Encryption-Response-Salt": "test-response-salt",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert manager.request_payload is not None
    assert manager.payload is not None
    assert manager.payload["comment"]["status"] == "pending"
    assert manager.payload["comment"]["body_text"] == "<script>alert(1)</script>"
    assert manager.payload["delete_token"].startswith("delete-token")
    assert service.created_payloads[0]["slug"] == "public-post"
    assert logs.items[0]["access_type"] == "public_comment_create"
    assert "delete-token" not in str(logs.items[0])
    assert "<script>" not in str(logs.items[0])


def test_public_owned_comments_return_pending_items_for_receipts() -> None:
    client = TestClient(app)
    service = FakeCommentService()
    manager = FakeEncryptionSessionManager(
        {
            "receipts": [
                {
                    "comment_id": 2,
                    "post_slug": "public-post",
                    "delete_token": "delete-token-value-with-enough-length-123456",
                },
            ],
        },
    )
    app.dependency_overrides[get_comment_service] = lambda: service
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: FakeLogService()

    try:
        response = client.post(
            "/api/public/posts/public-post/comments/owned",
            json=encrypted_body(),
            headers={
                "X-Encryption-Session": "public-session",
                "X-Encryption-Response-Salt": "test-response-salt",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert manager.payload is not None
    assert manager.payload["items"][0]["status"] == "pending"
    assert len(service.owned_receipts) == 1


def test_public_comment_delete_token_stays_in_encrypted_body_not_url_or_logs() -> None:
    client = TestClient(app)
    service = FakeCommentService()
    logs = FakeLogService()
    manager = FakeEncryptionSessionManager(
        {
            "delete_token": "delete-token-value-with-enough-length-123456",
        },
    )
    app.dependency_overrides[get_comment_service] = lambda: service
    app.dependency_overrides[get_encryption_session_manager] = lambda: manager
    app.dependency_overrides[get_log_service] = lambda: logs

    try:
        response = client.post(
            "/api/public/posts/public-post/comments/2/delete",
            json=encrypted_body(),
            headers={
                "X-Encryption-Session": "public-session",
                "X-Encryption-Response-Salt": "test-response-salt",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert manager.payload == {"id": 2, "status": "deleted_by_author"}
    assert service.deleted_tokens == ["delete-token-value-with-enough-length-123456"]
    assert "delete-token" not in logs.items[0]["path"]
    assert "delete-token" not in str(logs.items[0])


def encrypted_body() -> dict[str, str]:
    return {
        "session_id": "public-session",
        "profile": "content-v1",
        "salt_id": "request-salt",
        "nonce": "nonce",
        "ciphertext": "ciphertext",
    }


def fingerprint_payload() -> dict[str, object]:
    return {
        "fingerprint": {
            "version": "web-v1",
            "visitor_id": "local-visitor-id-0123456789",
            "browser_hash": "a" * 64,
            "device_hash": "b" * 64,
            "composite_hash": "c" * 64,
            "timezone": "Asia/Shanghai",
            "language": "zh-CN",
            "platform": "Win32",
            "screen": "1536x864x24",
            "created_at_ms": 1782460800000,
        },
    }


def comment_item(
    *,
    comment_id: int,
    status: str,
    body_text: str,
) -> PublicCommentItem:
    return PublicCommentItem(
        id=comment_id,
        parent_id=None,
        reply_to_id=None,
        reply_to_display_name=None,
        status=status,
        display_name="匿名读者 #A1B2C3",
        author_public_id="A1B2C3",
        body_text=body_text,
        reply_count=0,
        created_at=datetime(2026, 6, 29, tzinfo=UTC),
    )
