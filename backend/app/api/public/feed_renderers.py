from datetime import UTC, datetime
from email.utils import format_datetime
from html import escape
from typing import Any

from app.models.content import Post
from app.services.content_read_models import PublicTaxonomyRead


def render_rss(
    *,
    posts: list[Post],
    site_title: str,
    site_description: str,
    base_url: str,
) -> str:
    normalized_base_url = normalize_base_url(base_url)
    last_build_at = latest_datetime(posts) or datetime.now(UTC)
    items = "\n".join(
        render_rss_item(post=post, base_url=normalized_base_url) for post in posts
    )
    return "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<rss version="2.0">',
            "  <channel>",
            f"    <title>{xml(site_title)}</title>",
            f"    <link>{xml(normalized_base_url + '/')}</link>",
            f"    <description>{xml(site_description)}</description>",
            "    <language>zh-CN</language>",
            f"    <lastBuildDate>{rss_date(last_build_at)}</lastBuildDate>",
            items,
            "  </channel>",
            "</rss>",
            "",
        ],
    )


def render_robots(*, base_url: str) -> str:
    normalized_base_url = normalize_base_url(base_url)
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


def render_rss_item(*, post: Post, base_url: str) -> str:
    url = post_url(base_url=base_url, post=post)
    description = post.seo_description or post.summary or post.title
    categories = "\n".join(
        f"      <category>{xml(name)}</category>"
        for name in [*post.category_names, *post.tag_names]
    )
    parts = [
        "    <item>",
        f"      <title>{xml(post.seo_title or post.title)}</title>",
        f"      <link>{xml(url)}</link>",
        f"      <guid isPermaLink=\"true\">{xml(url)}</guid>",
        f"      <description>{xml(description)}</description>",
    ]
    if post.published_at is not None:
        parts.append(f"      <pubDate>{rss_date(post.published_at)}</pubDate>")
    if categories:
        parts.append(categories)
    parts.append("    </item>")
    return "\n".join(parts)


def render_sitemap(
    *,
    posts: list[Post],
    categories: list[PublicTaxonomyRead],
    tags: list[PublicTaxonomyRead],
    base_url: str,
) -> str:
    normalized_base_url = normalize_base_url(base_url)
    latest_post_at = latest_datetime(posts)
    urls = [
        render_sitemap_url(
            loc=normalized_base_url + "/",
            lastmod=latest_post_at,
            priority="1.0",
        ),
        render_sitemap_url(
            loc=f"{normalized_base_url}/posts",
            lastmod=latest_post_at,
            priority="0.8",
        ),
    ]
    urls.extend(
        render_sitemap_url(
            loc=post_url(base_url=normalized_base_url, post=post),
            lastmod=post.updated_at or post.published_at,
            priority="0.7",
        )
        for post in posts
    )
    urls.extend(
        render_sitemap_url(
            loc=taxonomy_url(
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
        render_sitemap_url(
            loc=taxonomy_url(base_url=normalized_base_url, kind="tags", item=tag),
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


def render_sitemap_url(
    *,
    loc: str,
    lastmod: datetime | None,
    priority: str,
) -> str:
    parts = [
        "  <url>",
        f"    <loc>{xml(loc)}</loc>",
    ]
    if lastmod is not None:
        parts.append(f"    <lastmod>{xml(sitemap_date(lastmod))}</lastmod>")
    parts.extend(
        [
            f"    <priority>{priority}</priority>",
            "  </url>",
        ],
    )
    return "\n".join(parts)


def site_profile(value: dict[str, Any]) -> dict[str, str]:
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


def post_url(*, base_url: str, post: Post) -> str:
    return f"{base_url}/posts/{post.slug}"


def taxonomy_url(*, base_url: str, kind: str, item: PublicTaxonomyRead) -> str:
    return f"{base_url}/{kind}/{item.slug}"


def normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def latest_datetime(posts: list[Post]) -> datetime | None:
    values = [
        value
        for post in posts
        for value in (post.updated_at, post.published_at)
        if value is not None
    ]
    if not values:
        return None
    return max(aware_datetime(value) for value in values)


def rss_date(value: datetime) -> str:
    return format_datetime(aware_datetime(value), usegmt=True)


def sitemap_date(value: datetime) -> str:
    return aware_datetime(value).date().isoformat()


def aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def xml(value: str) -> str:
    return escape(value, quote=True)
