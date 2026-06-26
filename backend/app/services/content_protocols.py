from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Protocol

from app.models.content import Page, Post


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

    async def count_public_posts(
        self,
        *,
        category_slug: str | None = None,
        tag_slug: str | None = None,
    ) -> int: ...

    async def list_public_feed_posts(self, *, limit: int) -> Sequence[Post]: ...

    async def list_public_categories(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[Mapping[str, object]]: ...

    async def get_public_category_by_slug(
        self,
        slug: str,
    ) -> Mapping[str, object] | None: ...

    async def list_public_tags(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[Mapping[str, object]]: ...

    async def get_public_tag_by_slug(
        self,
        slug: str,
    ) -> Mapping[str, object] | None: ...

    async def get_post(self, post_id: int) -> Post | None: ...

    async def get_post_by_slug(self, slug: str) -> Post | None: ...

    async def get_public_post_by_slug(self, slug: str) -> Post | None: ...

    async def get_public_post_counts_by_slug(
        self,
        slug: str,
    ) -> tuple[int, int, int] | None: ...

    async def get_post_like_active(
        self,
        *,
        post_id: int,
        visitor_hash: str,
    ) -> bool: ...

    async def increment_post_view_count(self, *, post_id: int) -> None: ...

    async def set_post_like_state(
        self,
        *,
        post_id: int,
        visitor_hash: str,
        fingerprint_hash: str,
        risk_hash: str,
        liked: bool,
    ) -> bool: ...

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

    async def clear_post_interactions(self, *, post_id: int) -> None: ...

    async def list_pages(self, *, limit: int, offset: int) -> Sequence[Page]: ...

    async def get_page(self, page_id: int) -> Page | None: ...

    async def get_page_by_slug(self, slug: str) -> Page | None: ...

    async def get_public_page_by_slug(self, slug: str) -> Page | None: ...

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
