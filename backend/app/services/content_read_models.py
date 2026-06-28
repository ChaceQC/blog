from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from app.models.content import Page, Post
from app.providers.markdown import count_words


@dataclass(frozen=True)
class AdminPostRead:
    id: int
    title: str
    slug: str
    summary: str | None
    content_md: str
    content_html: str
    status: str
    visibility: str
    cover_file_id: int | None
    author_id: int
    word_count: int
    seo_title: str | None
    seo_description: str | None
    seo_keywords: str | None
    category_names: list[str]
    tag_names: list[str]
    published_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True)
class AdminPageRead:
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


@dataclass(frozen=True)
class PublicPostRead:
    id: int
    title: str
    slug: str
    summary: str | None
    cover_file_id: int | None
    word_count: int
    view_count: int
    like_count: int
    comment_count: int
    seo_title: str | None
    seo_description: str | None
    seo_keywords: str | None
    category_names: list[str]
    tag_names: list[str]
    published_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True)
class PublicPostDetailRead(PublicPostRead):
    content_html: str
    content_md: str


@dataclass(frozen=True)
class PublicPageDetailRead:
    id: int
    title: str
    slug: str
    content_html: str
    seo_title: str | None
    seo_description: str | None
    updated_at: datetime | None


@dataclass(frozen=True)
class PublicTaxonomyRead:
    id: int
    name: str
    slug: str
    post_count: int


def public_post_read(post: Post) -> PublicPostRead:
    return PublicPostRead(
        id=post.id,
        title=post.title,
        slug=post.slug,
        summary=post.summary,
        cover_file_id=post.cover_file_id,
        word_count=max(post.word_count, count_words(post.content_md)),
        view_count=post.view_count,
        like_count=post.like_count,
        comment_count=post.comment_count,
        seo_title=post.seo_title,
        seo_description=post.seo_description,
        seo_keywords=post.seo_keywords,
        category_names=list(post.category_names),
        tag_names=list(post.tag_names),
        published_at=post.published_at,
        updated_at=post.updated_at,
    )


def admin_post_read(post: Post) -> AdminPostRead:
    return AdminPostRead(
        id=post.id,
        title=post.title,
        slug=post.slug,
        summary=post.summary,
        content_md=post.content_md,
        content_html=post.content_html,
        status=post.status,
        visibility=post.visibility,
        cover_file_id=post.cover_file_id,
        author_id=post.author_id,
        word_count=max(post.word_count, count_words(post.content_md)),
        seo_title=post.seo_title,
        seo_description=post.seo_description,
        seo_keywords=post.seo_keywords,
        category_names=list(post.category_names),
        tag_names=list(post.tag_names),
        published_at=post.published_at,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


def admin_post_reads(posts: Sequence[Post]) -> list[AdminPostRead]:
    return [admin_post_read(post) for post in posts]


def public_post_detail_read(post: Post) -> PublicPostDetailRead:
    item = public_post_read(post)
    return PublicPostDetailRead(
        id=item.id,
        title=item.title,
        slug=item.slug,
        summary=item.summary,
        cover_file_id=item.cover_file_id,
        word_count=item.word_count,
        view_count=item.view_count,
        like_count=item.like_count,
        comment_count=item.comment_count,
        seo_title=item.seo_title,
        seo_description=item.seo_description,
        seo_keywords=item.seo_keywords,
        category_names=item.category_names,
        tag_names=item.tag_names,
        published_at=item.published_at,
        updated_at=item.updated_at,
        content_html=post.content_html,
        content_md=post.content_md,
    )


def public_page_detail_read(page: Page) -> PublicPageDetailRead:
    return PublicPageDetailRead(
        id=page.id,
        title=page.title,
        slug=page.slug,
        content_html=page.content_html,
        seo_title=page.seo_title,
        seo_description=page.seo_description,
        updated_at=page.updated_at,
    )


def admin_page_read(page: Page) -> AdminPageRead:
    return AdminPageRead(
        id=page.id,
        title=page.title,
        slug=page.slug,
        content_md=page.content_md,
        content_html=page.content_html,
        status=page.status,
        show_in_nav=page.show_in_nav,
        sort_order=page.sort_order,
        seo_title=page.seo_title,
        seo_description=page.seo_description,
        created_at=page.created_at,
        updated_at=page.updated_at,
    )


def admin_page_reads(pages: Sequence[Page]) -> list[AdminPageRead]:
    return [admin_page_read(page) for page in pages]


def public_taxonomy_read(item: Mapping[str, object]) -> PublicTaxonomyRead:
    return PublicTaxonomyRead(
        id=int(item["id"]),
        name=str(item["name"]),
        slug=str(item["slug"]),
        post_count=int(item["post_count"]),
    )


def public_taxonomy_reads(
    items: Sequence[Mapping[str, object]],
) -> list[PublicTaxonomyRead]:
    return [public_taxonomy_read(item) for item in items]
