from fastapi import APIRouter, Query, Request

from app.api.admin.audit import record_admin_audit
from app.api.admin.dependencies import (
    AdminContentEncryptionDependency,
    AdminCsrfDependency,
)
from app.api.admin.links_common import (
    SiteNavWriterDependency,
    decrypt_links_payload,
    invalid_site_item_value,
    links_response,
    site_item_audit_payload,
    site_item_not_found,
    validate_decrypted_payload,
)
from app.api.dependencies import (
    EncryptionSessionManagerDependency,
    LinkServiceDependency,
    LogServiceDependency,
)
from app.schemas.encryption import EncryptedApiRequest, EncryptedApiResponse
from app.schemas.links import (
    AdminSiteNavItem,
    AdminSiteNavItemListResponse,
    SiteNavItemCreateRequest,
    SiteNavItemUpdateRequest,
)
from app.schemas.pagination import PAGE_OFFSET_MAX
from app.services.links import (
    CreateSiteNavItemCommand,
    InvalidSiteNavItemValueError,
    SiteNavItemNotFoundError,
    UpdateSiteNavItemCommand,
)
from app.services.update_commands import UNSET

router = APIRouter(tags=["admin-site-nav"])


@router.get("/site-items", response_model=EncryptedApiResponse)
async def list_site_nav_items(
    _: SiteNavWriterDependency,
    __: AdminContentEncryptionDependency,
    request: Request,
    service: LinkServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=PAGE_OFFSET_MAX),
) -> EncryptedApiResponse:
    items = await service.list_site_nav_items(limit=limit, offset=offset)
    return await links_response(
        AdminSiteNavItemListResponse(
            items=[AdminSiteNavItem.model_validate(item) for item in items],
        ),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.post("/site-items", response_model=EncryptedApiResponse)
async def create_site_nav_item(
    payload: EncryptedApiRequest,
    _: AdminCsrfDependency,
    current_user: SiteNavWriterDependency,
    request: Request,
    service: LinkServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
) -> EncryptedApiResponse:
    decrypted_payload = await decrypt_links_payload(
        payload,
        request=request,
        encryption_manager=encryption_manager,
    )
    item_payload = validate_decrypted_payload(
        SiteNavItemCreateRequest,
        decrypted_payload,
    )
    try:
        item = await service.create_site_nav_item(
            CreateSiteNavItemCommand(
                group_id=item_payload.group_id,
                title=item_payload.title,
                url=item_payload.url,
                icon_url=item_payload.icon_url,
                description=item_payload.description,
                tags_json=item_payload.tags_json,
                open_target=item_payload.open_target,
                visibility=item_payload.visibility,
                sort_order=item_payload.sort_order,
            ),
        )
    except InvalidSiteNavItemValueError as exc:
        raise invalid_site_item_value() from exc

    await record_admin_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="site_nav.create",
        entity_type="site_nav_item",
        entity_id=item.id,
        after_json=site_item_audit_payload(item),
    )
    return await links_response(
        AdminSiteNavItem.model_validate(item),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.patch("/site-items/{item_id}", response_model=EncryptedApiResponse)
async def update_site_nav_item(
    item_id: int,
    payload: EncryptedApiRequest,
    _: AdminCsrfDependency,
    current_user: SiteNavWriterDependency,
    request: Request,
    service: LinkServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
) -> EncryptedApiResponse:
    decrypted_payload = await decrypt_links_payload(
        payload,
        request=request,
        encryption_manager=encryption_manager,
    )
    item_payload = validate_decrypted_payload(
        SiteNavItemUpdateRequest,
        decrypted_payload,
    )
    try:
        item = await service.update_site_nav_item(
            item_id=item_id,
            command=_update_site_nav_item_command(item_payload),
        )
    except SiteNavItemNotFoundError as exc:
        raise site_item_not_found() from exc
    except InvalidSiteNavItemValueError as exc:
        raise invalid_site_item_value() from exc

    await record_admin_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="site_nav.update",
        entity_type="site_nav_item",
        entity_id=item.id,
        after_json={
            **site_item_audit_payload(item),
            "changed_fields": sorted(item_payload.model_fields_set),
        },
    )
    return await links_response(
        AdminSiteNavItem.model_validate(item),
        request=request,
        encryption_manager=encryption_manager,
    )


def _update_site_nav_item_command(
    payload: SiteNavItemUpdateRequest,
) -> UpdateSiteNavItemCommand:
    fields = payload.model_fields_set
    return UpdateSiteNavItemCommand(
        group_id=payload.group_id if "group_id" in fields else UNSET,
        title=payload.title if "title" in fields else UNSET,
        url=payload.url if "url" in fields else UNSET,
        icon_url=payload.icon_url if "icon_url" in fields else UNSET,
        description=payload.description if "description" in fields else UNSET,
        tags_json=payload.tags_json if "tags_json" in fields else UNSET,
        open_target=payload.open_target if "open_target" in fields else UNSET,
        visibility=payload.visibility if "visibility" in fields else UNSET,
        sort_order=payload.sort_order if "sort_order" in fields else UNSET,
    )
