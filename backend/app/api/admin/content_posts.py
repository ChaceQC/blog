from fastapi import APIRouter, Query, Request

from app.api.admin.audit import record_admin_audit
from app.api.admin.content_common import (
    PostPublisherDependency,
    PostReaderDependency,
    PostWriterDependency,
    content_response,
    decrypt_content_payload,
    not_found,
    slug_conflict,
    validate_decrypted_payload,
)
from app.api.admin.dependencies import (
    AdminContentEncryptionDependency,
    AdminCsrfDependency,
)
from app.api.dependencies import (
    ContentServiceDependency,
    EncryptionSessionManagerDependency,
    LogServiceDependency,
    SettingsDependency,
)
from app.schemas.content import (
    AdminPostItem,
    AdminPostListResponse,
    PostCreateRequest,
    PostPreviewRequest,
    PostPreviewResponse,
    PostUpdateRequest,
)
from app.schemas.encryption import EncryptedApiRequest, EncryptedApiResponse
from app.schemas.pagination import PAGE_OFFSET_MAX
from app.services.content import (
    ContentFileNotFoundError,
    ContentNotFoundError,
    ContentSlugExistsError,
    CreatePostCommand,
    UpdatePostCommand,
)
from app.services.files import sign_admin_preview_image_urls
from app.services.update_commands import UNSET

router = APIRouter(tags=["admin-content"])


@router.get("/posts", response_model=EncryptedApiResponse)
async def list_posts(
    _: PostReaderDependency,
    __: AdminContentEncryptionDependency,
    request: Request,
    service: ContentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=PAGE_OFFSET_MAX),
) -> EncryptedApiResponse:
    posts = await service.list_admin_posts(limit=limit, offset=offset)
    return await content_response(
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
    decrypted_payload = await decrypt_content_payload(
        payload,
        request=request,
        encryption_manager=encryption_manager,
    )
    post_payload = validate_decrypted_payload(PostCreateRequest, decrypted_payload)
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
        raise slug_conflict("post slug already exists") from exc
    except ContentFileNotFoundError as exc:
        raise not_found("file not found") from exc

    await record_admin_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="post.create",
        entity_type="post",
        entity_id=post.id,
        after_json=post_audit_payload(post),
    )
    return await content_response(
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
    decrypted_payload = await decrypt_content_payload(
        payload,
        request=request,
        encryption_manager=encryption_manager,
    )
    preview_payload = validate_decrypted_payload(PostPreviewRequest, decrypted_payload)
    content_html = service.render_preview(preview_payload.content_md)
    content_html = sign_admin_preview_image_urls(
        content_html=content_html,
        post_slug=preview_payload.slug,
        expires_seconds=settings.file_temporary_url_expire_seconds,
        secret_key=settings.secret_key,
    )
    return await content_response(
        PostPreviewResponse(content_html=content_html),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.get("/posts/{post_id}", response_model=EncryptedApiResponse)
async def get_post(
    post_id: int,
    _: PostReaderDependency,
    __: AdminContentEncryptionDependency,
    request: Request,
    service: ContentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
) -> EncryptedApiResponse:
    try:
        post = await service.get_admin_post(post_id)
    except ContentNotFoundError as exc:
        raise not_found("post not found") from exc

    return await content_response(
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
    decrypted_payload = await decrypt_content_payload(
        payload,
        request=request,
        encryption_manager=encryption_manager,
    )
    post_payload = validate_decrypted_payload(PostUpdateRequest, decrypted_payload)
    try:
        post = await service.update_post(
            post_id=post_id,
            command=update_post_command(post_payload),
        )
    except ContentNotFoundError as exc:
        raise not_found("post not found") from exc
    except ContentSlugExistsError as exc:
        raise slug_conflict("post slug already exists") from exc
    except ContentFileNotFoundError as exc:
        raise not_found("file not found") from exc

    await record_admin_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="post.update",
        entity_type="post",
        entity_id=post.id,
        after_json={
            **post_audit_payload(post),
            "changed_fields": sorted(post_payload.model_fields_set),
        },
    )
    return await content_response(
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
        raise not_found("post not found") from exc
    except ContentFileNotFoundError as exc:
        raise not_found("file not found") from exc

    await record_admin_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="post.publish",
        entity_type="post",
        entity_id=post.id,
        after_json=post_audit_payload(post),
    )
    return await content_response(
        AdminPostItem.model_validate(service.admin_post_response(post)),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.delete("/posts/{post_id}", response_model=EncryptedApiResponse)
async def delete_post(
    post_id: int,
    _: AdminCsrfDependency,
    current_user: PostWriterDependency,
    request: Request,
    service: ContentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
) -> EncryptedApiResponse:
    try:
        post = await service.delete_post(post_id)
    except ContentNotFoundError as exc:
        raise not_found("post not found") from exc

    await record_admin_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="post.delete",
        entity_type="post",
        entity_id=post.id,
        after_json={**post_audit_payload(post), "deleted": True},
    )
    return await content_response(
        AdminPostItem.model_validate(service.admin_post_response(post)),
        request=request,
        encryption_manager=encryption_manager,
    )


def update_post_command(payload: PostUpdateRequest) -> UpdatePostCommand:
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


def post_audit_payload(post: object) -> dict[str, object]:
    return {
        "status": getattr(post, "status", None),
        "visibility": getattr(post, "visibility", None),
        "published_at_set": getattr(post, "published_at", None) is not None,
    }
