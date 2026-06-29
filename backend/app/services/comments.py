from collections.abc import Sequence
from dataclasses import dataclass
from secrets import choice
from string import ascii_letters, digits
from typing import Protocol

from app.core.auth import utc_now
from app.models.content import Post, PostComment
from app.schemas.comments import (
    COMMENT_STATUS_DELETED_BY_ADMIN,
    COMMENT_STATUS_DELETED_BY_AUTHOR,
    COMMENT_STATUS_PENDING,
    COMMENT_STATUS_PUBLISHED,
    COMMENT_STATUS_REJECTED,
    COMMENT_STATUS_SPAM,
    AdminCommentItem,
    PublicCommentCreateRequest,
    PublicCommentItem,
    PublicOwnedCommentReceipt,
)
from app.services.comment_identity import CommentIdentityService


class CommentNotFoundError(Exception):
    pass


class CommentClosedError(Exception):
    pass


class CommentParentInvalidError(Exception):
    pass


class CommentDuplicateError(Exception):
    pass


class CommentQueueFullError(Exception):
    pass


class CommentRiskLimitedError(Exception):
    pass


class CommentTokenInvalidError(Exception):
    pass


class CommentStateConflictError(Exception):
    pass


class CommentRepositoryProtocol(Protocol):
    async def get_public_post_by_slug(self, slug: str) -> Post | None: ...

    async def get_reply_target_with_root(
        self,
        *,
        post_id: int,
        comment_id: int,
    ) -> tuple[PostComment, PostComment] | None: ...

    async def create_comment(
        self,
        *,
        post_id: int,
        parent_id: int | None,
        reply_to_id: int | None,
        reply_to_display_name: str | None,
        status: str,
        display_name: str | None,
        display_name_base: str | None,
        author_public_id: str,
        author_key_hash: str,
        fingerprint_hash: str,
        risk_hash: str,
        delete_token_hash: str,
        body_text: str,
        body_hash: str,
    ) -> PostComment: ...

    async def get_author_display_name(
        self,
        *,
        post_id: int,
        author_key_hash: str,
        display_name_base: str,
    ) -> str | None: ...

    async def display_name_exists_for_other_author(
        self,
        *,
        post_id: int,
        author_key_hash: str,
        display_name: str,
    ) -> bool: ...

    async def get_comment_for_update(
        self,
        *,
        post_id: int,
        comment_id: int,
    ) -> PostComment | None: ...

    async def list_public_comments(
        self,
        *,
        post_id: int,
        limit: int,
        offset: int,
    ) -> Sequence[PostComment]: ...

    async def count_public_comments(self, *, post_id: int) -> int: ...

    async def list_owned_comments(
        self,
        *,
        post_id: int,
        comment_ids: Sequence[int],
    ) -> Sequence[PostComment]: ...

    async def count_recent_duplicate_body(
        self,
        *,
        post_id: int,
        body_hash: str,
        window_seconds: int,
    ) -> int: ...

    async def count_pending_comments(self) -> int: ...

    async def count_recent_comments_by_author(
        self,
        *,
        author_key_hash: str,
        window_seconds: int,
    ) -> int: ...

    async def count_recent_comments_by_risk(
        self,
        *,
        risk_hash: str,
        window_seconds: int,
    ) -> int: ...

    async def list_admin_comments(
        self,
        *,
        status_filter: str,
        limit: int,
        offset: int,
    ) -> Sequence[tuple[PostComment, str, str]]: ...

    async def get_admin_comment_for_update(
        self,
        *,
        comment_id: int,
    ) -> tuple[PostComment, str, str] | None: ...

    async def count_admin_comments(self, *, status_filter: str) -> int: ...

    async def increment_post_comment_count(self, *, post_id: int) -> None: ...

    async def decrement_post_comment_count(self, *, post_id: int) -> None: ...

    async def increment_parent_reply_count(self, *, parent_id: int) -> None: ...

    async def decrement_parent_reply_count(self, *, parent_id: int) -> None: ...

    async def commit(self) -> None: ...

    async def refresh(self, instance: object) -> None: ...


@dataclass(frozen=True)
class CreatedComment:
    comment: PublicCommentItem
    delete_token: str


