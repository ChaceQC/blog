from datetime import UTC, datetime
from email.utils import format_datetime
from hashlib import sha256
from html import escape
from time import monotonic
from typing import Any

from fastapi import APIRouter, Request, status
from fastapi.responses import Response

from app.api.dependencies import (
    LogServiceDependency,
    SettingsDependency,
    SettingServiceDependency,
)
from app.api.public.common import PublicContentServiceDependency
from app.core.request import client_ip
from app.models.content import Post
from app.services.content_read_models import PublicTaxonomyRead

FEED_POST_LIMIT = 1000
FEED_CACHE_CONTROL = "public, max-age=300, stale-while-revalidate=60"
FEED_CACHE_SECONDS = 300

router = APIRouter(tags=["feeds"])


class CachedFeed:
    def __init__(
        self,
        *,
        content: str,
        media_type: str,
        etag: str,
        count: int,
        expires_at: float,
    ) -> None:
        self.content = content
        self.media_type = media_type
        self.etag = etag
        self.count = count
        self.expires_at = expires_at


@router.get("/rss.xml")
async def rss_feed(
    request: Request,
    content: PublicContentServiceDependency,
    settings_service: SettingServiceDependency,
    settings: SettingsDependency,
    logs: LogServiceDependency,
) -> Response:
    cached = _cached_feed_response(request, key="rss")
    if cached is not None:
        response, count = cached
        if response.status_code == status.HTTP_304_NOT_MODIFIED:
            return response
        await _record_feed_access(
            logs,
            request=request,
            access_type="public_rss",
        )
        return response

    posts = list(await content.list_public_feed_posts(limit=FEED_POST_LIMIT))
    profile = _site_profile((await settings_service.get_site_profile()).value_json)
    xml = _render_rss(
        posts=posts,
        site_title=profile["title"],
        site_description=profile["description"],
        base_url=settings.public_base_url,
    )
    response = _cached_or_new_feed_response(
        request=request,
        key="rss",
        content=xml,
        media_type="application/rss+xml",
        count=len(posts),
    )
    if response.status_code == status.HTTP_304_NOT_MODIFIED:
        return response
    await _record_feed_access(
        logs,
        request=request,
        access_type="public_rss",
    )
    return response


@router.get("/sitemap.xml")
async def sitemap(
    request: Request,
    content: PublicContentServiceDependency,
    settings: SettingsDependency,
    logs: LogServiceDependency,
) -> Response:
    cached = _cached_feed_response(request, key="sitemap")
    if cached is not None:
        response, count = cached
        if response.status_code == status.HTTP_304_NOT_MODIFIED:
            return response
        await _record_feed_access(
            logs,
            request=request,
            access_type="public_sitemap",
        )
        return response

    posts = list(await content.list_public_feed_posts(limit=FEED_POST_LIMIT))
    categories = list(
        await content.list_public_categories(limit=FEED_POST_LIMIT, offset=0),
    )
    tags = list(await content.list_public_tags(limit=FEED_POST_LIMIT, offset=0))
    xml = _render_sitemap(
        posts=posts,
        categories=categories,
        tags=tags,
        base_url=settings.public_base_url,
    )
    response = _cached_or_new_feed_response(
        request=request,
        key="sitemap",
        content=xml,
        media_type="application/xml",
        count=len(posts) + len(categories) + len(tags),
    )
    if response.status_code == status.HTTP_304_NOT_MODIFIED:
        return response
    await _record_feed_access(
        logs,
        request=request,
        access_type="public_sitemap",
    )
    return response


@router.get("/robots.txt")
async def robots_txt(
    request: Request,
    settings: SettingsDependency,
    logs: LogServiceDependency,
) -> Response:
    text = _render_robots(base_url=settings.public_base_url)
    response = _cacheable_response(
        request=request,
        content=text,
        media_type="text/plain; charset=utf-8",
    )
    if response.status_code == status.HTTP_304_NOT_MODIFIED:
        return response
    await _record_feed_access(
        logs,
        request=request,
        access_type="public_robots",
    )
    return response


def _cacheable_response(*, request: Request, content: str, media_type: str) -> Response:
    etag = f'"{sha256(content.encode("utf-8")).hexdigest()}"'
    headers = {
        "Cache-Control": FEED_CACHE_CONTROL,
        "ETag": etag,
    }
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    return Response(content=content, media_type=media_type, headers=headers)


def _cached_or_new_feed_response(
    *,
    request: Request,
    key: str,
    content: str,
    media_type: str,
    count: int,
) -> Response:
    entry = CachedFeed(
        content=content,
        media_type=media_type,
        etag=f'"{sha256(content.encode("utf-8")).hexdigest()}"',
        count=count,
        expires_at=monotonic() + FEED_CACHE_SECONDS,
    )
    _feed_cache(request)[key] = entry
    return _feed_entry_response(request=request, entry=entry)


def _cached_feed_response(
    request: Request,
    *,
    key: str,
) -> tuple[Response, int] | None:
    entry = _feed_cache(request).get(key)
    if entry is None:
        return None
    if entry.expires_at <= monotonic():
        _feed_cache(request).pop(key, None)
        return None
    return _feed_entry_response(request=request, entry=entry), entry.count


def _feed_entry_response(*, request: Request, entry: CachedFeed) -> Response:
    headers = {
        "Cache-Control": FEED_CACHE_CONTROL,
        "ETag": entry.etag,
    }
    if request.headers.get("if-none-match") == entry.etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    return Response(content=entry.content, media_type=entry.media_type, headers=headers)


