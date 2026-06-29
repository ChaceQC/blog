from collections.abc import Sequence
from datetime import timedelta

from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import utc_now
from app.models.content import Post, PostComment
from app.repositories.content_helpers import public_post_filters
from app.schemas.comments import (
    COMMENT_PUBLIC_OWNED_STATUSES,
    COMMENT_STATUS_DELETED_BY_ADMIN,
    COMMENT_STATUS_DELETED_BY_AUTHOR,
    COMMENT_STATUS_PUBLISHED,
)


class CommentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_public_post_by_slug(self, slug: str) -> Post | None:
        result = await self.session.execute(
            select(Post).where(Post.slug == slug, *public_post_filters(utc_now())),
        )
        return result.scalar_one_or_none()

    async def get_reply_target_with_root(
        self,
        *,
        post_id: int,
        comment_id: int,
    ) -> tuple[PostComment, PostComment] | None:
        target = await self.get_comment_for_reply(
            post_id=post_id,
            comment_id=comment_id,
        )
        if target is None:
            return None
        if target.parent_id is None:
            return target, target
        root = await self.get_public_thread_root(
            post_id=post_id,
            comment_id=target.parent_id,
        )
        if root is None:
            return None
        return target, root

    async def lock_post_for_comment_write(self, *, post_id: int) -> None:
        await self.session.execute(
            select(Post.id)
            .where(Post.id == post_id)
            .with_for_update(),
        )

    async def get_comment_for_reply(
        self,
        *,
        post_id: int,
        comment_id: int,
    ) -> PostComment | None:
        result = await self.session.execute(
            select(PostComment).where(
                PostComment.id == comment_id,
                PostComment.post_id == post_id,
                PostComment.status == "published",
            ),
        )
        return result.scalar_one_or_none()

    async def get_public_thread_root(
        self,
        *,
        post_id: int,
        comment_id: int,
    ) -> PostComment | None:
        result = await self.session.execute(
            select(PostComment).where(
                PostComment.id == comment_id,
                PostComment.post_id == post_id,
                PostComment.parent_id.is_(None),
                or_(
                    PostComment.status == COMMENT_STATUS_PUBLISHED,
                    and_(
                        PostComment.status.in_(
                            (
                                COMMENT_STATUS_DELETED_BY_AUTHOR,
                                COMMENT_STATUS_DELETED_BY_ADMIN,
                            ),
                        ),
                        PostComment.reply_count > 0,
                    ),
                ),
            ),
        )
        return result.scalar_one_or_none()

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
    ) -> PostComment:
        comment = PostComment(
            post_id=post_id,
            parent_id=parent_id,
            reply_to_id=reply_to_id,
            reply_to_display_name=reply_to_display_name,
            status=status,
            display_name=display_name,
            display_name_base=display_name_base,
            author_public_id=author_public_id,
            author_key_hash=author_key_hash,
            fingerprint_hash=fingerprint_hash,
            risk_hash=risk_hash,
            delete_token_hash=delete_token_hash,
            body_text=body_text,
            body_hash=body_hash,
        )
        self.session.add(comment)
        await self.session.flush()
        return comment

    async def get_author_display_name(
        self,
        *,
        post_id: int,
        author_key_hash: str,
        display_name_base: str,
    ) -> str | None:
        result = await self.session.execute(
            select(PostComment.display_name)
            .where(
                PostComment.post_id == post_id,
                PostComment.author_key_hash == author_key_hash,
                PostComment.display_name_base == display_name_base,
                PostComment.display_name.is_not(None),
            )
            .order_by(PostComment.created_at.asc(), PostComment.id.asc())
            .limit(1),
        )
        return result.scalar_one_or_none()

    async def display_name_exists_for_other_author(
        self,
        *,
        post_id: int,
        author_key_hash: str,
        display_name: str,
    ) -> bool:
        result = await self.session.execute(
            select(func.count(PostComment.id)).where(
                PostComment.post_id == post_id,
                func.lower(PostComment.display_name) == display_name.casefold(),
                PostComment.author_key_hash != author_key_hash,
            ),
        )
        return int(result.scalar_one()) > 0

    async def get_comment_for_update(
        self,
        *,
        post_id: int,
        comment_id: int,
    ) -> PostComment | None:
        result = await self.session.execute(
            select(PostComment)
            .where(
                PostComment.id == comment_id,
                PostComment.post_id == post_id,
            )
            .with_for_update(),
        )
        return result.scalar_one_or_none()

    async def list_public_comments(
        self,
        *,
        post_id: int,
        limit: int,
        offset: int,
    ) -> Sequence[PostComment]:
        root_result = await self.session.execute(
            select(PostComment.id)
            .where(
                PostComment.post_id == post_id,
                PostComment.parent_id.is_(None),
                _public_list_filter(),
            )
            .order_by(PostComment.created_at.asc(), PostComment.id.asc())
            .limit(limit)
            .offset(offset),
        )
        root_ids = list(root_result.scalars().all())
        if not root_ids:
            return []
        root_id_expr = case(
            (PostComment.parent_id.is_(None), PostComment.id),
            else_=PostComment.parent_id,
        )
        root_order = case(
            {root_id: index for index, root_id in enumerate(root_ids)},
            value=root_id_expr,
            else_=len(root_ids),
        )
        result = await self.session.execute(
            select(PostComment)
            .where(
                PostComment.post_id == post_id,
                _public_list_filter(),
                or_(
                    PostComment.id.in_(root_ids),
                    PostComment.parent_id.in_(root_ids),
                ),
            )
            .order_by(
                root_order,
                PostComment.parent_id.is_not(None),
                PostComment.created_at.asc(),
                PostComment.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def count_public_comments(self, *, post_id: int) -> int:
        result = await self.session.execute(
            select(func.count(PostComment.id)).where(
                PostComment.post_id == post_id,
                PostComment.status == COMMENT_STATUS_PUBLISHED,
            ),
        )
        return int(result.scalar_one())

    async def count_public_comment_threads(self, *, post_id: int) -> int:
        result = await self.session.execute(
            select(func.count(PostComment.id)).where(
                PostComment.post_id == post_id,
                PostComment.parent_id.is_(None),
                _public_list_filter(),
            ),
        )
        return int(result.scalar_one())

    async def list_owned_comments(
        self,
        *,
        post_id: int,
        comment_ids: Sequence[int],
    ) -> Sequence[PostComment]:
        if not comment_ids:
            return []
        result = await self.session.execute(
            select(PostComment)
            .where(
                PostComment.post_id == post_id,
                PostComment.id.in_(comment_ids),
                PostComment.status.in_(COMMENT_PUBLIC_OWNED_STATUSES),
            )
            .order_by(PostComment.created_at.asc(), PostComment.id.asc()),
        )
        return list(result.scalars().all())

    async def count_recent_duplicate_body(
        self,
        *,
        post_id: int,
        body_hash: str,
        window_seconds: int,
    ) -> int:
        if window_seconds <= 0:
            return 0
        since = utc_now() - timedelta(seconds=window_seconds)
        result = await self.session.execute(
            select(func.count(PostComment.id)).where(
                PostComment.post_id == post_id,
                PostComment.body_hash == body_hash,
                PostComment.created_at >= since,
                PostComment.status.in_(("pending", "published")),
            ),
        )
        return int(result.scalar_one())

    async def count_recent_comments_by_author(
        self,
        *,
        author_key_hash: str,
        window_seconds: int,
    ) -> int:
        if window_seconds <= 0:
            return 0
        since = utc_now() - timedelta(seconds=window_seconds)
        result = await self.session.execute(
            select(func.count(PostComment.id)).where(
                PostComment.author_key_hash == author_key_hash,
                PostComment.created_at >= since,
                PostComment.status.in_(("pending", "published")),
            ),
        )
        return int(result.scalar_one())

    async def count_recent_comments_by_risk(
        self,
        *,
        risk_hash: str,
        window_seconds: int,
    ) -> int:
        if window_seconds <= 0:
            return 0
        since = utc_now() - timedelta(seconds=window_seconds)
        result = await self.session.execute(
            select(func.count(PostComment.id)).where(
                PostComment.risk_hash == risk_hash,
                PostComment.created_at >= since,
                PostComment.status.in_(("pending", "published")),
            ),
        )
        return int(result.scalar_one())

    async def count_pending_comments(self) -> int:
        result = await self.session.execute(
            select(func.count(PostComment.id)).where(
                PostComment.status == "pending",
            ),
        )
        return int(result.scalar_one())

    async def list_admin_comments(
        self,
        *,
        status_filter: str,
        limit: int,
        offset: int,
    ) -> Sequence[tuple[PostComment, str, str]]:
        statement = (
            select(PostComment, Post.title, Post.slug)
            .join(Post, Post.id == PostComment.post_id)
            .order_by(PostComment.created_at.desc(), PostComment.id.desc())
            .limit(limit)
            .offset(offset)
        )
        if status_filter != "all":
            statement = statement.where(PostComment.status == status_filter)
        result = await self.session.execute(statement)
        return list(result.all())

    async def get_admin_comment_for_update(
        self,
        *,
        comment_id: int,
    ) -> tuple[PostComment, str, str] | None:
        result = await self.session.execute(
            select(PostComment, Post.title, Post.slug)
            .join(Post, Post.id == PostComment.post_id)
            .where(PostComment.id == comment_id)
            .with_for_update(),
        )
        row = result.one_or_none()
        if row is None:
            return None
        comment, title, slug = row
        return comment, str(title), str(slug)

    async def count_admin_comments(self, *, status_filter: str) -> int:
        statement = select(func.count(PostComment.id))
        if status_filter != "all":
            statement = statement.where(PostComment.status == status_filter)
        result = await self.session.execute(statement)
        return int(result.scalar_one())

    async def increment_post_comment_count(self, *, post_id: int) -> None:
        await self.session.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(comment_count=Post.comment_count + 1),
        )

    async def decrement_post_comment_count(self, *, post_id: int) -> None:
        await self.session.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(
                comment_count=case(
                    (Post.comment_count > 0, Post.comment_count - 1),
                    else_=0,
                ),
            ),
        )

    async def increment_parent_reply_count(self, *, parent_id: int) -> None:
        await self.session.execute(
            update(PostComment)
            .where(PostComment.id == parent_id)
            .values(reply_count=PostComment.reply_count + 1),
        )

    async def decrement_parent_reply_count(self, *, parent_id: int) -> None:
        await self.session.execute(
            update(PostComment)
            .where(PostComment.id == parent_id)
            .values(
                reply_count=case(
                    (PostComment.reply_count > 0, PostComment.reply_count - 1),
                    else_=0,
                ),
            ),
        )

    async def commit(self) -> None:
        await self.session.commit()

    async def refresh(self, instance: object) -> None:
        await self.session.refresh(instance)

    async def flush(self) -> None:
        await self.session.flush()


def _public_list_filter():
    return or_(
        PostComment.status == COMMENT_STATUS_PUBLISHED,
        and_(
            PostComment.status.in_(
                (COMMENT_STATUS_DELETED_BY_AUTHOR, COMMENT_STATUS_DELETED_BY_ADMIN),
            ),
            PostComment.reply_count > 0,
        ),
    )