class CommentService:
    def __init__(
        self,
        *,
        repository: CommentRepositoryProtocol,
        identity: CommentIdentityService,
        pending_limit: int,
        duplicate_window_seconds: int,
        risk_limit_max_attempts: int,
        risk_limit_window_seconds: int,
        author_limit_max_attempts: int,
        author_limit_window_seconds: int,
        auto_publish: bool = False,
        telemetry: object | None = None,
    ) -> None:
        self.repository = repository
        self.identity = identity
        self._pending_limit = pending_limit
        self._duplicate_window_seconds = duplicate_window_seconds
        self._risk_limit_max_attempts = risk_limit_max_attempts
        self._risk_limit_window_seconds = risk_limit_window_seconds
        self._author_limit_max_attempts = author_limit_max_attempts
        self._author_limit_window_seconds = author_limit_window_seconds
        self._auto_publish = auto_publish
        self._telemetry = telemetry

    async def list_public_comments(
        self,
        *,
        slug: str,
        limit: int,
        offset: int,
    ) -> tuple[list[PublicCommentItem], int]:
        post = await self._require_public_post(slug)
        comments = await self.repository.list_public_comments(
            post_id=post.id,
            limit=limit,
            offset=offset,
        )
        total = await self.repository.count_public_comments(post_id=post.id)
        return [public_comment_item(comment) for comment in comments], total

    async def create_public_comment(
        self,
        *,
        slug: str,
        payload: PublicCommentCreateRequest,
        client_ip: str | None,
        user_agent: str | None,
        accept_language: str | None,
    ) -> CreatedComment:
        post = await self._require_public_post(slug)
        if not post.allow_comment:
            self._record_create_telemetry(
                outcome="closed",
                status=COMMENT_STATUS_PENDING,
                entity_id=post.id,
            )
            raise CommentClosedError("comments are closed")
        if (
            not self._auto_publish
            and self._pending_limit > 0
            and await self.repository.count_pending_comments() >= self._pending_limit
        ):
            self._record_create_telemetry(
                outcome="queue_full",
                status=COMMENT_STATUS_PENDING,
                entity_id=post.id,
            )
            raise CommentQueueFullError("comment review queue is full")

        reply_target = None
        root_parent = None
        if payload.parent_id is not None:
            reply_row = await self.repository.get_reply_target_with_root(
                post_id=post.id,
                comment_id=payload.parent_id,
            )
            if reply_row is None:
                raise CommentParentInvalidError("invalid comment parent")
            reply_target, root_parent = reply_row

        identity = self.identity.identity(
            post_id=post.id,
            author_secret_proof=payload.author_secret_proof,
            fingerprint=payload.fingerprint,
            client_ip=client_ip,
            user_agent=user_agent,
            accept_language=accept_language,
        )
        body_hash = self.identity.body_hash(payload.body_text)
        if await self.repository.count_recent_comments_by_risk(
            risk_hash=identity.risk_hash,
            window_seconds=self._risk_limit_window_seconds,
        ) >= self._risk_limit_max_attempts:
            self._record_create_telemetry(
                outcome="risk_limited",
                status=COMMENT_STATUS_PENDING,
                entity_id=post.id,
            )
            raise CommentRiskLimitedError("comment risk limited")
        if await self.repository.count_recent_comments_by_author(
            author_key_hash=identity.author_key_hash,
            window_seconds=self._author_limit_window_seconds,
        ) >= self._author_limit_max_attempts:
            self._record_create_telemetry(
                outcome="author_limited",
                status=COMMENT_STATUS_PENDING,
                entity_id=post.id,
            )
            raise CommentRiskLimitedError("comment author limited")
        if await self.repository.count_recent_duplicate_body(
            post_id=post.id,
            body_hash=body_hash,
            window_seconds=self._duplicate_window_seconds,
        ):
            self._record_create_telemetry(
                outcome="duplicate",
                status=COMMENT_STATUS_PENDING,
                entity_id=post.id,
            )
            raise CommentDuplicateError("duplicate comment")

        delete_token = self.identity.create_delete_token()
        status = (
            COMMENT_STATUS_PUBLISHED
            if self._auto_publish
            else COMMENT_STATUS_PENDING
        )
        display_name = await self._display_name_for_author(
            post_id=post.id,
            author_key_hash=identity.author_key_hash,
            display_name=payload.display_name,
        )
        comment = await self.repository.create_comment(
            post_id=post.id,
            parent_id=root_parent.id if root_parent is not None else None,
            reply_to_id=reply_target.id if reply_target is not None else None,
            reply_to_display_name=(
                public_comment_item(reply_target).display_name
                if reply_target is not None
                else None
            ),
            status=status,
            display_name=display_name,
            display_name_base=payload.display_name,
            author_public_id=identity.author_public_id,
            author_key_hash=identity.author_key_hash,
            fingerprint_hash=identity.fingerprint_hash,
            risk_hash=identity.risk_hash,
            delete_token_hash=self.identity.delete_token_hash(delete_token),
            body_text=payload.body_text,
            body_hash=body_hash,
        )
        if status == COMMENT_STATUS_PUBLISHED:
            await self.repository.increment_post_comment_count(post_id=post.id)
            if root_parent is not None:
                await self._increment_reply_counts(
                    root_parent_id=root_parent.id,
                    reply_to_id=reply_target.id if reply_target is not None else None,
                )
        await self.repository.commit()
        await self.repository.refresh(comment)
        self._record_create_telemetry(
            outcome="created",
            status=comment.status,
            entity_id=post.id,
        )
        return CreatedComment(
            comment=public_comment_item(comment),
            delete_token=delete_token,
        )

    async def list_owned_comments(
        self,
        *,
        slug: str,
        receipts: Sequence[PublicOwnedCommentReceipt],
    ) -> list[PublicCommentItem]:
        post = await self._require_public_post(slug)
        token_by_id: dict[int, str] = {}
        for receipt in receipts:
            if receipt.post_slug is not None and receipt.post_slug != slug:
                continue
            token_by_id[receipt.comment_id] = receipt.delete_token
        comments = await self.repository.list_owned_comments(
            post_id=post.id,
            comment_ids=list(token_by_id),
        )
        verified = [
            comment
            for comment in comments
            if self.identity.verify_delete_token(
                stored_hash=comment.delete_token_hash,
                delete_token=token_by_id.get(comment.id, ""),
            )
        ]
        return [public_comment_item(comment) for comment in verified]

    async def delete_public_comment(
        self,
        *,
        slug: str,
        comment_id: int,
        delete_token: str,
    ) -> PublicCommentItem:
        post = await self._require_public_post(slug)
        comment = await self.repository.get_comment_for_update(
            post_id=post.id,
            comment_id=comment_id,
        )
        if comment is None:
            raise CommentNotFoundError("comment not found")
        if comment.status not in {COMMENT_STATUS_PENDING, COMMENT_STATUS_PUBLISHED}:
            raise CommentStateConflictError("comment cannot be deleted")
        if not self.identity.verify_delete_token(
            stored_hash=comment.delete_token_hash,
            delete_token=delete_token,
        ):
            self._record_delete_telemetry(
                scope="public",
                outcome="invalid_token",
                entity_id=post.id,
            )
            raise CommentTokenInvalidError("invalid delete token")

        was_published = comment.status == COMMENT_STATUS_PUBLISHED
        _mark_comment_deleted(
            comment,
            status=COMMENT_STATUS_DELETED_BY_AUTHOR,
            reason="author_deleted",
        )
        if was_published:
            await self.repository.decrement_post_comment_count(post_id=post.id)
            await self._decrement_reply_counts(comment)
        await self.repository.commit()
        await self.repository.refresh(comment)
        self._record_delete_telemetry(
            scope="public",
            outcome="deleted",
            entity_id=post.id,
        )
        return public_comment_item(comment)

    async def list_admin_comments(
        self,
        *,
        status_filter: str,
        limit: int,
        offset: int,
    ) -> tuple[list[AdminCommentItem], int]:
        rows = await self.repository.list_admin_comments(
            status_filter=status_filter,
            limit=limit,
            offset=offset,
        )
        total = await self.repository.count_admin_comments(status_filter=status_filter)
        return [admin_comment_item(*row) for row in rows], total

    async def review_comment(
        self,
        *,
        comment_id: int,
        action: str,
        reviewer_id: int,
        reason_class: str | None,
    ) -> AdminCommentItem:
        row = await self._admin_comment_row(comment_id)
        comment, post_title, post_slug = row
        previous_status = comment.status
        if action == "approve":
            if comment.status != COMMENT_STATUS_PENDING:
                raise CommentStateConflictError("comment is not pending")
            comment.status = COMMENT_STATUS_PUBLISHED
            comment.reviewed_at = utc_now()
            comment.reviewed_by = reviewer_id
            await self.repository.increment_post_comment_count(post_id=comment.post_id)
            if comment.parent_id is not None:
                await self._increment_reply_counts(
                    root_parent_id=comment.parent_id,
                    reply_to_id=comment.reply_to_id,
                )
        elif action in {"reject", "spam"}:
            if comment.status not in {COMMENT_STATUS_PENDING, COMMENT_STATUS_PUBLISHED}:
                raise CommentStateConflictError("comment cannot be reviewed")
            if comment.status == COMMENT_STATUS_PUBLISHED:
                await self.repository.decrement_post_comment_count(
                    post_id=comment.post_id,
                )
                await self._decrement_reply_counts(comment)
            comment.status = (
                COMMENT_STATUS_REJECTED if action == "reject" else COMMENT_STATUS_SPAM
            )
            comment.reviewed_at = utc_now()
            comment.reviewed_by = reviewer_id
            comment.deleted_reason = reason_class
        elif action == "delete":
            if comment.status in {
                COMMENT_STATUS_DELETED_BY_AUTHOR,
                COMMENT_STATUS_DELETED_BY_ADMIN,
            }:
                raise CommentStateConflictError("comment is already deleted")
            if comment.status == COMMENT_STATUS_PUBLISHED:
                await self.repository.decrement_post_comment_count(
                    post_id=comment.post_id,
                )
                await self._decrement_reply_counts(comment)
            _mark_comment_deleted(
                comment,
                status=COMMENT_STATUS_DELETED_BY_ADMIN,
                reason=reason_class or "admin_deleted",
            )
            comment.reviewed_at = utc_now()
            comment.reviewed_by = reviewer_id
        else:
            raise CommentStateConflictError("invalid review action")
        await self.repository.commit()
        await self.repository.refresh(comment)
        self._record_review_telemetry(
            action=action,
            previous_status=previous_status,
            status=comment.status,
            entity_id=comment.post_id,
        )
        if action == "delete":
            self._record_delete_telemetry(
                scope="admin",
                outcome="deleted",
                entity_id=comment.post_id,
            )
        return admin_comment_item(comment, post_title, post_slug)

    async def _admin_comment_row(
        self,
        comment_id: int,
    ) -> tuple[PostComment, str, str]:
        row = await self.repository.get_admin_comment_for_update(
            comment_id=comment_id,
        )
        if row is None:
            raise CommentNotFoundError("comment not found")
        return row

    async def _require_public_post(self, slug: str) -> Post:
        post = await self.repository.get_public_post_by_slug(slug)
        if post is None:
            raise CommentNotFoundError("post not found")
        return post

    async def _display_name_for_author(
        self,
        *,
        post_id: int,
        author_key_hash: str,
        display_name: str | None,
    ) -> str | None:
        if display_name is None:
            return None
        existing = await self.repository.get_author_display_name(
            post_id=post_id,
            author_key_hash=author_key_hash,
            display_name_base=display_name,
        )
        if existing is not None:
            return existing
        if not await self.repository.display_name_exists_for_other_author(
            post_id=post_id,
            author_key_hash=author_key_hash,
            display_name=display_name,
        ):
            return display_name
        for suffix_length in (4, 5, 6, 7, 8):
            for _ in range(4):
                suffix = _random_suffix(suffix_length)
                candidate = _append_display_name_suffix(display_name, suffix)
                if not await self.repository.display_name_exists_for_other_author(
                    post_id=post_id,
                    author_key_hash=author_key_hash,
                    display_name=candidate,
                ):
                    return candidate
        suffix = _random_suffix(8)
        return _append_display_name_suffix(display_name, suffix)

    async def _increment_reply_counts(
        self,
        *,
        root_parent_id: int,
        reply_to_id: int | None,
    ) -> None:
        await self.repository.increment_parent_reply_count(parent_id=root_parent_id)
        if reply_to_id is not None and reply_to_id != root_parent_id:
            await self.repository.increment_parent_reply_count(parent_id=reply_to_id)

    async def _decrement_reply_counts(self, comment: PostComment) -> None:
        if comment.parent_id is None:
            return
        await self.repository.decrement_parent_reply_count(parent_id=comment.parent_id)
        if comment.reply_to_id is not None and comment.reply_to_id != comment.parent_id:
            await self.repository.decrement_parent_reply_count(
                parent_id=comment.reply_to_id,
            )

    def _record_create_telemetry(
        self,
        *,
        outcome: str,
        status: str,
        entity_id: int | None,
    ) -> None:
        if self._telemetry is None:
            return
        from app.api.telemetry import record_comment_create_telemetry

        record_comment_create_telemetry(
            self._telemetry,
            outcome=outcome,
            status=status,
            entity_id=entity_id,
        )

    def _record_review_telemetry(
        self,
        *,
        action: str,
        previous_status: str,
        status: str,
        entity_id: int | None,
    ) -> None:
        if self._telemetry is None:
            return
        from app.api.telemetry import record_comment_review_telemetry

        record_comment_review_telemetry(
            self._telemetry,
            action=action,
            previous_status=previous_status,
            status=status,
            entity_id=entity_id,
        )

    def _record_delete_telemetry(
        self,
        *,
        scope: str,
        outcome: str,
        entity_id: int | None,
    ) -> None:
        if self._telemetry is None:
            return
        from app.api.telemetry import record_comment_delete_telemetry

        record_comment_delete_telemetry(
            self._telemetry,
            scope=scope,
            outcome=outcome,
            entity_id=entity_id,
        )


