from collections.abc import Mapping
from datetime import UTC, datetime
from email.utils import format_datetime
from html import escape
from typing import Any

from fastapi import APIRouter, Request, status
from fastapi.responses import Response

from app.api.admin.dependencies import (
    LogServiceDependency,
    SettingsDependency,
    SettingServiceDependency,
)
from app.api.public.router import PublicContentServiceDependency
from app.models.content import Post

FEED_POST_LIMIT = 1000

router = APIRouter(tags=["feeds"])


@router.get("/rss.xml")
async def rss_feed(
    request: Request,
    content: PublicContentServiceDependency,
    settings_service: SettingServiceDependency,
    settings: SettingsDependency,
    logs: LogServiceDependency,
) -> Response:
    posts = list(await content.list_public_feed_posts(limit=FEED_POST_LIMIT))
    profile = _site_profile((await settings_service.get_site_profile()).value_json)
    xml = _render_rss(
        posts=posts,
        site_title=profile["title"],
        site_description=profile["description"],
        base_url=settings.public_base_url,
    )
    await _record_feed_access(
        logs,
        request=request,
        access_type="public_rss",
        count=len(posts),
    )
    return Response(content=xml, media_type="application/rss+xml")


@router.get("/sitemap.xml")
async def sitemap(
    request: Request,
    content: PublicContentServiceDependency,
    settings: SettingsDependency,
    logs: LogServiceDependency,
) -> Response:
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
    await _record_feed_access(
        logs,
        request=request,
        access_type="public_sitemap",
        count=len(posts) + len(categories) + len(tags),
    )
    return Response(content=xml, media_type="application/xml")


@router.get("/robots.txt")
async def robots_txt(
    request: Request,
    settings: SettingsDependency,
    logs: LogServiceDependency,
) -> Response:
    text = _render_robots(base_url=settings.public_base_url)
    await _record_feed_access(
        logs,
        request=request,
        access_type="public_robots",
        count=0,
    )
    return Response(content=text, media_type="text/plain; charset=utf-8")


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
    categories: list[Mapping[str, object]],
    tags: list[Mapping[str, object]],
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


def _taxonomy_url(*, base_url: str, kind: str, item: Mapping[str, object]) -> str:
    return f"{base_url}/{kind}/{item['slug']}"


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
    count: int,
) -> None:
    await logs.record_access_log(
        access_type=access_type,
        method=request.method,
        path=str(request.url.path),
        status_code=status.HTTP_200_OK,
        entity_type="post",
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail_json={"count": count},
    )
