from fastapi import APIRouter, Query, Request

from app.api.admin.audit import record_admin_audit
from app.api.admin.content_common import (
    PageWriterDependency,
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
)
from app.schemas.content import (
    AdminPageItem,
    AdminPageListResponse,
    PageCreateRequest,
    PageUpdateRequest,
)
from app.schemas.encryption import EncryptedApiRequest, EncryptedApiResponse
from app.schemas.pagination import PAGE_OFFSET_MAX
from app.services.content import (
    ContentNotFoundError,
    ContentSlugExistsError,
    CreatePageCommand,
    UpdatePageCommand,
)
from app.services.update_commands import UNSET

router = APIRouter(tags=["admin-content"])


@router.get("/pages", response_model=EncryptedApiResponse)
async def list_pages(
    _: PageWriterDependency,
    __: AdminContentEncryptionDependency,
    request: Request,
    service: ContentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=PAGE_OFFSET_MAX),
) -> EncryptedApiResponse:
    pages = await service.list_admin_pages(limit=limit, offset=offset)
    return await content_response(
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
    decrypted_payload = await decrypt_content_payload(
        payload,
        request=request,
        encryption_manager=encryption_manager,
    )
    page_payload = validate_decrypted_payload(PageCreateRequest, decrypted_payload)
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
        raise slug_conflict("page slug already exists") from exc

    await record_admin_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="page.create",
        entity_type="page",
        entity_id=page.id,
        after_json=page_audit_payload(page),
    )
    return await content_response(
        AdminPageItem.model_validate(service.admin_page_response(page)),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.get("/pages/{page_id}", response_model=EncryptedApiResponse)
async def get_page(
    page_id: int,
    _: PageWriterDependency,
    __: AdminContentEncryptionDependency,
    request: Request,
    service: ContentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
) -> EncryptedApiResponse:
    try:
        page = await service.get_admin_page(page_id)
    except ContentNotFoundError as exc:
        raise not_found("page not found") from exc

    return await content_response(
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
    decrypted_payload = await decrypt_content_payload(
        payload,
        request=request,
        encryption_manager=encryption_manager,
    )
    page_payload = validate_decrypted_payload(PageUpdateRequest, decrypted_payload)
    try:
        page = await service.update_page(
            page_id=page_id,
            command=update_page_command(page_payload),
        )
    except ContentNotFoundError as exc:
        raise not_found("page not found") from exc
    except ContentSlugExistsError as exc:
        raise slug_conflict("page slug already exists") from exc

    await record_admin_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="page.update",
        entity_type="page",
        entity_id=page.id,
        after_json={
            **page_audit_payload(page),
            "changed_fields": sorted(page_payload.model_fields_set),
        },
    )
    return await content_response(
        AdminPageItem.model_validate(service.admin_page_response(page)),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.delete("/pages/{page_id}", response_model=EncryptedApiResponse)
async def delete_page(
    page_id: int,
    _: AdminCsrfDependency,
    current_user: PageWriterDependency,
    request: Request,
    service: ContentServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
) -> EncryptedApiResponse:
    try:
        page = await service.delete_page(page_id)
    except ContentNotFoundError as exc:
        raise not_found("page not found") from exc

    await record_admin_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="page.delete",
        entity_type="page",
        entity_id=page.id,
        after_json={**page_audit_payload(page), "deleted": True},
    )
    return await content_response(
        AdminPageItem.model_validate(service.admin_page_response(page)),
        request=request,
        encryption_manager=encryption_manager,
    )


def update_page_command(payload: PageUpdateRequest) -> UpdatePageCommand:
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


def page_audit_payload(page: object) -> dict[str, object]:
    return {
        "status": getattr(page, "status", None),
        "show_in_nav": getattr(page, "show_in_nav", None),
    }
