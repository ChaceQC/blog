from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from app.services.update_commands import UNSET, UnsetType


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


@dataclass(frozen=True)
class UpdatePostCommand:
    title: str | UnsetType = UNSET
    slug: str | UnsetType = UNSET
    summary: str | None | UnsetType = UNSET
    content_md: str | UnsetType = UNSET
    status: str | UnsetType = UNSET
    visibility: str | UnsetType = UNSET
    cover_file_id: int | None | UnsetType = UNSET
    seo_title: str | None | UnsetType = UNSET
    seo_description: str | None | UnsetType = UNSET
    seo_keywords: str | None | UnsetType = UNSET
    category_names: Sequence[str] | None | UnsetType = UNSET
    tag_names: Sequence[str] | None | UnsetType = UNSET
    published_at: datetime | None | UnsetType = UNSET


@dataclass(frozen=True)
class UpdatePageCommand:
    title: str | UnsetType = UNSET
    slug: str | UnsetType = UNSET
    content_md: str | UnsetType = UNSET
    status: str | UnsetType = UNSET
    show_in_nav: bool | UnsetType = UNSET
    sort_order: int | UnsetType = UNSET
    seo_title: str | None | UnsetType = UNSET
    seo_description: str | None | UnsetType = UNSET
