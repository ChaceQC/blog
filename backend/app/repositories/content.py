from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Page, Post
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
        return result.scalars().all()

    async def list_public_posts(self, *, limit: int, offset: int) -> Sequence[Post]:
        result = await self.session.execute(
            select(Post)
            .where(
                Post.deleted_at.is_(None),
                Post.status == "published",
                Post.visibility == "public",
            )
            .order_by(Post.published_at.desc(), Post.id.desc())
            .limit(limit)
            .offset(offset),
        )
        return result.scalars().all()

    async def get_post(self, post_id: int) -> Post | None:
        result = await self.session.execute(
            select(Post).where(Post.id == post_id, Post.deleted_at.is_(None)),
        )
        return result.scalar_one_or_none()

    async def get_post_by_slug(self, slug: str) -> Post | None:
        result = await self.session.execute(
            select(Post).where(Post.slug == slug, Post.deleted_at.is_(None)),
        )
        return result.scalar_one_or_none()

    async def get_public_post_by_slug(self, slug: str) -> Post | None:
        result = await self.session.execute(
            select(Post).where(
                Post.slug == slug,
                Post.deleted_at.is_(None),
                Post.status == "published",
                Post.visibility == "public",
            ),
        )
        return result.scalar_one_or_none()

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
        )
        self.session.add(post)
        await self.session.flush()
        return post

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
