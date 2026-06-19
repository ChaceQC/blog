from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, Request, status

from app.api.dependencies import (
    EncryptionSessionManagerDependency,
    LogServiceDependency,
    SettingsDependency,
)
from app.api.encrypted_response import encrypted_response
from app.api.public.common import (
    PublicContentServiceDependency,
    record_public_access,
    validate_public_content_session,
)
from app.core.encryption import EncryptionProfile
from app.schemas.content import (
    SLUG_PATTERN,
    PublicPageDetail,
    PublicPostDetail,
    PublicPostItem,
    PublicPostListResponse,
)
from app.schemas.pagination import PAGE_OFFSET_MAX
from app.services.content import ContentNotFoundError
from app.services.content_read_models import PublicPostDetailRead, PublicPostRead
from app.services.files import create_article_render_token, sign_article_render_urls

router = APIRouter(tags=["public-posts"])


@router.get("/posts")
async def list_public_posts(
    request: Request,
    service: PublicContentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    settings: SettingsDependency,
    logs: LogServiceDependency,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=PAGE_OFFSET_MAX),
    category_slug: str | None = Query(
        default=None,
        alias="category",
        min_length=1,
        max_length=80,
        pattern=SLUG_PATTERN,
    ),
    tag_slug: str | None = Query(
        default=None,
        alias="tag",
        min_length=1,
        max_length=80,
        pattern=SLUG_PATTERN,
    ),
):
    await validate_public_content_session(request, encryption_manager)
    posts = await service.list_public_posts(
        limit=limit,
        offset=offset,
        category_slug=category_slug,
        tag_slug=tag_slug,
    )
    total = await service.count_public_posts(
        category_slug=category_slug,
        tag_slug=tag_slug,
    )
    response = await encrypted_response(
        PublicPostListResponse(
            items=[
                _signed_public_post_item(
                    post,
                    expires_seconds=settings.file_temporary_url_expire_seconds,
                    secret_key=settings.secret_key,
                )
                for post in posts
            ],
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
        access_type="public_posts_list",
        status_code=status.HTTP_200_OK,
        entity_type="post",
    )
    return response


@router.get("/posts/{slug}")
async def get_public_post(
    slug: Annotated[
        str,
        Path(min_length=1, max_length=220, pattern=SLUG_PATTERN),
    ],
    request: Request,
    service: PublicContentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    settings: SettingsDependency,
    logs: LogServiceDependency,
):
    await validate_public_content_session(request, encryption_manager)
    try:
        post = await service.get_public_post_by_slug(slug)
    except ContentNotFoundError as exc:
        await record_public_access(
            logs,
            request=request,
            access_type="public_post_detail",
            status_code=status.HTTP_404_NOT_FOUND,
            entity_type="post",
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
        scope="public",
    )
    await record_public_access(
        logs,
        request=request,
        access_type="public_post_detail",
        status_code=status.HTTP_200_OK,
        entity_type="post",
        entity_id=post.id,
    )
    return response


@router.get("/pages/{slug}")
async def get_public_page(
    slug: Annotated[
        str,
        Path(min_length=1, max_length=220, pattern=SLUG_PATTERN),
    ],
    request: Request,
    service: PublicContentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
):
    await validate_public_content_session(request, encryption_manager)
    try:
        page = await service.get_public_page_by_slug(slug)
    except ContentNotFoundError as exc:
        await record_public_access(
            logs,
            request=request,
            access_type="public_page_detail",
            status_code=status.HTTP_404_NOT_FOUND,
            entity_type="page",
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="page not found",
        ) from exc

    response = await encrypted_response(
        PublicPageDetail.model_validate(page),
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
        scope="public",
    )
    await record_public_access(
        logs,
        request=request,
        access_type="public_page_detail",
        status_code=status.HTTP_200_OK,
        entity_type="page",
        entity_id=page.id,
    )
    return response


def _signed_public_post_item(
    post: PublicPostRead,
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
        },
    )


def _public_post_detail(
    post: PublicPostDetailRead,
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
        },
    )


def _signed_cover_url(
    post: PublicPostRead,
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
