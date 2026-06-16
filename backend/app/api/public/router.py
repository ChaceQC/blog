from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.dependencies import (
    EncryptionSessionManagerDependency,
    LogServiceDependency,
    SettingsDependency,
    SettingServiceDependency,
)
from app.api.admin.encrypted_response import encrypted_response
from app.api.public.encryption import router as public_encryption_router
from app.api.public.files import router as public_files_router
from app.core.database import get_session
from app.core.encryption import EncryptionProfile
from app.repositories.content import ContentRepository
from app.repositories.links import LinkRepository
from app.schemas.content import (
    PublicPostDetail,
    PublicPostItem,
    PublicPostListResponse,
)
from app.schemas.links import (
    PublicFriendLinkItem,
    PublicFriendLinkListResponse,
    PublicSiteNavItem,
    PublicSiteNavItemListResponse,
)
from app.schemas.settings import PublicSiteProfileResponse
from app.services.content import ContentNotFoundError, ContentService
from app.services.files import sign_article_render_urls
from app.services.links import LinkService

router = APIRouter(tags=["public"])
router.include_router(public_encryption_router)
router.include_router(public_files_router)
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


def get_public_content_service(session: SessionDependency) -> ContentService:
    return ContentService(repository=ContentRepository(session))


def get_public_link_service(session: SessionDependency) -> LinkService:
    return LinkService(repository=LinkRepository(session))


PublicContentServiceDependency = Annotated[
    ContentService,
    Depends(get_public_content_service),
]
PublicLinkServiceDependency = Annotated[
    LinkService,
    Depends(get_public_link_service),
]


@router.get("/status")
async def public_status() -> dict[str, str]:
    return {"status": "public-api-ready"}


@router.get("/posts")
async def list_public_posts(
    request: Request,
    service: PublicContentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    posts = await service.list_public_posts(limit=limit, offset=offset)
    response = await encrypted_response(
        PublicPostListResponse(
            items=[PublicPostItem.model_validate(post) for post in posts],
        ),
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
    )
    await _record_public_access(
        logs,
        request=request,
        access_type="public_posts_list",
        status_code=status.HTTP_200_OK,
        entity_type="post",
        detail_json={"limit": limit, "offset": offset, "count": len(posts)},
    )
    return response


@router.get("/posts/{slug}")
async def get_public_post(
    slug: str,
    request: Request,
    service: PublicContentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    settings: SettingsDependency,
    logs: LogServiceDependency,
):
    try:
        post = await service.get_public_post_by_slug(slug)
    except ContentNotFoundError as exc:
        await _record_public_access(
            logs,
            request=request,
            access_type="public_post_detail",
            status_code=status.HTTP_404_NOT_FOUND,
            entity_type="post",
            detail_json={"slug": slug},
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="post not found",
        ) from exc

    detail = PublicPostDetail.model_validate(post)
    signed_detail = detail.model_copy(
        update={
            "content_html": sign_article_render_urls(
                content_html=detail.content_html,
                post_slug=detail.slug,
                expires_seconds=settings.file_temporary_url_expire_seconds,
                secret_key=settings.secret_key,
            ),
        },
    )
    response = await encrypted_response(
        signed_detail,
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
    )
    await _record_public_access(
        logs,
        request=request,
        access_type="public_post_detail",
        status_code=status.HTTP_200_OK,
        entity_type="post",
        entity_id=post.id,
        detail_json={"slug": slug},
    )
    return response


@router.get("/settings/site-profile")
async def get_public_site_profile(
    request: Request,
    service: SettingServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
):
    setting = await service.get_site_profile()
    profile = _site_profile_response(setting.value_json)
    response = await encrypted_response(
        profile,
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
    )
    await _record_public_access(
        logs,
        request=request,
        access_type="public_site_profile",
        status_code=status.HTTP_200_OK,
        entity_type="setting",
        detail_json={"key_name": setting.key_name},
    )
    return response


@router.get("/friend-links")
async def list_public_friend_links(
    request: Request,
    service: PublicLinkServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    links = await service.list_public_friend_links(limit=limit, offset=offset)
    response = await encrypted_response(
        PublicFriendLinkListResponse(
            items=[PublicFriendLinkItem.model_validate(link) for link in links],
        ),
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
    )
    await _record_public_access(
        logs,
        request=request,
        access_type="public_friend_links_list",
        status_code=status.HTTP_200_OK,
        entity_type="friend_link",
        detail_json={"limit": limit, "offset": offset, "count": len(links)},
    )
    return response


@router.get("/site-items")
async def list_public_site_items(
    request: Request,
    service: PublicLinkServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    items = await service.list_public_site_nav_items(limit=limit, offset=offset)
    response = await encrypted_response(
        PublicSiteNavItemListResponse(
            items=[PublicSiteNavItem.model_validate(item) for item in items],
        ),
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
    )
    await _record_public_access(
        logs,
        request=request,
        access_type="public_site_items_list",
        status_code=status.HTTP_200_OK,
        entity_type="site_nav_item",
        detail_json={"limit": limit, "offset": offset, "count": len(items)},
    )
    return response


def _site_profile_response(value: dict[str, object]) -> PublicSiteProfileResponse:
    return PublicSiteProfileResponse(
        title=_string_value(value.get("title"), "静默书房"),
        owner=_string_value(value.get("owner"), "ChaceQC"),
        avatar_url=_string_value(
            value.get("avatar_url"),
            "https://github.com/ChaceQC.png",
        ),
        description=_string_value(
            value.get("description"),
            "把长期写作、素材管理和自建服务收束到一处安静的发布空间。",
        ),
        quote=_string_value(
            value.get("quote"),
            "「把想法放慢一点，让每一次发布都留下可以回看的纹理。」",
        ),
    )


def _string_value(value: object, fallback: str) -> str:
    return value if isinstance(value, str) and value else fallback


async def _record_public_access(
    logs: LogServiceDependency,
    *,
    request: Request,
    access_type: str,
    status_code: int,
    entity_type: str | None,
    entity_id: int | None = None,
    detail_json: dict[str, object] | None = None,
) -> None:
    await logs.record_access_log(
        access_type=access_type,
        method=request.method,
        path=str(request.url.path),
        status_code=status_code,
        entity_type=entity_type,
        entity_id=entity_id,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail_json=detail_json,
    )
