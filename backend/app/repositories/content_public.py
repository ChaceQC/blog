from collections.abc import Sequence

from sqlalchemy import func, select

from app.core.auth import utc_now
from app.models.content import Category, Page, Post, PostCategory, PostTag, Tag
from app.repositories.content_helpers import public_post_filters


class ContentPublicQueryMixin:
    async def list_public_posts(
        self,
        *,
        limit: int,
        offset: int,
        category_slug: str | None = None,
        tag_slug: str | None = None,
    ) -> Sequence[Post]:
        statement = _public_post_statement(
            category_slug=category_slug,
            tag_slug=tag_slug,
        )
        result = await self.session.execute(
            statement
            .order_by(Post.published_at.desc(), Post.id.desc())
            .limit(limit)
            .offset(offset),
        )
        posts = list(result.scalars().all())
        await self._attach_post_taxonomy(posts)
        return posts

    async def count_public_posts(
        self,
        *,
        category_slug: str | None = None,
        tag_slug: str | None = None,
    ) -> int:
        statement = _public_post_statement(
            category_slug=category_slug,
            tag_slug=tag_slug,
            count=True,
        )
        result = await self.session.execute(statement)
        return int(result.scalar_one())

    async def list_public_feed_posts(self, *, limit: int) -> Sequence[Post]:
        result = await self.session.execute(
            select(Post)
            .where(*public_post_filters(utc_now()))
            .order_by(Post.published_at.desc(), Post.id.desc())
            .limit(limit),
        )
        posts = list(result.scalars().all())
        await self._attach_post_taxonomy(posts)
        return posts

    async def list_public_categories(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[dict[str, object]]:
        result = await self.session.execute(
            _public_category_statement()
            .order_by(Category.sort_order, Category.name)
            .limit(limit)
            .offset(offset),
        )
        return [dict(row) for row in result.mappings().all()]

    async def get_public_category_by_slug(
        self,
        slug: str,
    ) -> dict[str, object] | None:
        result = await self.session.execute(
            _public_category_statement()
            .where(Category.slug == slug)
            .group_by(Category.id, Category.name, Category.slug),
        )
        row = result.mappings().one_or_none()
        return dict(row) if row is not None else None

    async def list_public_tags(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[dict[str, object]]:
        result = await self.session.execute(
            _public_tag_statement()
            .order_by(Tag.name)
            .limit(limit)
            .offset(offset),
        )
        return [dict(row) for row in result.mappings().all()]

    async def get_public_tag_by_slug(self, slug: str) -> dict[str, object] | None:
        result = await self.session.execute(
            _public_tag_statement()
            .where(Tag.slug == slug)
            .group_by(Tag.id, Tag.name, Tag.slug),
        )
        row = result.mappings().one_or_none()
        return dict(row) if row is not None else None

    async def get_public_post_by_slug(self, slug: str) -> Post | None:
        result = await self.session.execute(
            select(Post).where(Post.slug == slug, *public_post_filters(utc_now())),
        )
        post = result.scalar_one_or_none()
        await self._attach_post_taxonomy([post] if post is not None else [])
        return post

    async def get_public_post_counts_by_slug(
        self,
        slug: str,
    ) -> tuple[int, int, int] | None:
        result = await self.session.execute(
            select(Post.id, Post.view_count, Post.like_count).where(
                Post.slug == slug,
                *public_post_filters(utc_now()),
            ),
        )
        row = result.one_or_none()
        if row is None:
            return None
        return int(row.id), int(row.view_count), int(row.like_count)

    async def get_public_page_by_slug(self, slug: str) -> Page | None:
        result = await self.session.execute(
            select(Page).where(
                Page.slug == slug,
                Page.deleted_at.is_(None),
                Page.status == "published",
            ),
        )
        return result.scalar_one_or_none()


def _public_post_statement(
    *,
    category_slug: str | None,
    tag_slug: str | None,
    count: bool = False,
):
    selectable = func.count(Post.id) if count else Post
    statement = select(selectable).where(*public_post_filters(utc_now()))
    if category_slug is not None:
        statement = (
            statement.join(PostCategory, PostCategory.post_id == Post.id)
            .join(Category, Category.id == PostCategory.category_id)
            .where(Category.slug == category_slug)
        )
    if tag_slug is not None:
        statement = (
            statement.join(PostTag, PostTag.post_id == Post.id)
            .join(Tag, Tag.id == PostTag.tag_id)
            .where(Tag.slug == tag_slug)
        )
    return statement


def _public_category_statement():
    return (
        select(
            Category.id,
            Category.name,
            Category.slug,
            func.count(Post.id).label("post_count"),
        )
        .join(PostCategory, PostCategory.category_id == Category.id)
        .join(Post, Post.id == PostCategory.post_id)
        .where(*public_post_filters(utc_now()))
        .group_by(Category.id, Category.name, Category.slug, Category.sort_order)
    )


def _public_tag_statement():
    return (
        select(
            Tag.id,
            Tag.name,
            Tag.slug,
            func.count(Post.id).label("post_count"),
        )
        .join(PostTag, PostTag.tag_id == Tag.id)
        .join(Post, Post.id == PostTag.post_id)
        .where(*public_post_filters(utc_now()))
        .group_by(Tag.id, Tag.name, Tag.slug)
    )
