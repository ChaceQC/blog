from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.auth import utc_now
from app.models.content import Page, Post
from app.providers.markdown import MarkdownRenderer, count_words


class ContentNotFoundError(Exception):
    pass


class ContentSlugExistsError(Exception):
    pass


class ContentRepositoryProtocol(Protocol):
    async def list_posts(self, *, limit: int, offset: int) -> Sequence[Post]: ...

    async def get_post(self, post_id: int) -> Post | None: ...

    async def get_post_by_slug(self, slug: str) -> Post | None: ...

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
        word_count: int,
        seo_title: str | None,
        seo_description: str | None,
    ) -> Post: ...

    async def list_pages(self, *, limit: int, offset: int) -> Sequence[Page]: ...

    async def get_page(self, page_id: int) -> Page | None: ...

    async def get_page_by_slug(self, slug: str) -> Page | None: ...

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
    ) -> Page: ...

    async def commit(self) -> None: ...

    async def refresh(self, instance: object) -> None: ...


@dataclass(frozen=True)
class CreatePostCommand:
    title: str
    slug: str
    summary: str | None
    content_md: str
    author_id: int
    status: str
    visibility: str
    seo_title: str | None
    seo_description: str | None


@dataclass(frozen=True)
class CreatePageCommand:
    title: str
    slug: str
    content_md: str
    status: str
    show_in_nav: bool
    sort_order: int
    seo_title: str | None
    seo_description: str | None


class ContentService:
    def __init__(
        self,
        *,
        repository: ContentRepositoryProtocol,
        renderer: MarkdownRenderer | None = None,
    ) -> None:
        self.repository = repository
        self.renderer = renderer or MarkdownRenderer()

    async def list_posts(self, *, limit: int, offset: int) -> Sequence[Post]:
        return await self.repository.list_posts(limit=limit, offset=offset)

    async def get_post(self, post_id: int) -> Post:
        post = await self.repository.get_post(post_id)
        if post is None:
            raise ContentNotFoundError("post not found")
        return post

    async def create_post(self, command: CreatePostCommand) -> Post:
        await self._ensure_post_slug_available(command.slug)
        post = await self.repository.create_post(
            title=command.title,
            slug=command.slug,
            summary=command.summary,
            content_md=command.content_md,
            content_html=self.renderer.render(command.content_md),
            author_id=command.author_id,
            status=command.status,
            visibility=command.visibility,
            word_count=count_words(command.content_md),
            seo_title=command.seo_title,
            seo_description=command.seo_description,
        )
        if command.status == "published":
            post.published_at = utc_now()
        await self.repository.commit()
        await self.repository.refresh(post)
        return post

    async def update_post(self, *, post_id: int, changes: dict[str, Any]) -> Post:
        post = await self.get_post(post_id)
        slug = changes.get("slug")
        if isinstance(slug, str):
            await self._ensure_post_slug_available(slug, current_id=post.id)

        for field in (
            "title",
            "slug",
            "summary",
            "status",
            "visibility",
            "seo_title",
            "seo_description",
        ):
            if field in changes:
                setattr(post, field, changes[field])

        if "content_md" in changes:
            post.content_md = changes["content_md"]
            post.content_html = self.renderer.render(post.content_md)
            post.word_count = count_words(post.content_md)

        if post.status == "published" and post.published_at is None:
            post.published_at = utc_now()
        await self.repository.commit()
        await self.repository.refresh(post)
        return post

    async def publish_post(self, post_id: int) -> Post:
        post = await self.get_post(post_id)
        post.status = "published"
        post.published_at = utc_now()
        await self.repository.commit()
        await self.repository.refresh(post)
        return post

    async def list_pages(self, *, limit: int, offset: int) -> Sequence[Page]:
        return await self.repository.list_pages(limit=limit, offset=offset)

    async def get_page(self, page_id: int) -> Page:
        page = await self.repository.get_page(page_id)
        if page is None:
            raise ContentNotFoundError("page not found")
        return page

    async def create_page(self, command: CreatePageCommand) -> Page:
        await self._ensure_page_slug_available(command.slug)
        page = await self.repository.create_page(
            title=command.title,
            slug=command.slug,
            content_md=command.content_md,
            content_html=self.renderer.render(command.content_md),
            status=command.status,
            show_in_nav=command.show_in_nav,
            sort_order=command.sort_order,
            seo_title=command.seo_title,
            seo_description=command.seo_description,
        )
        await self.repository.commit()
        await self.repository.refresh(page)
        return page

    async def update_page(self, *, page_id: int, changes: dict[str, Any]) -> Page:
        page = await self.get_page(page_id)
        slug = changes.get("slug")
        if isinstance(slug, str):
            await self._ensure_page_slug_available(slug, current_id=page.id)

        for field in (
            "title",
            "slug",
            "status",
            "show_in_nav",
            "sort_order",
            "seo_title",
            "seo_description",
        ):
            if field in changes:
                setattr(page, field, changes[field])

        if "content_md" in changes:
            page.content_md = changes["content_md"]
            page.content_html = self.renderer.render(page.content_md)
        await self.repository.commit()
        await self.repository.refresh(page)
        return page

    async def _ensure_post_slug_available(
        self,
        slug: str,
        current_id: int | None = None,
    ) -> None:
        post = await self.repository.get_post_by_slug(slug)
        if post is not None and post.id != current_id:
            raise ContentSlugExistsError("post slug already exists")

    async def _ensure_page_slug_available(
        self,
        slug: str,
        current_id: int | None = None,
    ) -> None:
        page = await self.repository.get_page_by_slug(slug)
        if page is not None and page.id != current_id:
            raise ContentSlugExistsError("page slug already exists")
