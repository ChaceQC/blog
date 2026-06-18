from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from app.models.content import Page, Post
from app.providers.markdown import count_words


@dataclass(frozen=True)
class PublicPostRead:
    id: int
    title: str
    slug: str
    summary: str | None
    cover_file_id: int | None
    word_count: int
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
        seo_title=post.seo_title,
        seo_description=post.seo_description,
        seo_keywords=post.seo_keywords,
        category_names=list(post.category_names),
        tag_names=list(post.tag_names),
        published_at=post.published_at,
        updated_at=post.updated_at,
    )


def public_post_detail_read(post: Post) -> PublicPostDetailRead:
    item = public_post_read(post)
    return PublicPostDetailRead(
        id=item.id,
        title=item.title,
        slug=item.slug,
        summary=item.summary,
        cover_file_id=item.cover_file_id,
        word_count=item.word_count,
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
