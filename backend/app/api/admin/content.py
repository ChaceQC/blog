from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.admin.dependencies import (
    AdminCsrfDependency,
    ContentServiceDependency,
    EncryptionSessionManagerDependency,
    require_admin_permission,
)
from app.api.admin.encrypted_response import encrypted_response
from app.core.encryption import EncryptionProfile
from app.schemas.content import (
    AdminPageItem,
    AdminPageListResponse,
    AdminPostItem,
    AdminPostListResponse,
    PageCreateRequest,
    PageUpdateRequest,
    PostCreateRequest,
    PostUpdateRequest,
)
from app.schemas.encryption import EncryptedApiResponse
from app.services.auth import AuthenticatedUser
from app.services.content import (
    ContentNotFoundError,
    ContentSlugExistsError,
    CreatePageCommand,
    CreatePostCommand,
)
from app.services.encryption import EncryptionSessionManager

router = APIRouter(tags=["admin-content"])
PostReaderDependency = Annotated[
    AuthenticatedUser,
    Depends(require_admin_permission("post:read")),
]
PostWriterDependency = Annotated[
    AuthenticatedUser,
    Depends(require_admin_permission("post:write")),
]
PostPublisherDependency = Annotated[
    AuthenticatedUser,
    Depends(require_admin_permission("post:publish")),
]
PageWriterDependency = Annotated[
    AuthenticatedUser,
    Depends(require_admin_permission("page:write")),
]


@router.get("/posts", response_model=EncryptedApiResponse)
async def list_posts(
    _: PostReaderDependency,
    request: Request,
    service: ContentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> EncryptedApiResponse:
    posts = await service.list_posts(limit=limit, offset=offset)
    return await _content_response(
        AdminPostListResponse(
            items=[AdminPostItem.model_validate(post) for post in posts],
        ),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.post("/posts", response_model=EncryptedApiResponse)
async def create_post(
    payload: PostCreateRequest,
    current_user: PostWriterDependency,
    request: Request,
    _: AdminCsrfDependency,
    service: ContentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
) -> EncryptedApiResponse:
    try:
        post = await service.create_post(
            CreatePostCommand(
                title=payload.title,
                slug=payload.slug,
                summary=payload.summary,
                content_md=payload.content_md,
                author_id=current_user.id,
                status=payload.status,
                visibility=payload.visibility,
                seo_title=payload.seo_title,
                seo_description=payload.seo_description,
            ),
        )
    except ContentSlugExistsError as exc:
        raise _slug_conflict("post slug already exists") from exc

    return await _content_response(
        AdminPostItem.model_validate(post),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.get("/posts/{post_id}", response_model=EncryptedApiResponse)
async def get_post(
    post_id: int,
    _: PostReaderDependency,
    request: Request,
    service: ContentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
) -> EncryptedApiResponse:
    try:
        post = await service.get_post(post_id)
    except ContentNotFoundError as exc:
        raise _not_found("post not found") from exc

    return await _content_response(
        AdminPostItem.model_validate(post),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.patch("/posts/{post_id}", response_model=EncryptedApiResponse)
async def update_post(
    post_id: int,
    payload: PostUpdateRequest,
    _: AdminCsrfDependency,
    __: PostWriterDependency,
    request: Request,
    service: ContentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
) -> EncryptedApiResponse:
    try:
        post = await service.update_post(
            post_id=post_id,
            changes=payload.model_dump(exclude_unset=True),
        )
    except ContentNotFoundError as exc:
        raise _not_found("post not found") from exc
    except ContentSlugExistsError as exc:
        raise _slug_conflict("post slug already exists") from exc

    return await _content_response(
        AdminPostItem.model_validate(post),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.post("/posts/{post_id}/publish", response_model=EncryptedApiResponse)
async def publish_post(
    post_id: int,
    _: AdminCsrfDependency,
    __: PostPublisherDependency,
    request: Request,
    service: ContentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
) -> EncryptedApiResponse:
    try:
        post = await service.publish_post(post_id)
    except ContentNotFoundError as exc:
        raise _not_found("post not found") from exc

    return await _content_response(
        AdminPostItem.model_validate(post),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.get("/pages", response_model=EncryptedApiResponse)
async def list_pages(
    _: PageWriterDependency,
    request: Request,
    service: ContentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> EncryptedApiResponse:
    pages = await service.list_pages(limit=limit, offset=offset)
    return await _content_response(
        AdminPageListResponse(
            items=[AdminPageItem.model_validate(page) for page in pages],
        ),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.post("/pages", response_model=EncryptedApiResponse)
async def create_page(
    payload: PageCreateRequest,
    _: AdminCsrfDependency,
    __: PageWriterDependency,
    request: Request,
    service: ContentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
) -> EncryptedApiResponse:
    try:
        page = await service.create_page(
            CreatePageCommand(
                title=payload.title,
                slug=payload.slug,
                content_md=payload.content_md,
                status=payload.status,
                show_in_nav=payload.show_in_nav,
                sort_order=payload.sort_order,
                seo_title=payload.seo_title,
                seo_description=payload.seo_description,
            ),
        )
    except ContentSlugExistsError as exc:
        raise _slug_conflict("page slug already exists") from exc

    return await _content_response(
        AdminPageItem.model_validate(page),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.get("/pages/{page_id}", response_model=EncryptedApiResponse)
async def get_page(
    page_id: int,
    _: PageWriterDependency,
    request: Request,
    service: ContentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
) -> EncryptedApiResponse:
    try:
        page = await service.get_page(page_id)
    except ContentNotFoundError as exc:
        raise _not_found("page not found") from exc

    return await _content_response(
        AdminPageItem.model_validate(page),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.patch("/pages/{page_id}", response_model=EncryptedApiResponse)
async def update_page(
    page_id: int,
    payload: PageUpdateRequest,
    _: AdminCsrfDependency,
    __: PageWriterDependency,
    request: Request,
    service: ContentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
) -> EncryptedApiResponse:
    try:
        page = await service.update_page(
            page_id=page_id,
            changes=payload.model_dump(exclude_unset=True),
        )
    except ContentNotFoundError as exc:
        raise _not_found("page not found") from exc
    except ContentSlugExistsError as exc:
        raise _slug_conflict("page slug already exists") from exc

    return await _content_response(
        AdminPageItem.model_validate(page),
        request=request,
        encryption_manager=encryption_manager,
    )


async def _content_response(
    payload: (
        AdminPostItem
        | AdminPostListResponse
        | AdminPageItem
        | AdminPageListResponse
    ),
    *,
    request: Request,
    encryption_manager: EncryptionSessionManager,
) -> EncryptedApiResponse:
    return await encrypted_response(
        payload,
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
    )


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def _slug_conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
