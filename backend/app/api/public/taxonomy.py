from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, Request, status

from app.api.dependencies import (
    EncryptionSessionManagerDependency,
    LogServiceDependency,
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
    PublicTaxonomyItem,
    PublicTaxonomyListResponse,
)
from app.schemas.pagination import PAGE_OFFSET_MAX
from app.services.content import ContentNotFoundError

router = APIRouter(tags=["public-taxonomy"])


@router.get("/categories")
async def list_public_categories(
    request: Request,
    service: PublicContentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=PAGE_OFFSET_MAX),
):
    await validate_public_content_session(request, encryption_manager)
    categories = await service.list_public_categories(limit=limit, offset=offset)
    response = await encrypted_response(
        PublicTaxonomyListResponse(
            items=[PublicTaxonomyItem.model_validate(item) for item in categories],
        ),
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
        scope="public",
    )
    await record_public_access(
        logs,
        request=request,
        access_type="public_categories_list",
        status_code=status.HTTP_200_OK,
        entity_type="category",
    )
    return response


@router.get("/categories/{slug}")
async def get_public_category(
    slug: Annotated[
        str,
        Path(min_length=1, max_length=80, pattern=SLUG_PATTERN),
    ],
    request: Request,
    service: PublicContentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
):
    await validate_public_content_session(request, encryption_manager)
    try:
        category = await service.get_public_category_by_slug(slug)
    except ContentNotFoundError as exc:
        await record_public_access(
            logs,
            request=request,
            access_type="public_category_detail",
            status_code=status.HTTP_404_NOT_FOUND,
            entity_type="category",
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="category not found",
        ) from exc

    response = await encrypted_response(
        PublicTaxonomyItem.model_validate(category),
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
        scope="public",
    )
    await record_public_access(
        logs,
        request=request,
        access_type="public_category_detail",
        status_code=status.HTTP_200_OK,
        entity_type="category",
        entity_id=category.id,
    )
    return response


@router.get("/tags")
async def list_public_tags(
    request: Request,
    service: PublicContentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=PAGE_OFFSET_MAX),
):
    await validate_public_content_session(request, encryption_manager)
    tags = await service.list_public_tags(limit=limit, offset=offset)
    response = await encrypted_response(
        PublicTaxonomyListResponse(
            items=[PublicTaxonomyItem.model_validate(item) for item in tags],
        ),
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
        scope="public",
    )
    await record_public_access(
        logs,
        request=request,
        access_type="public_tags_list",
        status_code=status.HTTP_200_OK,
        entity_type="tag",
    )
    return response


@router.get("/tags/{slug}")
async def get_public_tag(
    slug: Annotated[
        str,
        Path(min_length=1, max_length=80, pattern=SLUG_PATTERN),
    ],
    request: Request,
    service: PublicContentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
):
    await validate_public_content_session(request, encryption_manager)
    try:
        tag = await service.get_public_tag_by_slug(slug)
    except ContentNotFoundError as exc:
        await record_public_access(
            logs,
            request=request,
            access_type="public_tag_detail",
            status_code=status.HTTP_404_NOT_FOUND,
            entity_type="tag",
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="tag not found",
        ) from exc

    response = await encrypted_response(
        PublicTaxonomyItem.model_validate(tag),
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
        scope="public",
    )
    await record_public_access(
        logs,
        request=request,
        access_type="public_tag_detail",
        status_code=status.HTTP_200_OK,
        entity_type="tag",
        entity_id=tag.id,
    )
    return response
