from collections.abc import Sequence

from app.core.auth import utc_now
from app.models.content import Page, Post
from app.providers.markdown import MarkdownRenderer, count_words
from app.services.content_commands import (
    CreatePageCommand,
    CreatePostCommand,
    UpdatePageCommand,
    UpdatePostCommand,
)
from app.services.content_errors import (
    ContentFileNotFoundError,
    ContentNotFoundError,
    ContentSlugExistsError,
)
from app.services.content_post_helpers import (
    build_post_file_usages,
    normalize_labels,
    published_at_for_status,
)
from app.services.content_protocols import ContentRepositoryProtocol
from app.services.content_read_models import (
    AdminPageRead,
    AdminPostRead,
    PublicPageDetailRead,
    PublicPostDetailRead,
    PublicPostRead,
    PublicTaxonomyRead,
    admin_page_read,
    admin_page_reads,
    admin_post_read,
    admin_post_reads,
    public_page_detail_read,
    public_post_detail_read,
    public_post_read,
    public_taxonomy_read,
    public_taxonomy_reads,
)
from app.services.update_commands import is_set


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

    async def list_admin_posts(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[AdminPostRead]:
        posts = await self.repository.list_posts(limit=limit, offset=offset)
        return admin_post_reads(posts)

    async def list_public_posts(
        self,
        *,
        limit: int,
        offset: int,
        category_slug: str | None = None,
        tag_slug: str | None = None,
    ) -> Sequence[PublicPostRead]:
        posts = await self.repository.list_public_posts(
            limit=limit,
            offset=offset,
            category_slug=category_slug,
            tag_slug=tag_slug,
        )
        return [public_post_read(post) for post in posts]

    async def count_public_posts(
        self,
        *,
        category_slug: str | None = None,
        tag_slug: str | None = None,
    ) -> int:
        return await self.repository.count_public_posts(
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
    ) -> Sequence[PublicTaxonomyRead]:
        categories = await self.repository.list_public_categories(
            limit=limit,
            offset=offset,
        )
        return public_taxonomy_reads(categories)

    async def get_public_category_by_slug(self, slug: str) -> PublicTaxonomyRead:
        category = await self.repository.get_public_category_by_slug(slug)
        if category is None:
            raise ContentNotFoundError("category not found")
        return public_taxonomy_read(category)

    async def list_public_tags(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[PublicTaxonomyRead]:
        tags = await self.repository.list_public_tags(limit=limit, offset=offset)
        return public_taxonomy_reads(tags)

    async def get_public_tag_by_slug(self, slug: str) -> PublicTaxonomyRead:
        tag = await self.repository.get_public_tag_by_slug(slug)
        if tag is None:
            raise ContentNotFoundError("tag not found")
        return public_taxonomy_read(tag)

    async def get_post(self, post_id: int) -> Post:
        post = await self.repository.get_post(post_id)
        if post is None:
            raise ContentNotFoundError("post not found")
        return post

    async def get_admin_post(self, post_id: int) -> AdminPostRead:
        return admin_post_read(await self.get_post(post_id))

    def admin_post_response(self, post: Post) -> AdminPostRead:
        return admin_post_read(post)

    async def get_public_post_by_slug(self, slug: str) -> PublicPostDetailRead:
        post = await self.repository.get_public_post_by_slug(slug)
        if post is None:
            raise ContentNotFoundError("post not found")
        return public_post_detail_read(post)

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
            published_at=published_at_for_status(
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

    async def update_post(self, *, post_id: int, command: UpdatePostCommand) -> Post:
        post = await self.get_post(post_id)

        if is_set(command.slug):
            await self._ensure_post_slug_available(command.slug, current_id=post.id)
            post.slug = command.slug
        if is_set(command.title):
            post.title = command.title
        if is_set(command.summary):
            post.summary = command.summary
        if is_set(command.status):
            post.status = command.status
        if is_set(command.visibility):
            post.visibility = command.visibility
        if is_set(command.cover_file_id):
            post.cover_file_id = command.cover_file_id
        if is_set(command.seo_title):
            post.seo_title = command.seo_title
        if is_set(command.seo_description):
            post.seo_description = command.seo_description
        if is_set(command.seo_keywords):
            post.seo_keywords = command.seo_keywords

        if is_set(command.category_names):
            category_names = command.category_names or []
            await self.repository.replace_post_categories(
                post_id=post.id,
                category_names=category_names,
            )
            post.category_names = normalize_labels(category_names)
        if is_set(command.tag_names):
            tag_names = command.tag_names or []
            await self.repository.replace_post_tags(
                post_id=post.id,
                tag_names=tag_names,
            )
            post.tag_names = normalize_labels(tag_names)
        if is_set(command.published_at):
            post.published_at = command.published_at

        if is_set(command.content_md):
            post.content_md = command.content_md
            post.content_html = self.renderer.render(post.content_md)
            post.word_count = count_words(post.content_md)

        if is_set(command.status) and not is_set(command.published_at):
            post.published_at = published_at_for_status(
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

    async def list_admin_pages(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[AdminPageRead]:
        pages = await self.repository.list_pages(limit=limit, offset=offset)
        return admin_page_reads(pages)

    async def get_page(self, page_id: int) -> Page:
        page = await self.repository.get_page(page_id)
        if page is None:
            raise ContentNotFoundError("page not found")
        return page

    async def get_admin_page(self, page_id: int) -> AdminPageRead:
        return admin_page_read(await self.get_page(page_id))

    def admin_page_response(self, page: Page) -> AdminPageRead:
        return admin_page_read(page)

    async def get_public_page_by_slug(self, slug: str) -> PublicPageDetailRead:
        page = await self.repository.get_public_page_by_slug(slug)
        if page is None:
            raise ContentNotFoundError("page not found")
        return public_page_detail_read(page)

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

    async def update_page(self, *, page_id: int, command: UpdatePageCommand) -> Page:
        page = await self.get_page(page_id)

        if is_set(command.slug):
            await self._ensure_page_slug_available(command.slug, current_id=page.id)
            page.slug = command.slug
        if is_set(command.title):
            page.title = command.title
        if is_set(command.status):
            page.status = command.status
        if is_set(command.show_in_nav):
            page.show_in_nav = command.show_in_nav
        if is_set(command.sort_order):
            page.sort_order = command.sort_order
        if is_set(command.seo_title):
            page.seo_title = command.seo_title
        if is_set(command.seo_description):
            page.seo_description = command.seo_description

        if is_set(command.content_md):
            page.content_md = command.content_md
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
        usages = build_post_file_usages(
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
        normalized_categories = normalize_labels(category_names)
        normalized_tags = normalize_labels(tag_names)
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


__all__ = [
    "ContentFileNotFoundError",
    "ContentNotFoundError",
    "ContentRepositoryProtocol",
    "ContentService",
    "ContentSlugExistsError",
    "CreatePageCommand",
    "CreatePostCommand",
    "UpdatePageCommand",
    "UpdatePostCommand",
]
