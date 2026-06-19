from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ValidationError

from app.api.admin.audit import record_admin_audit
from app.api.admin.dependencies import (
    AdminCsrfDependency,
    require_admin_permission,
)
from app.api.dependencies import (
    ContentServiceDependency,
    EncryptionSessionManagerDependency,
    LogServiceDependency,
    SettingsDependency,
)
from app.api.encrypted_response import (
    decrypt_encrypted_request,
    encrypted_response,
)
from app.core.encryption import EncryptionProfile
from app.schemas.content import (
    AdminPageItem,
    AdminPageListResponse,
    AdminPostItem,
    AdminPostListResponse,
    PageCreateRequest,
    PageUpdateRequest,
    PostCreateRequest,
    PostPreviewRequest,
    PostPreviewResponse,
    PostUpdateRequest,
)
from app.schemas.encryption import EncryptedApiRequest, EncryptedApiResponse
from app.schemas.pagination import PAGE_OFFSET_MAX
from app.services.auth import AuthenticatedUser
from app.services.content import (
    ContentFileNotFoundError,
    ContentNotFoundError,
    ContentSlugExistsError,
    CreatePageCommand,
    CreatePostCommand,
    UpdatePageCommand,
    UpdatePostCommand,
)
from app.services.encryption import EncryptionSessionManager
from app.services.files import sign_admin_preview_image_urls
from app.services.update_commands import UNSET

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
    offset: int = Query(default=0, ge=0, le=PAGE_OFFSET_MAX),
) -> EncryptedApiResponse:
    posts = await service.list_admin_posts(limit=limit, offset=offset)
    return await _content_response(
        AdminPostListResponse(
            items=[AdminPostItem.model_validate(post) for post in posts],
        ),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.post("/posts", response_model=EncryptedApiResponse)
async def create_post(
    payload: EncryptedApiRequest,
    current_user: PostWriterDependency,
    request: Request,
    _: AdminCsrfDependency,
    service: ContentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
) -> EncryptedApiResponse:
    decrypted_payload = await _decrypt_content_payload(
        payload,
        request=request,
        encryption_manager=encryption_manager,
    )
    post_payload = _validate_decrypted_payload(PostCreateRequest, decrypted_payload)
    try:
        post = await service.create_post(
            CreatePostCommand(
                title=post_payload.title,
                slug=post_payload.slug,
                summary=post_payload.summary,
                content_md=post_payload.content_md,
                author_id=current_user.id,
                status=post_payload.status,
                visibility=post_payload.visibility,
                cover_file_id=post_payload.cover_file_id,
                seo_title=post_payload.seo_title,
                seo_description=post_payload.seo_description,
                seo_keywords=post_payload.seo_keywords,
                category_names=post_payload.category_names,
                tag_names=post_payload.tag_names,
                published_at=post_payload.published_at,
            ),
        )
    except ContentSlugExistsError as exc:
        raise _slug_conflict("post slug already exists") from exc
    except ContentFileNotFoundError as exc:
        raise _not_found("file not found") from exc

    await record_admin_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="post.create",
        entity_type="post",
        entity_id=post.id,
        after_json=_post_audit_payload(post),
    )
    return await _content_response(
        AdminPostItem.model_validate(service.admin_post_response(post)),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.post("/posts/preview", response_model=EncryptedApiResponse)
async def preview_post(
    payload: EncryptedApiRequest,
    _: AdminCsrfDependency,
    __: PostWriterDependency,
    request: Request,
    service: ContentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    settings: SettingsDependency,
) -> EncryptedApiResponse:
    decrypted_payload = await _decrypt_content_payload(
        payload,
        request=request,
        encryption_manager=encryption_manager,
    )
    preview_payload = _validate_decrypted_payload(
        PostPreviewRequest,
        decrypted_payload,
    )
    content_html = service.render_preview(preview_payload.content_md)
    content_html = sign_admin_preview_image_urls(
        content_html=content_html,
        post_slug=preview_payload.slug,
        expires_seconds=settings.file_temporary_url_expire_seconds,
        secret_key=settings.secret_key,
    )
    return await _content_response(
        PostPreviewResponse(content_html=content_html),
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
        post = await service.get_admin_post(post_id)
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
    payload: EncryptedApiRequest,
    _: AdminCsrfDependency,
    current_user: PostWriterDependency,
    request: Request,
    service: ContentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
) -> EncryptedApiResponse:
    decrypted_payload = await _decrypt_content_payload(
        payload,
        request=request,
        encryption_manager=encryption_manager,
    )
    post_payload = _validate_decrypted_payload(PostUpdateRequest, decrypted_payload)
    try:
        post = await service.update_post(
            post_id=post_id,
            command=_update_post_command(post_payload),
        )
    except ContentNotFoundError as exc:
        raise _not_found("post not found") from exc
    except ContentSlugExistsError as exc:
        raise _slug_conflict("post slug already exists") from exc
    except ContentFileNotFoundError as exc:
        raise _not_found("file not found") from exc

    await record_admin_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="post.update",
        entity_type="post",
        entity_id=post.id,
        after_json={
            **_post_audit_payload(post),
            "changed_fields": sorted(post_payload.model_fields_set),
        },
    )
    return await _content_response(
        AdminPostItem.model_validate(service.admin_post_response(post)),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.post("/posts/{post_id}/publish", response_model=EncryptedApiResponse)
async def publish_post(
    post_id: int,
    _: AdminCsrfDependency,
    current_user: PostPublisherDependency,
    request: Request,
    service: ContentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
) -> EncryptedApiResponse:
    try:
        post = await service.publish_post(post_id)
    except ContentNotFoundError as exc:
        raise _not_found("post not found") from exc
    except ContentFileNotFoundError as exc:
        raise _not_found("file not found") from exc

    await record_admin_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="post.publish",
        entity_type="post",
        entity_id=post.id,
        after_json=_post_audit_payload(post),
    )
    return await _content_response(
        AdminPostItem.model_validate(service.admin_post_response(post)),
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
    offset: int = Query(default=0, ge=0, le=PAGE_OFFSET_MAX),
) -> EncryptedApiResponse:
    pages = await service.list_admin_pages(limit=limit, offset=offset)
    return await _content_response(
        AdminPageListResponse(
            items=[AdminPageItem.model_validate(page) for page in pages],
        ),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.post("/pages", response_model=EncryptedApiResponse)
async def create_page(
    payload: EncryptedApiRequest,
    _: AdminCsrfDependency,
    current_user: PageWriterDependency,
    request: Request,
    service: ContentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
) -> EncryptedApiResponse:
    decrypted_payload = await _decrypt_content_payload(
        payload,
        request=request,
        encryption_manager=encryption_manager,
    )
    page_payload = _validate_decrypted_payload(PageCreateRequest, decrypted_payload)
    try:
        page = await service.create_page(
            CreatePageCommand(
                title=page_payload.title,
                slug=page_payload.slug,
                content_md=page_payload.content_md,
                status=page_payload.status,
                show_in_nav=page_payload.show_in_nav,
                sort_order=page_payload.sort_order,
                seo_title=page_payload.seo_title,
                seo_description=page_payload.seo_description,
            ),
        )
    except ContentSlugExistsError as exc:
        raise _slug_conflict("page slug already exists") from exc

    await record_admin_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="page.create",
        entity_type="page",
        entity_id=page.id,
        after_json=_page_audit_payload(page),
    )
    return await _content_response(
        AdminPageItem.model_validate(service.admin_page_response(page)),
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
        page = await service.get_admin_page(page_id)
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
    payload: EncryptedApiRequest,
    _: AdminCsrfDependency,
    current_user: PageWriterDependency,
    request: Request,
    service: ContentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
) -> EncryptedApiResponse:
    decrypted_payload = await _decrypt_content_payload(
        payload,
        request=request,
        encryption_manager=encryption_manager,
    )
    page_payload = _validate_decrypted_payload(PageUpdateRequest, decrypted_payload)
    try:
        page = await service.update_page(
            page_id=page_id,
            command=_update_page_command(page_payload),
        )
    except ContentNotFoundError as exc:
        raise _not_found("page not found") from exc
    except ContentSlugExistsError as exc:
        raise _slug_conflict("page slug already exists") from exc

    await record_admin_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="page.update",
        entity_type="page",
        entity_id=page.id,
        after_json={
            **_page_audit_payload(page),
            "changed_fields": sorted(page_payload.model_fields_set),
        },
    )
    return await _content_response(
        AdminPageItem.model_validate(service.admin_page_response(page)),
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


async def _decrypt_content_payload(
    payload: EncryptedApiRequest,
    *,
    request: Request,
    encryption_manager: EncryptionSessionManager,
) -> dict[str, object]:
    return await decrypt_encrypted_request(
        payload,
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
    )


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


def _update_post_command(payload: PostUpdateRequest) -> UpdatePostCommand:
    fields = payload.model_fields_set
    return UpdatePostCommand(
        title=payload.title if "title" in fields else UNSET,
        slug=payload.slug if "slug" in fields else UNSET,
        summary=payload.summary if "summary" in fields else UNSET,
        content_md=payload.content_md if "content_md" in fields else UNSET,
        status=payload.status if "status" in fields else UNSET,
        visibility=payload.visibility if "visibility" in fields else UNSET,
        cover_file_id=payload.cover_file_id if "cover_file_id" in fields else UNSET,
        seo_title=payload.seo_title if "seo_title" in fields else UNSET,
        seo_description=(
            payload.seo_description if "seo_description" in fields else UNSET
        ),
        seo_keywords=payload.seo_keywords if "seo_keywords" in fields else UNSET,
        category_names=(
            payload.category_names if "category_names" in fields else UNSET
        ),
        tag_names=payload.tag_names if "tag_names" in fields else UNSET,
        published_at=payload.published_at if "published_at" in fields else UNSET,
    )


def _update_page_command(payload: PageUpdateRequest) -> UpdatePageCommand:
    fields = payload.model_fields_set
    return UpdatePageCommand(
        title=payload.title if "title" in fields else UNSET,
        slug=payload.slug if "slug" in fields else UNSET,
        content_md=payload.content_md if "content_md" in fields else UNSET,
        status=payload.status if "status" in fields else UNSET,
        show_in_nav=payload.show_in_nav if "show_in_nav" in fields else UNSET,
        sort_order=payload.sort_order if "sort_order" in fields else UNSET,
        seo_title=payload.seo_title if "seo_title" in fields else UNSET,
        seo_description=(
            payload.seo_description if "seo_description" in fields else UNSET
        ),
    )


def _post_audit_payload(post: object) -> dict[str, object]:
    return {
        "status": getattr(post, "status", None),
        "visibility": getattr(post, "visibility", None),
        "published_at_set": getattr(post, "published_at", None) is not None,
    }


def _page_audit_payload(page: object) -> dict[str, object]:
    return {
        "status": getattr(page, "status", None),
        "show_in_nav": getattr(page, "show_in_nav", None),
    }


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def _slug_conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
