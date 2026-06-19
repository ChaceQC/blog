from fastapi import APIRouter, Request, status
from fastapi.responses import Response

from app.api.dependencies import (
    LogServiceDependency,
    SettingsDependency,
    SettingServiceDependency,
)
from app.api.public.common import PublicContentServiceDependency
from app.api.public.feed_cache import (
    cacheable_response,
    cached_feed_response,
    cached_or_new_feed_response,
)
from app.api.public.feed_renderers import (
    render_robots,
    render_rss,
    render_sitemap,
    site_profile,
)
from app.core.request import client_ip

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
    cached = cached_feed_response(request, key="rss")
    if cached is not None:
        response, _count = cached
        if response.status_code == status.HTTP_304_NOT_MODIFIED:
            return response
        await record_feed_access(logs, request=request, access_type="public_rss")
        return response

    posts = list(await content.list_public_feed_posts(limit=FEED_POST_LIMIT))
    profile = site_profile((await settings_service.get_site_profile()).value_json)
    xml = render_rss(
        posts=posts,
        site_title=profile["title"],
        site_description=profile["description"],
        base_url=settings.public_base_url,
    )
    response = cached_or_new_feed_response(
        request=request,
        key="rss",
        content=xml,
        media_type="application/rss+xml",
        count=len(posts),
    )
    if response.status_code == status.HTTP_304_NOT_MODIFIED:
        return response
    await record_feed_access(logs, request=request, access_type="public_rss")
    return response


@router.get("/sitemap.xml")
async def sitemap(
    request: Request,
    content: PublicContentServiceDependency,
    settings: SettingsDependency,
    logs: LogServiceDependency,
) -> Response:
    cached = cached_feed_response(request, key="sitemap")
    if cached is not None:
        response, _count = cached
        if response.status_code == status.HTTP_304_NOT_MODIFIED:
            return response
        await record_feed_access(logs, request=request, access_type="public_sitemap")
        return response

    posts = list(await content.list_public_feed_posts(limit=FEED_POST_LIMIT))
    categories = list(
        await content.list_public_categories(limit=FEED_POST_LIMIT, offset=0),
    )
    tags = list(await content.list_public_tags(limit=FEED_POST_LIMIT, offset=0))
    xml = render_sitemap(
        posts=posts,
        categories=categories,
        tags=tags,
        base_url=settings.public_base_url,
    )
    response = cached_or_new_feed_response(
        request=request,
        key="sitemap",
        content=xml,
        media_type="application/xml",
        count=len(posts) + len(categories) + len(tags),
    )
    if response.status_code == status.HTTP_304_NOT_MODIFIED:
        return response
    await record_feed_access(logs, request=request, access_type="public_sitemap")
    return response


@router.get("/robots.txt")
async def robots_txt(
    request: Request,
    settings: SettingsDependency,
    logs: LogServiceDependency,
) -> Response:
    text = render_robots(base_url=settings.public_base_url)
    response = cacheable_response(
        request=request,
        content=text,
        media_type="text/plain; charset=utf-8",
    )
    if response.status_code == status.HTTP_304_NOT_MODIFIED:
        return response
    await record_feed_access(logs, request=request, access_type="public_robots")
    return response


async def record_feed_access(
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
