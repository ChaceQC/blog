from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.schemas.comments import PublicCommentCreateRequest, PublicOwnedCommentReceipt
from app.schemas.content import VisitorFingerprint
from app.services.comment_identity import CommentIdentityService
from app.services.comments import (
    CommentDuplicateError,
    CommentRiskLimitedError,
    CommentService,
    CommentTokenInvalidError,
)


class FakeCommentRepository:
    def __init__(self) -> None:
        self.post = SimpleNamespace(
            id=1,
            slug="public-post",
            allow_comment=True,
        )
        self.comments: list[SimpleNamespace] = []
        self.next_id = 1
        self.comment_count = 0
        self.commits = 0

    async def get_public_post_by_slug(self, slug: str) -> object | None:
        return self.post if slug == self.post.slug else None

    async def get_reply_target_with_root(self, *, post_id: int, comment_id: int):
        target = self._comment_by_id(post_id=post_id, comment_id=comment_id)
        if target is None or target.status != "published":
            return None
        if target.parent_id is None:
            return target, target
        root = self._comment_by_id(post_id=post_id, comment_id=target.parent_id)
        if (
            root is None
            or root.parent_id is not None
            or root.status not in {"published", "deleted_by_author", "deleted_by_admin"}
        ):
            return None
        return target, root

    def _comment_by_id(self, *, post_id: int, comment_id: int):
        for comment in self.comments:
            if (
                comment.id == comment_id
                and comment.post_id == post_id
            ):
                return comment
        return None

    async def create_comment(self, **kwargs: object):
        values = dict(kwargs)
        values.setdefault("reply_to_id", None)
        values.setdefault("reply_to_display_name", None)
        values.setdefault("display_name_base", None)
        comment = SimpleNamespace(
            id=self.next_id,
            created_at=datetime(2026, 6, 29, tzinfo=UTC),
            updated_at=datetime(2026, 6, 29, tzinfo=UTC),
            reply_count=0,
            reviewed_at=None,
            reviewed_by=None,
            deleted_at=None,
            deleted_reason=None,
            **values,
        )
        self.next_id += 1
        self.comments.append(comment)
        return comment

    async def get_comment_for_update(self, *, post_id: int, comment_id: int):
        for comment in self.comments:
            if comment.id == comment_id and comment.post_id == post_id:
                return comment
        return None

    async def list_public_comments(self, *, post_id: int, limit: int, offset: int):
        items = [
            comment
            for comment in self.comments
            if comment.post_id == post_id
            and (
                comment.status == "published"
                or (
                    comment.status in {"deleted_by_author", "deleted_by_admin"}
                    and comment.reply_count > 0
                )
            )
        ]
        return items[offset : offset + limit]

    async def count_public_comments(self, *, post_id: int) -> int:
        return len(
            [
                comment
                for comment in self.comments
                if comment.post_id == post_id and comment.status == "published"
            ],
        )

    async def list_owned_comments(self, *, post_id: int, comment_ids: list[int]):
        return [
            comment
            for comment in self.comments
            if comment.post_id == post_id and comment.id in comment_ids
        ]

    async def count_recent_duplicate_body(
        self,
        *,
        post_id: int,
        body_hash: str,
        window_seconds: int,
    ) -> int:
        return len(
            [
                comment
                for comment in self.comments
                if (
                    comment.post_id == post_id
                    and comment.body_hash == body_hash
                    and comment.status in {"pending", "published"}
                )
            ],
        )

    async def count_pending_comments(self) -> int:
        return len(
            [comment for comment in self.comments if comment.status == "pending"],
        )

    async def count_recent_comments_by_author(
        self,
        *,
        author_key_hash: str,
        window_seconds: int,
    ) -> int:
        return len(
            [
                comment
                for comment in self.comments
                if comment.author_key_hash == author_key_hash
                and comment.status in {"pending", "published"}
            ],
        )

    async def count_recent_comments_by_risk(
        self,
        *,
        risk_hash: str,
        window_seconds: int,
    ) -> int:
        return len(
            [
                comment
                for comment in self.comments
                if comment.risk_hash == risk_hash
                and comment.status in {"pending", "published"}
            ],
        )

    async def list_admin_comments(self, *, status_filter: str, limit: int, offset: int):
        rows = [(comment, "公开文章", "public-post") for comment in self.comments]
        if status_filter != "all":
            rows = [row for row in rows if row[0].status == status_filter]
        return rows[offset : offset + limit]

    async def get_admin_comment_for_update(self, *, comment_id: int):
        for comment in self.comments:
            if comment.id == comment_id:
                return comment, "公开文章", "public-post"
        return None

    async def count_admin_comments(self, *, status_filter: str) -> int:
        rows = await self.list_admin_comments(
            status_filter=status_filter,
            limit=100,
            offset=0,
        )
        return len(rows)

    async def increment_post_comment_count(self, *, post_id: int) -> None:
        self.comment_count += 1

    async def decrement_post_comment_count(self, *, post_id: int) -> None:
        self.comment_count = max(0, self.comment_count - 1)

    async def increment_parent_reply_count(self, *, parent_id: int) -> None:
        for comment in self.comments:
            if comment.id == parent_id:
                comment.reply_count += 1

    async def decrement_parent_reply_count(self, *, parent_id: int) -> None:
        for comment in self.comments:
            if comment.id == parent_id:
                comment.reply_count = max(0, comment.reply_count - 1)

    async def get_author_display_name(
        self,
        *,
        post_id: int,
        author_key_hash: str,
        display_name_base: str,
    ) -> str | None:
        for comment in self.comments:
            if (
                comment.post_id == post_id
                and comment.author_key_hash == author_key_hash
                and comment.display_name_base == display_name_base
                and comment.display_name is not None
            ):
                return comment.display_name
        return None

    async def display_name_exists_for_other_author(
        self,
        *,
        post_id: int,
        author_key_hash: str,
        display_name: str,
    ) -> bool:
        return any(
            comment.post_id == post_id
            and comment.author_key_hash != author_key_hash
            and comment.display_name is not None
            and comment.display_name.casefold() == display_name.casefold()
            for comment in self.comments
        )

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, instance: object) -> None:
        return None


