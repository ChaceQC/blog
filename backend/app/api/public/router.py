from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.dependencies import (
    EncryptionSessionManagerDependency,
    LogServiceDependency,
    RateLimitServiceDependency,
    SettingsDependency,
    SettingServiceDependency,
)
from app.api.admin.encrypted_response import (
    decrypt_encrypted_request,
    encrypted_response,
)
from app.api.admin.limits import client_ip, enforce_rate_limit
from app.api.public.encryption import router as public_encryption_router
from app.api.public.files import router as public_files_router
from app.core.database import get_session
from app.core.encryption import EncryptionProfile
from app.models.content import Post
from app.providers.markdown import count_words
from app.repositories.content import ContentRepository
from app.repositories.links import LinkRepository
from app.schemas.content import (
    PublicPostDetail,
    PublicPostItem,
    PublicPostListResponse,
)
from app.schemas.encryption import EncryptedApiRequest
from app.schemas.links import (
    PublicFriendLinkApplicationRequest,
    PublicFriendLinkApplicationResponse,
    PublicFriendLinkItem,
    PublicFriendLinkListResponse,
    PublicSiteNavItem,
    PublicSiteNavItemListResponse,
)
from app.schemas.settings import PublicSiteProfileResponse
from app.services.content import ContentNotFoundError, ContentService
from app.services.files import create_article_render_token, sign_article_render_urls
from app.services.links import CreateFriendLinkCommand, LinkService
from app.services.rate_limit import RateLimitRule

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
    settings: SettingsDependency,
    logs: LogServiceDependency,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    posts = await service.list_public_posts(limit=limit, offset=offset)
    response = await encrypted_response(
        PublicPostListResponse(
            items=[
                _public_post_item(
                    post,
                    expires_seconds=settings.file_temporary_url_expire_seconds,
                    secret_key=settings.secret_key,
                )
                for post in posts
            ],
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

    detail = _public_post_detail(
        post,
        expires_seconds=settings.file_temporary_url_expire_seconds,
        secret_key=settings.secret_key,
    )
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
    )
    application = _validate_decrypted_payload(
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
    )
    await _record_public_access(
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


def _validate_decrypted_payload[T: BaseModel](
    model: type[T],
    payload: dict[str, object],
) -> T:
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid encrypted request payload",
        ) from exc


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
        musings=_musings_value(value.get("musings")),
        social_links=_social_links_value(value.get("social_links")),
    )


def _string_value(value: object, fallback: str) -> str:
    return value if isinstance(value, str) and value else fallback


def _musings_value(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []

    musings: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        date = item.get("date")
        if isinstance(content, str) and content.strip():
            musings.append(
                {
                    "content": content.strip(),
                    "date": date.strip() if isinstance(date, str) else "",
                },
            )
    return musings[:3]


def _social_links_value(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []

    links: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        label = item.get("label")
        url = item.get("url")
        if (
            isinstance(label, str)
            and label.strip()
            and isinstance(url, str)
            and url.strip()
        ):
            links.append({"label": label.strip(), "url": url.strip()})
    return links[:6]


def _public_post_item(
    post: Post,
    *,
    expires_seconds: int,
    secret_key: str,
) -> PublicPostItem:
    item = PublicPostItem.model_validate(post)
    return item.model_copy(
        update={
            "cover_image_url": _signed_cover_url(
                post,
                expires_seconds=expires_seconds,
                secret_key=secret_key,
            ),
            "word_count": max(
                item.word_count,
                count_words(getattr(post, "content_md", "")),
            ),
        },
    )


def _public_post_detail(
    post: Post,
    *,
    expires_seconds: int,
    secret_key: str,
) -> PublicPostDetail:
    detail = PublicPostDetail.model_validate(post)
    return detail.model_copy(
        update={
            "cover_image_url": _signed_cover_url(
                post,
                expires_seconds=expires_seconds,
                secret_key=secret_key,
            ),
            "word_count": max(
                detail.word_count,
                count_words(getattr(post, "content_md", "")),
            ),
        },
    )


def _signed_cover_url(
    post: Post,
    *,
    expires_seconds: int,
    secret_key: str,
) -> str | None:
    if post.cover_file_id is None:
        return None

    access = create_article_render_token(
        post_slug=post.slug,
        file_id=post.cover_file_id,
        expires_seconds=expires_seconds,
        secret_key=secret_key,
    )
    return (
        f"/api/public/posts/{post.slug}/files/{post.cover_file_id}/thumbnail"
        f"?expires={access.expires}&token={access.token}"
    )


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
