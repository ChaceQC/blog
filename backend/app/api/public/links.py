from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse

from app.api.dependencies import (
    EncryptionSessionManagerDependency,
    LogServiceDependency,
    RateLimitServiceDependency,
    SettingsDependency,
)
from app.api.encrypted_response import decrypt_encrypted_request, encrypted_response
from app.api.limits import enforce_rate_limit
from app.api.public.common import (
    PublicLinkServiceDependency,
    record_public_access,
    validate_decrypted_payload,
    validate_public_content_session,
)
from app.core.encryption import EncryptionProfile
from app.core.request import client_ip
from app.schemas.encryption import EncryptedApiRequest
from app.schemas.links import (
    PublicFriendLinkApplicationRequest,
    PublicFriendLinkApplicationResponse,
    PublicFriendLinkItem,
    PublicFriendLinkListResponse,
    PublicSiteNavItem,
    PublicSiteNavItemListResponse,
)
from app.schemas.pagination import PAGE_OFFSET_MAX
from app.services.links import (
    CreateFriendLinkCommand,
    SiteNavItemNotFoundError,
)
from app.services.rate_limit import RateLimitRule

router = APIRouter(tags=["public-links"])


@router.get("/friend-links")
async def list_public_friend_links(
    request: Request,
    service: PublicLinkServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=PAGE_OFFSET_MAX),
):
    await validate_public_content_session(request, encryption_manager)
    links = await service.list_public_friend_links(limit=limit, offset=offset)
    total = await service.count_public_friend_links()
    response = await encrypted_response(
        PublicFriendLinkListResponse(
            items=[PublicFriendLinkItem.model_validate(link) for link in links],
            total=total,
        ),
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
        scope="public",
    )
    await record_public_access(
        logs,
        request=request,
        access_type="public_friend_links_list",
        status_code=status.HTTP_200_OK,
        entity_type="friend_link",
        detail_json={
            "limit": limit,
            "offset": offset,
            "count": len(links),
            "total": total,
        },
    )
    return response


@router.post("/friend-links/applications")
async def create_public_friend_link_application(
    payload: EncryptedApiRequest,
    request: Request,
    service: PublicLinkServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    settings: SettingsDependency,
    logs: LogServiceDependency,
    rate_limiter: RateLimitServiceDependency,
):
    await enforce_rate_limit(
        request=request,
        limiter=rate_limiter,
        logs=logs,
        key=f"friend-link-application:{client_ip(request) or 'unknown'}",
        rule=RateLimitRule(
            max_attempts=settings.friend_link_application_rate_limit_max_attempts,
            window_seconds=settings.friend_link_application_rate_limit_window_seconds,
        ),
        event_type="rate_limit.friend_link_application",
        detail_json={"scope": "public"},
    )
    decrypted_payload = await decrypt_encrypted_request(
        payload,
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
        scope="public",
    )
    application = validate_decrypted_payload(
        PublicFriendLinkApplicationRequest,
        decrypted_payload,
    )
    link = await service.create_friend_link(
        CreateFriendLinkCommand(
            group_id=None,
            name=application.name,
            url=application.url,
            avatar_url=application.avatar_url,
            description=application.description,
            rss_url=application.rss_url,
            status="pending",
            sort_order=1000,
        ),
    )
    response = await encrypted_response(
        PublicFriendLinkApplicationResponse(id=link.id, status="pending"),
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
        scope="public",
    )
    await record_public_access(
        logs,
        request=request,
        access_type="public_friend_link_application",
        status_code=status.HTTP_200_OK,
        entity_type="friend_link",
        entity_id=link.id,
        detail_json={"name": application.name, "url": application.url},
    )
    return response


@router.get("/site-items")
async def list_public_site_items(
    request: Request,
    service: PublicLinkServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=PAGE_OFFSET_MAX),
):
    await validate_public_content_session(request, encryption_manager)
    items = await service.list_public_site_nav_items(limit=limit, offset=offset)
    total = await service.count_public_site_nav_items()
    response = await encrypted_response(
        PublicSiteNavItemListResponse(
            items=[PublicSiteNavItem.model_validate(item) for item in items],
            total=total,
        ),
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
        scope="public",
    )
    await record_public_access(
        logs,
        request=request,
        access_type="public_site_items_list",
        status_code=status.HTTP_200_OK,
        entity_type="site_nav_item",
        detail_json={
            "limit": limit,
            "offset": offset,
            "count": len(items),
            "total": total,
        },
    )
    return response


@router.get("/site-items/{item_id}/visit")
async def visit_public_site_item(
    item_id: int,
    request: Request,
    service: PublicLinkServiceDependency,
    logs: LogServiceDependency,
) -> RedirectResponse:
    try:
        item = await service.record_public_site_nav_click(item_id=item_id)
    except SiteNavItemNotFoundError as exc:
        await record_public_access(
            logs,
            request=request,
            access_type="public_site_item_visit",
            status_code=status.HTTP_404_NOT_FOUND,
            entity_type="site_nav_item",
            entity_id=item_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="site nav item not found",
        ) from exc

    await record_public_access(
        logs,
        request=request,
        access_type="public_site_item_visit",
        status_code=status.HTTP_302_FOUND,
        entity_type="site_nav_item",
        entity_id=item.id,
        detail_json={
            "click_count": item.click_count,
            "open_target": item.open_target,
        },
    )
    return RedirectResponse(url=item.url, status_code=status.HTTP_302_FOUND)