def public_comment_item(comment: PostComment) -> PublicCommentItem:
    deleted = comment.status in {
        COMMENT_STATUS_DELETED_BY_AUTHOR,
        COMMENT_STATUS_DELETED_BY_ADMIN,
    }
    display_name = comment.display_name or f"匿名读者 #{comment.author_public_id}"
    return PublicCommentItem(
        id=comment.id,
        parent_id=comment.parent_id,
        reply_to_id=comment.reply_to_id,
        reply_to_display_name=comment.reply_to_display_name,
        status=comment.status,
        display_name="匿名读者" if deleted else display_name,
        author_public_id=comment.author_public_id,
        body_text="评论已删除" if deleted else comment.body_text,
        reply_count=comment.reply_count,
        created_at=comment.created_at,
    )


def admin_comment_item(
    comment: PostComment,
    post_title: str,
    post_slug: str,
) -> AdminCommentItem:
    public_item = public_comment_item(comment)
    return AdminCommentItem(
        id=comment.id,
        post_id=comment.post_id,
        post_title=post_title,
        post_slug=post_slug,
        parent_id=comment.parent_id,
        reply_to_id=comment.reply_to_id,
        reply_to_display_name=public_item.reply_to_display_name,
        status=comment.status,
        display_name=public_item.display_name,
        author_public_id=comment.author_public_id,
        body_text=public_item.body_text,
        reply_count=comment.reply_count,
        risk_hash_prefix=comment.risk_hash[:8],
        created_at=comment.created_at,
        reviewed_at=comment.reviewed_at,
        reviewed_by=comment.reviewed_by,
        deleted_at=comment.deleted_at,
        deleted_reason=comment.deleted_reason,
    )


def _mark_comment_deleted(
    comment: PostComment,
    *,
    status: str,
    reason: str,
) -> None:
    comment.status = status
    comment.body_text = ""
    comment.display_name = None
    comment.display_name_base = None
    comment.delete_token_hash = None
    comment.deleted_at = utc_now()
    comment.deleted_reason = reason


def _random_suffix(length: int) -> str:
    alphabet = ascii_letters + digits
    return "".join(choice(alphabet) for _ in range(length))


def _append_display_name_suffix(display_name: str, suffix: str) -> str:
    marker = f"#{suffix}"
    base_length = 32 - len(marker)
    return f"{display_name[:base_length]}{marker}"
