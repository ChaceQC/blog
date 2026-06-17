import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from app.core.auth import utc_now
from app.models.content import Page, Post
from app.providers.markdown import MarkdownRenderer, count_words


class ContentNotFoundError(Exception):
    pass


class ContentSlugExistsError(Exception):
    pass


class ContentFileNotFoundError(Exception):
    pass


class ContentRepositoryProtocol(Protocol):
    async def list_posts(self, *, limit: int, offset: int) -> Sequence[Post]: ...

    async def list_public_posts(
        self,
        *,
        limit: int,
        offset: int,
        category_slug: str | None = None,
        tag_slug: str | None = None,
    ) -> Sequence[Post]: ...

    async def list_public_feed_posts(self, *, limit: int) -> Sequence[Post]: ...

    async def list_public_categories(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[Mapping[str, object]]: ...

    async def list_public_tags(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[Mapping[str, object]]: ...

    async def get_post(self, post_id: int) -> Post | None: ...

    async def get_post_by_slug(self, slug: str) -> Post | None: ...

    async def get_public_post_by_slug(self, slug: str) -> Post | None: ...

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
        published_at: datetime | None,
    ) -> Post: ...

    async def replace_post_categories(
        self,
        *,
        post_id: int,
        category_names: Sequence[str],
    ) -> None: ...

    async def replace_post_tags(
        self,
        *,
        post_id: int,
        tag_names: Sequence[str],
    ) -> None: ...

    async def file_exists(self, file_id: int) -> bool: ...

    async def replace_file_usages(
        self,
        *,
        entity_type: str,
        entity_id: int,
        usages: Sequence[tuple[int, str]],
    ) -> None: ...

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
    cover_file_id: int | None
    seo_title: str | None
    seo_description: str | None
    seo_keywords: str | None = None
    category_names: Sequence[str] = ()
    tag_names: Sequence[str] = ()
    published_at: datetime | None = None


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

    async def list_public_posts(
        self,
        *,
        limit: int,
        offset: int,
        category_slug: str | None = None,
        tag_slug: str | None = None,
    ) -> Sequence[Post]:
        return await self.repository.list_public_posts(
            limit=limit,
            offset=offset,
            category_slug=category_slug,
            tag_slug=tag_slug,
        )

    async def list_public_feed_posts(self, *, limit: int) -> Sequence[Post]:
        return await self.repository.list_public_feed_posts(limit=limit)

    async def list_public_categories(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[Mapping[str, object]]:
        return await self.repository.list_public_categories(
            limit=limit,
            offset=offset,
        )

    async def list_public_tags(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[Mapping[str, object]]:
        return await self.repository.list_public_tags(limit=limit, offset=offset)

    async def get_post(self, post_id: int) -> Post:
        post = await self.repository.get_post(post_id)
        if post is None:
            raise ContentNotFoundError("post not found")
        return post

    async def get_public_post_by_slug(self, slug: str) -> Post:
        post = await self.repository.get_public_post_by_slug(slug)
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
            cover_file_id=command.cover_file_id,
            word_count=count_words(command.content_md),
            seo_title=command.seo_title,
            seo_description=command.seo_description,
            seo_keywords=command.seo_keywords,
            published_at=_published_at_for_status(
                status=command.status,
                requested_at=command.published_at,
            ),
        )
        await self._sync_post_taxonomy(
            post=post,
            category_names=command.category_names,
            tag_names=command.tag_names,
        )
        await self._sync_post_file_usages(post)
        await self.repository.commit()
        await self.repository.refresh(post)
        return post

    def render_preview(self, content_md: str) -> str:
        return self.renderer.render(content_md)

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
            "cover_file_id",
            "seo_title",
            "seo_description",
            "seo_keywords",
        ):
            if field in changes:
                setattr(post, field, changes[field])
        if "category_names" in changes:
            category_names = changes["category_names"] or []
            await self.repository.replace_post_categories(
                post_id=post.id,
                category_names=category_names,
            )
            post.category_names = _normalize_labels(category_names)
        if "tag_names" in changes:
            tag_names = changes["tag_names"] or []
            await self.repository.replace_post_tags(
                post_id=post.id,
                tag_names=tag_names,
            )
            post.tag_names = _normalize_labels(tag_names)
        if "published_at" in changes:
            post.published_at = changes["published_at"]

        if "content_md" in changes:
            post.content_md = changes["content_md"]
            post.content_html = self.renderer.render(post.content_md)
            post.word_count = count_words(post.content_md)

        if "status" in changes and "published_at" not in changes:
            post.published_at = _published_at_for_status(
                status=post.status,
                requested_at=post.published_at,
            )
        await self._sync_post_file_usages(post)
        await self.repository.commit()
        await self.repository.refresh(post)
        return post

    async def publish_post(self, post_id: int) -> Post:
        post = await self.get_post(post_id)
        post.status = "published"
        post.published_at = utc_now()
        await self._sync_post_file_usages(post)
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

    async def _sync_post_file_usages(self, post: Post) -> None:
        usages = _build_post_file_usages(
            content_md=post.content_md,
            cover_file_id=post.cover_file_id,
        )
        for file_id, _ in usages:
            if not await self.repository.file_exists(file_id):
                raise ContentFileNotFoundError("referenced file not found")
        await self.repository.replace_file_usages(
            entity_type="post",
            entity_id=post.id,
            usages=usages,
        )

    async def _sync_post_taxonomy(
        self,
        *,
        post: Post,
        category_names: Sequence[str],
        tag_names: Sequence[str],
    ) -> None:
        normalized_categories = _normalize_labels(category_names)
        normalized_tags = _normalize_labels(tag_names)
        await self.repository.replace_post_categories(
            post_id=post.id,
            category_names=normalized_categories,
        )
        await self.repository.replace_post_tags(
            post_id=post.id,
            tag_names=normalized_tags,
        )
        post.category_names = normalized_categories
        post.tag_names = normalized_tags


def _build_post_file_usages(
    *,
    content_md: str,
    cover_file_id: int | None,
) -> list[tuple[int, str]]:
    usages: list[tuple[int, str]] = []
    if cover_file_id is not None:
        usages.append((cover_file_id, "cover"))

    for file_id in _extract_post_body_file_ids(content_md):
        usages.append((file_id, "post_body"))

    seen: set[tuple[int, str]] = set()
    deduped: list[tuple[int, str]] = []
    for usage in usages:
        if usage not in seen:
            seen.add(usage)
            deduped.append(usage)
    return deduped


def _extract_post_body_file_ids(content_md: str) -> list[int]:
    pattern = re.compile(
        r"/?api/public/posts/[a-z0-9][a-z0-9_-]*/files/(?P<file_id>\d+)/render",
    )
    return [int(match.group("file_id")) for match in pattern.finditer(content_md)]


def _published_at_for_status(
    *,
    status: str,
    requested_at: datetime | None,
) -> datetime | None:
    if status == "published":
        return requested_at or utc_now()
    if status == "scheduled":
        return requested_at
    return None


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
