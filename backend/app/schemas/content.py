from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ContentStatus = Literal["draft", "published", "scheduled", "archived"]
PostVisibility = Literal["public", "hidden", "private"]
SLUG_PATTERN = r"^[a-z0-9][a-z0-9_-]*$"


class PostCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=220, pattern=SLUG_PATTERN)
    summary: str | None = Field(default=None, max_length=500)
    content_md: str = Field(min_length=1)
    status: ContentStatus = "draft"
    visibility: PostVisibility = "public"
    seo_title: str | None = Field(default=None, max_length=255)
    seo_description: str | None = Field(default=None, max_length=500)

    model_config = ConfigDict(extra="forbid")


class PostUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=220,
        pattern=SLUG_PATTERN,
    )
    summary: str | None = Field(default=None, max_length=500)
    content_md: str | None = Field(default=None, min_length=1)
    status: ContentStatus | None = None
    visibility: PostVisibility | None = None
    seo_title: str | None = Field(default=None, max_length=255)
    seo_description: str | None = Field(default=None, max_length=500)

    model_config = ConfigDict(extra="forbid")


class AdminPostItem(BaseModel):
    id: int
    title: str
    slug: str
    summary: str | None
    content_md: str
    content_html: str
    status: str
    visibility: str
    author_id: int
    word_count: int
    seo_title: str | None
    seo_description: str | None
    published_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class AdminPostListResponse(BaseModel):
    items: list[AdminPostItem]

    model_config = ConfigDict(extra="forbid")


class PublicPostItem(BaseModel):
    id: int
    title: str
    slug: str
    summary: str | None
    word_count: int
    seo_title: str | None
    seo_description: str | None
    published_at: datetime | None
    updated_at: datetime | None

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class PublicPostDetail(PublicPostItem):
    content_html: str


class PublicPostListResponse(BaseModel):
    items: list[PublicPostItem]

    model_config = ConfigDict(extra="forbid")


class PageCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=220, pattern=SLUG_PATTERN)
    content_md: str = Field(min_length=1)
    status: ContentStatus = "draft"
    show_in_nav: bool = False
    sort_order: int = Field(default=0, ge=0, le=10000)
    seo_title: str | None = Field(default=None, max_length=255)
    seo_description: str | None = Field(default=None, max_length=500)

    model_config = ConfigDict(extra="forbid")


class PageUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=220,
        pattern=SLUG_PATTERN,
    )
    content_md: str | None = Field(default=None, min_length=1)
    status: ContentStatus | None = None
    show_in_nav: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10000)
    seo_title: str | None = Field(default=None, max_length=255)
    seo_description: str | None = Field(default=None, max_length=500)

    model_config = ConfigDict(extra="forbid")


class AdminPageItem(BaseModel):
    id: int
    title: str
    slug: str
    content_md: str
    content_html: str
    status: str
    show_in_nav: bool
    sort_order: int
    seo_title: str | None
    seo_description: str | None
    created_at: datetime | None
    updated_at: datetime | None

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class AdminPageListResponse(BaseModel):
    items: list[AdminPageItem]

    model_config = ConfigDict(extra="forbid")