class FakeTelemetry:
    environment = "test"
    version = "1.0.0"

    def __init__(self) -> None:
        self.metrics: list[dict[str, object]] = []

    def record_metric(self, **kwargs: object) -> None:
        self.metrics.append(dict(kwargs))


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_create_comment_returns_pending_item_and_one_time_delete_token() -> None:
    repository = FakeCommentRepository()
    service = create_service(repository)

    created = await service.create_public_comment(
        slug="public-post",
        payload=create_payload(body_text="<script>alert(1)</script>\n纯文本"),
        client_ip="203.0.113.8",
        user_agent="pytest-browser",
        accept_language="zh-CN",
    )

    assert created.comment.status == "pending"
    assert created.comment.body_text == "<script>alert(1)</script>\n纯文本"
    assert created.comment.display_name.startswith("匿名读者 #")
    assert len(created.delete_token) >= 32
    stored = repository.comments[0]
    assert stored.delete_token_hash != created.delete_token
    assert stored.body_text == "<script>alert(1)</script>\n纯文本"
    assert repository.comment_count == 0


@pytest.mark.anyio
async def test_owned_comments_return_pending_comment_for_matching_receipt() -> None:
    repository = FakeCommentRepository()
    service = create_service(repository)
    created = await service.create_public_comment(
        slug="public-post",
        payload=create_payload(),
        client_ip="203.0.113.8",
        user_agent="pytest-browser",
        accept_language="zh-CN",
    )

    items = await service.list_owned_comments(
        slug="public-post",
        receipts=[
            PublicOwnedCommentReceipt(
                comment_id=created.comment.id,
                post_slug="public-post",
                delete_token=created.delete_token,
            ),
        ],
    )

    assert len(items) == 1
    assert items[0].id == created.comment.id
    assert items[0].status == "pending"


@pytest.mark.anyio
async def test_delete_with_token_clears_body_and_token_hash() -> None:
    repository = FakeCommentRepository()
    service = create_service(repository, auto_publish=True)
    created = await service.create_public_comment(
        slug="public-post",
        payload=create_payload(body_text="可以删除"),
        client_ip="203.0.113.8",
        user_agent="pytest-browser",
        accept_language="zh-CN",
    )

    deleted = await service.delete_public_comment(
        slug="public-post",
        comment_id=created.comment.id,
        delete_token=created.delete_token,
    )

    stored = repository.comments[0]
    assert deleted.status == "deleted_by_author"
    assert deleted.body_text == "评论已删除"
    assert stored.body_text == ""
    assert stored.display_name_base is None
    assert stored.delete_token_hash is None
    assert repository.comment_count == 0


