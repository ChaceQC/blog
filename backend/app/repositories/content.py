import re
from collections.abc import Sequence
from hashlib import sha1

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import utc_now
from app.models.content import Category, Page, Post, PostCategory, PostTag, Tag
from app.models.file import BlogFile, FileUsage


class ContentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_posts(self, *, limit: int, offset: int) -> Sequence[Post]:
        result = await self.session.execute(
            select(Post)
            .where(Post.deleted_at.is_(None))
            .order_by(Post.updated_at.desc(), Post.id.desc())
            .limit(limit)
            .offset(offset),
        )
        posts = list(result.scalars().all())
        await self._attach_post_taxonomy(posts)
        return posts

    async def list_public_posts(self, *, limit: int, offset: int) -> Sequence[Post]:
        now = utc_now()
        result = await self.session.execute(
            select(Post)
            .where(
                *_public_post_filters(now),
            )
            .order_by(Post.published_at.desc(), Post.id.desc())
            .limit(limit)
            .offset(offset),
        )
        posts = list(result.scalars().all())
        await self._attach_post_taxonomy(posts)
        return posts

    async def list_public_feed_posts(self, *, limit: int) -> Sequence[Post]:
        now = utc_now()
        result = await self.session.execute(
            select(Post)
            .where(
                *_public_post_filters(now),
            )
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
        now = utc_now()
        result = await self.session.execute(
            select(
                Category.id,
                Category.name,
                Category.slug,
                func.count(Post.id).label("post_count"),
            )
            .join(PostCategory, PostCategory.category_id == Category.id)
            .join(Post, Post.id == PostCategory.post_id)
            .where(*_public_post_filters(now))
            .group_by(Category.id, Category.name, Category.slug, Category.sort_order)
            .order_by(Category.sort_order, Category.name)
            .limit(limit)
            .offset(offset),
        )
        return [dict(row) for row in result.mappings().all()]

    async def list_public_tags(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[dict[str, object]]:
        now = utc_now()
        result = await self.session.execute(
            select(
                Tag.id,
                Tag.name,
                Tag.slug,
                func.count(Post.id).label("post_count"),
            )
            .join(PostTag, PostTag.tag_id == Tag.id)
            .join(Post, Post.id == PostTag.post_id)
            .where(*_public_post_filters(now))
            .group_by(Tag.id, Tag.name, Tag.slug)
            .order_by(Tag.name)
            .limit(limit)
            .offset(offset),
        )
        return [dict(row) for row in result.mappings().all()]

    async def get_post(self, post_id: int) -> Post | None:
        result = await self.session.execute(
            select(Post).where(Post.id == post_id, Post.deleted_at.is_(None)),
        )
        post = result.scalar_one_or_none()
        await self._attach_post_taxonomy([post] if post is not None else [])
        return post

    async def get_post_by_slug(self, slug: str) -> Post | None:
        result = await self.session.execute(
            select(Post).where(Post.slug == slug, Post.deleted_at.is_(None)),
        )
        post = result.scalar_one_or_none()
        await self._attach_post_taxonomy([post] if post is not None else [])
        return post

    async def get_public_post_by_slug(self, slug: str) -> Post | None:
        now = utc_now()
        result = await self.session.execute(
            select(Post).where(
                Post.slug == slug,
                *_public_post_filters(now),
            ),
        )
        post = result.scalar_one_or_none()
        await self._attach_post_taxonomy([post] if post is not None else [])
        return post

    async def create_post(
        self,
        *,
        title: str,
        slug: str,
        summary: str | None,
        content_md: str,
        content_html: str,
        author_id: int,
        status: str,
        visibility: str,
        cover_file_id: int | None,
        word_count: int,
        seo_title: str | None,
        seo_description: str | None,
        seo_keywords: str | None,
        published_at,
    ) -> Post:
        post = Post(
            title=title,
            slug=slug,
            summary=summary,
            content_md=content_md,
            content_html=content_html,
            author_id=author_id,
            status=status,
            visibility=visibility,
            cover_file_id=cover_file_id,
            word_count=word_count,
            seo_title=seo_title,
            seo_description=seo_description,
            seo_keywords=seo_keywords,
            published_at=published_at,
        )
        self.session.add(post)
        await self.session.flush()
        return post

    async def replace_post_categories(
        self,
        *,
        post_id: int,
        category_names: Sequence[str],
    ) -> None:
        await self.session.execute(
            delete(PostCategory).where(PostCategory.post_id == post_id),
        )
        for name in _normalize_labels(category_names):
            category = await self._get_or_create_category(name)
            self.session.add(
                PostCategory(post_id=post_id, category_id=category.id),
            )
        await self.session.flush()

    async def replace_post_tags(
        self,
        *,
        post_id: int,
        tag_names: Sequence[str],
    ) -> None:
        await self.session.execute(
            delete(PostTag).where(PostTag.post_id == post_id),
        )
        for name in _normalize_labels(tag_names):
            tag = await self._get_or_create_tag(name)
            self.session.add(PostTag(post_id=post_id, tag_id=tag.id))
        await self.session.flush()

    async def file_exists(self, file_id: int) -> bool:
        result = await self.session.execute(
            select(BlogFile.id).where(
                BlogFile.id == file_id,
                BlogFile.deleted_at.is_(None),
                BlogFile.status == "active",
            ),
        )
        return result.scalar_one_or_none() is not None

    async def replace_file_usages(
        self,
        *,
        entity_type: str,
        entity_id: int,
        usages: Sequence[tuple[int, str]],
    ) -> None:
        await self.session.execute(
            delete(FileUsage).where(
                FileUsage.entity_type == entity_type,
                FileUsage.entity_id == entity_id,
            ),
        )
        for file_id, purpose in usages:
            self.session.add(
                FileUsage(
                    file_id=file_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    purpose=purpose,
                ),
            )
        await self.session.flush()

    async def list_pages(self, *, limit: int, offset: int) -> Sequence[Page]:
        result = await self.session.execute(
            select(Page)
            .where(Page.deleted_at.is_(None))
            .order_by(Page.updated_at.desc(), Page.id.desc())
            .limit(limit)
            .offset(offset),
        )
        return result.scalars().all()

    async def get_page(self, page_id: int) -> Page | None:
        result = await self.session.execute(
            select(Page).where(Page.id == page_id, Page.deleted_at.is_(None)),
        )
        return result.scalar_one_or_none()

    async def get_page_by_slug(self, slug: str) -> Page | None:
        result = await self.session.execute(
            select(Page).where(Page.slug == slug, Page.deleted_at.is_(None)),
        )
        return result.scalar_one_or_none()

    async def create_page(
        self,
        *,
        title: str,
        slug: str,
        content_md: str,
        content_html: str,
        status: str,
        show_in_nav: bool,
        sort_order: int,
        seo_title: str | None,
        seo_description: str | None,
    ) -> Page:
        page = Page(
            title=title,
            slug=slug,
            content_md=content_md,
            content_html=content_html,
            status=status,
            show_in_nav=show_in_nav,
            sort_order=sort_order,
            seo_title=seo_title,
            seo_description=seo_description,
        )
        self.session.add(page)
        await self.session.flush()
        return page

    async def commit(self) -> None:
        await self.session.commit()

    async def refresh(self, instance: object) -> None:
        await self.session.refresh(instance)

    async def _get_or_create_category(self, name: str) -> Category:
        slug = _slug_from_label(name, prefix="category")
        result = await self.session.execute(
            select(Category).where(Category.slug == slug),
        )
        category = result.scalar_one_or_none()
        if category is not None:
            return category
        category = Category(name=name, slug=slug)
        self.session.add(category)
        await self.session.flush()
        return category

    async def _get_or_create_tag(self, name: str) -> Tag:
        slug = _slug_from_label(name, prefix="tag")
        result = await self.session.execute(select(Tag).where(Tag.slug == slug))
        tag = result.scalar_one_or_none()
        if tag is not None:
            return tag
        tag = Tag(name=name, slug=slug)
        self.session.add(tag)
        await self.session.flush()
        return tag

    async def _attach_post_taxonomy(self, posts: Sequence[Post]) -> None:
        post_ids = [post.id for post in posts]
        if not post_ids:
            return

        categories = await self.session.execute(
            select(PostCategory.post_id, Category.name)
            .join(Category, Category.id == PostCategory.category_id)
            .where(PostCategory.post_id.in_(post_ids))
            .order_by(Category.sort_order, Category.name),
        )
        tags = await self.session.execute(
            select(PostTag.post_id, Tag.name)
            .join(Tag, Tag.id == PostTag.tag_id)
            .where(PostTag.post_id.in_(post_ids))
            .order_by(Tag.name),
        )
        category_map = _rows_to_map(categories.all())
        tag_map = _rows_to_map(tags.all())
        for post in posts:
            post.category_names = category_map.get(post.id, [])
            post.tag_names = tag_map.get(post.id, [])


def _normalize_labels(labels: Sequence[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for label in labels:
        value = label.strip()
        key = value.casefold()
        if not value or key in seen:
            continue
        seen.add(key)
        normalized.append(value[:64])
    return normalized


def _slug_from_label(label: str, *, prefix: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    if slug:
        return slug[:80]
    digest = sha1(label.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def _public_post_filters(now) -> tuple[object, ...]:
    return (
        Post.deleted_at.is_(None),
        or_(
            Post.status == "published",
            Post.status == "scheduled",
        ),
        Post.visibility == "public",
        Post.published_at.is_not(None),
        Post.published_at <= now,
    )


def _rows_to_map(rows: Sequence[tuple[int, str]]) -> dict[int, list[str]]:
    mapped: dict[int, list[str]] = {}
    for post_id, name in rows:
        mapped.setdefault(post_id, []).append(name)
    return mapped
