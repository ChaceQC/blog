from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

ContentStatus = Literal["draft", "published", "scheduled", "archived"]
PostVisibility = Literal["public", "hidden", "private"]
SLUG_PATTERN = r"^[a-z0-9][a-z0-9_-]*$"
CONTENT_MD_MAX_LENGTH = 200_000
TAXONOMY_NAME_MAX_LENGTH = 64
TaxonomyName = Annotated[str, Field(min_length=1, max_length=TAXONOMY_NAME_MAX_LENGTH)]


class PostCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=220, pattern=SLUG_PATTERN)
    summary: str | None = Field(default=None, max_length=500)
    content_md: str = Field(min_length=1, max_length=CONTENT_MD_MAX_LENGTH)
    status: ContentStatus = "draft"
    visibility: PostVisibility = "public"
    cover_file_id: int | None = Field(default=None, ge=1)
    seo_title: str | None = Field(default=None, max_length=255)
    seo_description: str | None = Field(default=None, max_length=500)
    seo_keywords: str | None = Field(default=None, max_length=500)
    category_names: list[TaxonomyName] = Field(default_factory=list, max_length=8)
    tag_names: list[TaxonomyName] = Field(default_factory=list, max_length=20)
    published_at: datetime | None = None

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
    content_md: str | None = Field(
        default=None,
        min_length=1,
        max_length=CONTENT_MD_MAX_LENGTH,
    )
    status: ContentStatus | None = None
    visibility: PostVisibility | None = None
    cover_file_id: int | None = Field(default=None, ge=1)
    seo_title: str | None = Field(default=None, max_length=255)
    seo_description: str | None = Field(default=None, max_length=500)
    seo_keywords: str | None = Field(default=None, max_length=500)
    category_names: list[TaxonomyName] | None = Field(default=None, max_length=8)
    tag_names: list[TaxonomyName] | None = Field(default=None, max_length=20)
    published_at: datetime | None = None

    model_config = ConfigDict(extra="forbid")


class PostPreviewRequest(BaseModel):
    slug: str = Field(min_length=1, max_length=220, pattern=SLUG_PATTERN)
    content_md: str = Field(min_length=1, max_length=CONTENT_MD_MAX_LENGTH)

    model_config = ConfigDict(extra="forbid")


class PostPreviewResponse(BaseModel):
    content_html: str

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
    cover_file_id: int | None = None
    author_id: int
    word_count: int
    seo_title: str | None
    seo_description: str | None
    seo_keywords: str | None = None
    category_names: list[str] = Field(default_factory=list)
    tag_names: list[str] = Field(default_factory=list)
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
    cover_file_id: int | None
    cover_image_url: str | None = None
    word_count: int
    seo_title: str | None
    seo_description: str | None
    seo_keywords: str | None = None
    category_names: list[str] = Field(default_factory=list)
    tag_names: list[str] = Field(default_factory=list)
    published_at: datetime | None
    updated_at: datetime | None

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class PublicPostDetail(PublicPostItem):
    content_html: str


class PublicPageDetail(BaseModel):
    id: int
    title: str
    slug: str
    content_html: str
    seo_title: str | None
    seo_description: str | None
    updated_at: datetime | None

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class PublicPostListResponse(BaseModel):
    items: list[PublicPostItem]
    total: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid")


class PublicTaxonomyItem(BaseModel):
    id: int
    name: str
    slug: str
    post_count: int

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class PublicTaxonomyListResponse(BaseModel):
    items: list[PublicTaxonomyItem]

    model_config = ConfigDict(extra="forbid")


class PageCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=220, pattern=SLUG_PATTERN)
    content_md: str = Field(min_length=1, max_length=CONTENT_MD_MAX_LENGTH)
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
    content_md: str | None = Field(
        default=None,
        min_length=1,
        max_length=CONTENT_MD_MAX_LENGTH,
    )
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