@pytest.mark.anyio
async def test_reply_to_reply_stays_in_root_thread_with_target_snapshot() -> None:
    repository = FakeCommentRepository()
    service = create_service(repository, auto_publish=True)
    root = await service.create_public_comment(
        slug="public-post",
        payload=create_payload(body_text="根评论", display_name="楼主"),
        client_ip="203.0.113.8",
        user_agent="pytest-browser",
        accept_language="zh-CN",
    )
    reply = await service.create_public_comment(
        slug="public-post",
        payload=create_payload(
            body_text="第一条回复",
            display_name="甲",
            parent_id=root.comment.id,
            author_secret_proof="b" * 64,
        ),
        client_ip="203.0.113.8",
        user_agent="pytest-browser",
        accept_language="zh-CN",
    )

    nested = await service.create_public_comment(
        slug="public-post",
        payload=create_payload(
            body_text="回复回复",
            display_name="乙",
            parent_id=reply.comment.id,
            author_secret_proof="c" * 64,
        ),
        client_ip="203.0.113.8",
        user_agent="pytest-browser",
        accept_language="zh-CN",
    )

    stored = repository.comments[-1]
    assert nested.comment.parent_id == root.comment.id
    assert nested.comment.reply_to_id == reply.comment.id
    assert nested.comment.reply_to_display_name == "甲"
    assert stored.parent_id == root.comment.id
    assert stored.reply_to_id == reply.comment.id
    assert repository.comments[0].reply_count == 2
    assert repository.comments[1].reply_count == 1


@pytest.mark.anyio
async def test_deleting_one_reply_keeps_other_replies_from_same_author() -> None:
    repository = FakeCommentRepository()
    service = create_service(repository, auto_publish=True)
    root = await service.create_public_comment(
        slug="public-post",
        payload=create_payload(body_text="根评论"),
        client_ip="203.0.113.8",
        user_agent="pytest-browser",
        accept_language="zh-CN",
    )
    first_reply = await service.create_public_comment(
        slug="public-post",
        payload=create_payload(
            body_text="同一作者回复一",
            display_name="同名",
            parent_id=root.comment.id,
            author_secret_proof="d" * 64,
        ),
        client_ip="203.0.113.8",
        user_agent="pytest-browser",
        accept_language="zh-CN",
    )
    second_reply = await service.create_public_comment(
        slug="public-post",
        payload=create_payload(
            body_text="同一作者回复二",
            display_name="同名",
            parent_id=root.comment.id,
            author_secret_proof="d" * 64,
        ),
        client_ip="203.0.113.8",
        user_agent="pytest-browser",
        accept_language="zh-CN",
    )

    await service.delete_public_comment(
        slug="public-post",
        comment_id=first_reply.comment.id,
        delete_token=first_reply.delete_token,
    )
    comments, _ = await service.list_public_comments(
        slug="public-post",
        limit=20,
        offset=0,
    )

    assert [comment.id for comment in comments] == [
        root.comment.id,
        second_reply.comment.id,
    ]
    assert comments[1].body_text == "同一作者回复二"
    assert repository.comments[0].reply_count == 1


@pytest.mark.anyio
async def test_deleted_reply_target_keeps_snapshot_for_later_replies() -> None:
    repository = FakeCommentRepository()
    service = create_service(repository, auto_publish=True)
    root = await service.create_public_comment(
        slug="public-post",
        payload=create_payload(body_text="根评论"),
        client_ip="203.0.113.8",
        user_agent="pytest-browser",
        accept_language="zh-CN",
    )
    target = await service.create_public_comment(
        slug="public-post",
        payload=create_payload(
            body_text="会被删除的回复",
            display_name="被回复的人",
            parent_id=root.comment.id,
            author_secret_proof="e" * 64,
        ),
        client_ip="203.0.113.8",
        user_agent="pytest-browser",
        accept_language="zh-CN",
    )
    later_reply = await service.create_public_comment(
        slug="public-post",
        payload=create_payload(
            body_text="先回复它",
            display_name="后来的回复",
            parent_id=target.comment.id,
            author_secret_proof="f" * 64,
        ),
        client_ip="203.0.113.8",
        user_agent="pytest-browser",
        accept_language="zh-CN",
    )

    await service.delete_public_comment(
        slug="public-post",
        comment_id=target.comment.id,
        delete_token=target.delete_token,
    )
    comments, _ = await service.list_public_comments(
        slug="public-post",
        limit=20,
        offset=0,
    )

    deleted_target = next(
        comment for comment in comments if comment.id == target.comment.id
    )
    visible_later_reply = next(
        comment for comment in comments if comment.id == later_reply.comment.id
    )
    assert deleted_target.body_text == "评论已删除"
    assert deleted_target.reply_count == 1
    assert visible_later_reply.reply_to_id == target.comment.id
    assert visible_later_reply.reply_to_display_name == "被回复的人"


