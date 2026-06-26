from collections.abc import Sequence

from sqlalchemy import case, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import (
    Category,
    Page,
    Post,
    PostCategory,
    PostLike,
    PostTag,
    Tag,
)
from app.models.file import BlogFile, FileUsage
from app.repositories.content_helpers import (
    normalize_labels,
    rows_to_map,
    slug_from_label,
)
from app.repositories.content_public import ContentPublicQueryMixin


class ContentRepository(ContentPublicQueryMixin):
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
        for name in normalize_labels(category_names):
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
        for name in normalize_labels(tag_names):
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

    async def get_post_like_active(
        self,
        *,
        post_id: int,
        visitor_hash: str,
    ) -> bool | None:
        result = await self.session.execute(
            select(PostLike.active).where(
                PostLike.post_id == post_id,
                PostLike.visitor_hash == visitor_hash,
            ),
        )
        return result.scalar_one_or_none()

    async def increment_post_view_count(self, *, post_id: int) -> None:
        await self.session.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(view_count=Post.view_count + 1),
        )
        await self.session.flush()

    async def set_post_like_state(
        self,
        *,
        post_id: int,
        visitor_hash: str,
        fingerprint_hash: str,
        risk_hash: str,
        liked: bool,
    ) -> bool:
        result = await self.session.execute(
            select(PostLike)
            .where(
                PostLike.post_id == post_id,
                PostLike.visitor_hash == visitor_hash,
            )
            .with_for_update(),
        )
        post_like = result.scalar_one_or_none()
        if post_like is None:
            if not liked:
                return False
            self.session.add(
                PostLike(
                    post_id=post_id,
                    visitor_hash=visitor_hash,
                    fingerprint_hash=fingerprint_hash,
                    risk_hash=risk_hash,
                    active=liked,
                ),
            )
            if liked:
                await self._increment_post_like_count(post_id)
            await self.session.flush()
            return liked

        previous = post_like.active
        post_like.fingerprint_hash = fingerprint_hash
        post_like.risk_hash = risk_hash
        post_like.active = liked
        if previous != liked:
            if liked:
                await self._increment_post_like_count(post_id)
            else:
                await self._decrement_post_like_count(post_id)
        await self.session.flush()
        return liked

    async def clear_post_interactions(self, *, post_id: int) -> None:
        await self.session.execute(
            delete(PostLike).where(PostLike.post_id == post_id),
        )
        await self.session.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(view_count=0, like_count=0),
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
        slug = slug_from_label(name, prefix="category")
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
        slug = slug_from_label(name, prefix="tag")
        result = await self.session.execute(select(Tag).where(Tag.slug == slug))
        tag = result.scalar_one_or_none()
        if tag is not None:
            return tag
        tag = Tag(name=name, slug=slug)
        self.session.add(tag)
        await self.session.flush()
        return tag

    async def _increment_post_like_count(self, post_id: int) -> None:
        await self.session.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(like_count=Post.like_count + 1),
        )

    async def _decrement_post_like_count(self, post_id: int) -> None:
        await self.session.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(
                like_count=case(
                    (Post.like_count > 0, Post.like_count - 1),
                    else_=0,
                ),
            ),
        )

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
        category_map = rows_to_map(categories.all())
        tag_map = rows_to_map(tags.all())
        for post in posts:
            post.category_names = category_map.get(post.id, [])
            post.tag_names = tag_map.get(post.id, [])