def _feed_cache(request: Request) -> dict[str, CachedFeed]:
    cache = getattr(request.app.state, "feed_response_cache", None)
    if not isinstance(cache, dict):
        cache = {}
        request.app.state.feed_response_cache = cache
    return cache


def _render_rss(
    *,
    posts: list[Post],
    site_title: str,
    site_description: str,
    base_url: str,
) -> str:
    normalized_base_url = _normalize_base_url(base_url)
    last_build_at = _latest_datetime(posts) or datetime.now(UTC)
    items = "\n".join(
        _render_rss_item(post=post, base_url=normalized_base_url) for post in posts
    )
    return "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<rss version="2.0">',
            "  <channel>",
            f"    <title>{_xml(site_title)}</title>",
            f"    <link>{_xml(normalized_base_url + '/')}</link>",
            f"    <description>{_xml(site_description)}</description>",
            "    <language>zh-CN</language>",
            f"    <lastBuildDate>{_rss_date(last_build_at)}</lastBuildDate>",
            items,
            "  </channel>",
            "</rss>",
            "",
        ],
    )


def _render_robots(*, base_url: str) -> str:
    normalized_base_url = _normalize_base_url(base_url)
    return "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /admin",
            "Disallow: /api/admin/",
            f"Sitemap: {normalized_base_url}/sitemap.xml",
            "",
        ],
    )


def _render_rss_item(*, post: Post, base_url: str) -> str:
    url = _post_url(base_url=base_url, post=post)
    description = post.seo_description or post.summary or post.title
    categories = "\n".join(
        f"      <category>{_xml(name)}</category>"
        for name in [*post.category_names, *post.tag_names]
    )
    parts = [
        "    <item>",
        f"      <title>{_xml(post.seo_title or post.title)}</title>",
        f"      <link>{_xml(url)}</link>",
        f"      <guid isPermaLink=\"true\">{_xml(url)}</guid>",
        f"      <description>{_xml(description)}</description>",
    ]
    if post.published_at is not None:
        parts.append(f"      <pubDate>{_rss_date(post.published_at)}</pubDate>")
    if categories:
        parts.append(categories)
    parts.append("    </item>")
    return "\n".join(parts)


def _render_sitemap(
    *,
    posts: list[Post],
    categories: list[PublicTaxonomyRead],
    tags: list[PublicTaxonomyRead],
    base_url: str,
) -> str:
    normalized_base_url = _normalize_base_url(base_url)
    latest_post_at = _latest_datetime(posts)
    urls = [
        _render_sitemap_url(
            loc=normalized_base_url + "/",
            lastmod=latest_post_at,
            priority="1.0",
        ),
        _render_sitemap_url(
            loc=f"{normalized_base_url}/posts",
            lastmod=latest_post_at,
            priority="0.8",
        ),
    ]
    urls.extend(
        _render_sitemap_url(
            loc=_post_url(base_url=normalized_base_url, post=post),
            lastmod=post.updated_at or post.published_at,
            priority="0.7",
        )
        for post in posts
    )
    urls.extend(
        _render_sitemap_url(
            loc=_taxonomy_url(
                base_url=normalized_base_url,
                kind="categories",
                item=category,
            ),
            lastmod=latest_post_at,
            priority="0.6",
        )
        for category in categories
    )
    urls.extend(
        _render_sitemap_url(
            loc=_taxonomy_url(base_url=normalized_base_url, kind="tags", item=tag),
            lastmod=latest_post_at,
            priority="0.5",
        )
        for tag in tags
    )
    return "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
            *urls,
            "</urlset>",
            "",
        ],
    )


def _render_sitemap_url(
    *,
    loc: str,
    lastmod: datetime | None,
    priority: str,
) -> str:
    parts = [
        "  <url>",
        f"    <loc>{_xml(loc)}</loc>",
    ]
    if lastmod is not None:
        parts.append(f"    <lastmod>{_xml(_sitemap_date(lastmod))}</lastmod>")
    parts.extend(
        [
            f"    <priority>{priority}</priority>",
            "  </url>",
        ],
    )
    return "\n".join(parts)


def _site_profile(value: dict[str, Any]) -> dict[str, str]:
    title = value.get("title")
    description = value.get("description")
    return {
        "title": title if isinstance(title, str) and title else "静默书房",
        "description": (
            description
            if isinstance(description, str) and description
            else "把长期写作、素材管理和自建服务收束到一处安静的发布空间。"
        ),
    }


def _post_url(*, base_url: str, post: Post) -> str:
    return f"{base_url}/posts/{post.slug}"


def _taxonomy_url(*, base_url: str, kind: str, item: PublicTaxonomyRead) -> str:
    return f"{base_url}/{kind}/{item.slug}"


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def _latest_datetime(posts: list[Post]) -> datetime | None:
    values = [
        value
        for post in posts
        for value in (post.updated_at, post.published_at)
        if value is not None
    ]
    if not values:
        return None
    return max(_aware_datetime(value) for value in values)


def _rss_date(value: datetime) -> str:
    return format_datetime(_aware_datetime(value), usegmt=True)


def _sitemap_date(value: datetime) -> str:
    return _aware_datetime(value).date().isoformat()


def _aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _xml(value: str) -> str:
    return escape(value, quote=True)


async def _record_feed_access(
    logs: LogServiceDependency,
    *,
    request: Request,
    access_type: str,
) -> None:
    await logs.record_access_log(
        access_type=access_type,
        method=request.method,
        path=str(request.url.path),
        status_code=status.HTTP_200_OK,
        entity_type="post",
        ip=client_ip(request),
        user_agent=request.headers.get("user-agent"),
        detail_json=None,
    )