@pytest.mark.anyio
async def test_duplicate_display_name_suffix_only_for_other_authors() -> None:
    repository = FakeCommentRepository()
    service = create_service(repository, auto_publish=True)
    first = await service.create_public_comment(
        slug="public-post",
        payload=create_payload(display_name="访客", author_secret_proof="a" * 64),
        client_ip="203.0.113.8",
        user_agent="pytest-browser",
        accept_language="zh-CN",
    )
    same_author = await service.create_public_comment(
        slug="public-post",
        payload=create_payload(
            body_text="同一作者继续评论",
            display_name="访客",
            author_secret_proof="a" * 64,
        ),
        client_ip="203.0.113.8",
        user_agent="pytest-browser",
        accept_language="zh-CN",
    )
    other_author = await service.create_public_comment(
        slug="public-post",
        payload=create_payload(
            body_text="另一个作者",
            display_name="访客",
            author_secret_proof="b" * 64,
        ),
        client_ip="203.0.113.8",
        user_agent="pytest-browser",
        accept_language="zh-CN",
    )
    same_other_author = await service.create_public_comment(
        slug="public-post",
        payload=create_payload(
            body_text="另一个作者继续评论",
            display_name="访客",
            author_secret_proof="b" * 64,
        ),
        client_ip="203.0.113.8",
        user_agent="pytest-browser",
        accept_language="zh-CN",
    )

    assert first.comment.display_name == "访客"
    assert same_author.comment.display_name == "访客"
    assert other_author.comment.display_name.startswith("访客#")
    assert 4 <= len(other_author.comment.display_name.removeprefix("访客#")) <= 8
    assert same_other_author.comment.display_name == other_author.comment.display_name


@pytest.mark.anyio
async def test_delete_rejects_wrong_token() -> None:
    repository = FakeCommentRepository()
    service = create_service(repository)
    created = await service.create_public_comment(
        slug="public-post",
        payload=create_payload(),
        client_ip="203.0.113.8",
        user_agent="pytest-browser",
        accept_language="zh-CN",
    )

    with pytest.raises(CommentTokenInvalidError):
        await service.delete_public_comment(
            slug="public-post",
            comment_id=created.comment.id,
            delete_token="wrong-token-value-with-enough-length-123456",
        )


@pytest.mark.anyio
async def test_duplicate_body_in_window_is_rejected() -> None:
    repository = FakeCommentRepository()
    service = create_service(repository)
    payload = create_payload(body_text="重复正文")
    await service.create_public_comment(
        slug="public-post",
        payload=payload,
        client_ip="203.0.113.8",
        user_agent="pytest-browser",
        accept_language="zh-CN",
    )

    with pytest.raises(CommentDuplicateError):
        await service.create_public_comment(
            slug="public-post",
            payload=payload,
            client_ip="203.0.113.8",
            user_agent="pytest-browser",
            accept_language="zh-CN",
        )


@pytest.mark.anyio
async def test_risk_bucket_limit_rejects_excessive_comments() -> None:
    repository = FakeCommentRepository()
    service = CommentService(
        repository=repository,
        identity=CommentIdentityService(
            secret_key="test-secret-key-with-at-least-32-chars",
        ),
        pending_limit=500,
        duplicate_window_seconds=0,
        risk_limit_max_attempts=1,
        risk_limit_window_seconds=600,
        author_limit_max_attempts=100,
        author_limit_window_seconds=3600,
    )
    await service.create_public_comment(
        slug="public-post",
        payload=create_payload(body_text="第一条"),
        client_ip="203.0.113.8",
        user_agent="pytest-browser",
        accept_language="zh-CN",
    )

    with pytest.raises(CommentRiskLimitedError):
        await service.create_public_comment(
            slug="public-post",
            payload=create_payload(body_text="第二条"),
            client_ip="203.0.113.8",
            user_agent="pytest-browser",
            accept_language="zh-CN",
        )


def create_service(
    repository: FakeCommentRepository,
    *,
    auto_publish: bool = False,
) -> CommentService:
    return CommentService(
        repository=repository,
        identity=CommentIdentityService(
            secret_key="test-secret-key-with-at-least-32-chars",
        ),
        pending_limit=500,
        duplicate_window_seconds=600,
        risk_limit_max_attempts=100,
        risk_limit_window_seconds=600,
        author_limit_max_attempts=100,
        author_limit_window_seconds=3600,
        auto_publish=auto_publish,
        telemetry=FakeTelemetry(),
    )


def create_payload(
    *,
    body_text: str = "这是一条评论",
    display_name: str | None = None,
    parent_id: int | None = None,
    author_secret_proof: str = "a" * 64,
) -> PublicCommentCreateRequest:
    return PublicCommentCreateRequest(
        parent_id=parent_id,
        display_name=display_name,
        body_text=body_text,
        author_secret_proof=author_secret_proof,
        fingerprint=VisitorFingerprint(
            version="web-v1",
            visitor_id="local-visitor-id-0123456789",
            browser_hash="a" * 64,
            device_hash="b" * 64,
            composite_hash="c" * 64,
            timezone="Asia/Shanghai",
            language="zh-CN",
            platform="Win32",
            screen="1536x864x24",
            created_at_ms=1782460800000,
        ),
    )
