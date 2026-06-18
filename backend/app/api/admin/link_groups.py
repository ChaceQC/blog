from fastapi import APIRouter, Query, Request

from app.api.admin.audit import record_admin_audit
from app.api.admin.dependencies import AdminCsrfDependency, LinkGroupServiceDependency
from app.api.admin.links_common import (
    FriendLinkReviewerDependency,
    SiteNavWriterDependency,
    decrypt_links_payload,
    friend_link_group_not_found,
    group_audit_payload,
    group_slug_exists,
    invalid_group_value,
    links_response,
    site_group_not_found,
    validate_decrypted_payload,
)
from app.api.dependencies import (
    EncryptionSessionManagerDependency,
    LogServiceDependency,
)
from app.schemas.encryption import EncryptedApiRequest, EncryptedApiResponse
from app.schemas.links import (
    AdminFriendLinkGroupItem,
    AdminFriendLinkGroupListResponse,
    AdminSiteNavGroupItem,
    AdminSiteNavGroupListResponse,
    FriendLinkGroupCreateRequest,
    FriendLinkGroupUpdateRequest,
    SiteNavGroupCreateRequest,
    SiteNavGroupUpdateRequest,
)
from app.schemas.pagination import PAGE_OFFSET_MAX
from app.services.link_groups import (
    CreateFriendLinkGroupCommand,
    CreateSiteNavGroupCommand,
    InvalidLinkGroupValueError,
    LinkGroupNotFoundError,
    LinkGroupSlugExistsError,
    UpdateFriendLinkGroupCommand,
    UpdateSiteNavGroupCommand,
)
from app.services.update_commands import UNSET

router = APIRouter(tags=["admin-link-groups"])


@router.get("/friend-link-groups", response_model=EncryptedApiResponse)
async def list_friend_link_groups(
    _: FriendLinkReviewerDependency,
    request: Request,
    service: LinkGroupServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=PAGE_OFFSET_MAX),
) -> EncryptedApiResponse:
    groups = await service.list_friend_link_groups(limit=limit, offset=offset)
    return await links_response(
        AdminFriendLinkGroupListResponse(
            items=[AdminFriendLinkGroupItem.model_validate(group) for group in groups],
        ),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.post("/friend-link-groups", response_model=EncryptedApiResponse)
async def create_friend_link_group(
    payload: EncryptedApiRequest,
    _: AdminCsrfDependency,
    current_user: FriendLinkReviewerDependency,
    request: Request,
    service: LinkGroupServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
) -> EncryptedApiResponse:
    decrypted_payload = await decrypt_links_payload(
        payload,
        request=request,
        encryption_manager=encryption_manager,
    )
    group_payload = validate_decrypted_payload(
        FriendLinkGroupCreateRequest,
        decrypted_payload,
    )
    try:
        group = await service.create_friend_link_group(
            CreateFriendLinkGroupCommand(
                name=group_payload.name,
                slug=group_payload.slug,
                sort_order=group_payload.sort_order,
            ),
        )
    except LinkGroupSlugExistsError as exc:
        raise group_slug_exists() from exc

    await record_admin_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="friend_link_group.create",
        entity_type="friend_link_group",
        entity_id=group.id,
        after_json=group_audit_payload(group),
    )
    return await links_response(
        AdminFriendLinkGroupItem.model_validate(group),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.patch("/friend-link-groups/{group_id}", response_model=EncryptedApiResponse)
async def update_friend_link_group(
    group_id: int,
    payload: EncryptedApiRequest,
    _: AdminCsrfDependency,
    current_user: FriendLinkReviewerDependency,
    request: Request,
    service: LinkGroupServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
) -> EncryptedApiResponse:
    decrypted_payload = await decrypt_links_payload(
        payload,
        request=request,
        encryption_manager=encryption_manager,
    )
    group_payload = validate_decrypted_payload(
        FriendLinkGroupUpdateRequest,
        decrypted_payload,
    )
    try:
        group = await service.update_friend_link_group(
            group_id=group_id,
            command=_update_friend_link_group_command(group_payload),
        )
    except LinkGroupNotFoundError as exc:
        raise friend_link_group_not_found() from exc
    except LinkGroupSlugExistsError as exc:
        raise group_slug_exists() from exc

    await record_admin_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="friend_link_group.update",
        entity_type="friend_link_group",
        entity_id=group.id,
        after_json={
            **group_audit_payload(group),
            "changed_fields": sorted(group_payload.model_fields_set),
        },
    )
    return await links_response(
        AdminFriendLinkGroupItem.model_validate(group),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.get("/site-groups", response_model=EncryptedApiResponse)
async def list_site_nav_groups(
    _: SiteNavWriterDependency,
    request: Request,
    service: LinkGroupServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=PAGE_OFFSET_MAX),
) -> EncryptedApiResponse:
    groups = await service.list_site_nav_groups(limit=limit, offset=offset)
    return await links_response(
        AdminSiteNavGroupListResponse(
            items=[AdminSiteNavGroupItem.model_validate(group) for group in groups],
        ),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.post("/site-groups", response_model=EncryptedApiResponse)
async def create_site_nav_group(
    payload: EncryptedApiRequest,
    _: AdminCsrfDependency,
    current_user: SiteNavWriterDependency,
    request: Request,
    service: LinkGroupServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
) -> EncryptedApiResponse:
    decrypted_payload = await decrypt_links_payload(
        payload,
        request=request,
        encryption_manager=encryption_manager,
    )
    group_payload = validate_decrypted_payload(
        SiteNavGroupCreateRequest,
        decrypted_payload,
    )
    try:
        group = await service.create_site_nav_group(
            CreateSiteNavGroupCommand(
                name=group_payload.name,
                slug=group_payload.slug,
                description=group_payload.description,
                visibility=group_payload.visibility,
                sort_order=group_payload.sort_order,
            ),
        )
    except LinkGroupSlugExistsError as exc:
        raise group_slug_exists() from exc
    except InvalidLinkGroupValueError as exc:
        raise invalid_group_value() from exc

    await record_admin_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="site_nav_group.create",
        entity_type="site_nav_group",
        entity_id=group.id,
        after_json=group_audit_payload(group),
    )
    return await links_response(
        AdminSiteNavGroupItem.model_validate(group),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.patch("/site-groups/{group_id}", response_model=EncryptedApiResponse)
async def update_site_nav_group(
    group_id: int,
    payload: EncryptedApiRequest,
    _: AdminCsrfDependency,
    current_user: SiteNavWriterDependency,
    request: Request,
    service: LinkGroupServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
) -> EncryptedApiResponse:
    decrypted_payload = await decrypt_links_payload(
        payload,
        request=request,
        encryption_manager=encryption_manager,
    )
    group_payload = validate_decrypted_payload(
        SiteNavGroupUpdateRequest,
        decrypted_payload,
    )
    try:
        group = await service.update_site_nav_group(
            group_id=group_id,
            command=_update_site_nav_group_command(group_payload),
        )
    except LinkGroupNotFoundError as exc:
        raise site_group_not_found() from exc
    except LinkGroupSlugExistsError as exc:
        raise group_slug_exists() from exc
    except InvalidLinkGroupValueError as exc:
        raise invalid_group_value() from exc

    await record_admin_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="site_nav_group.update",
        entity_type="site_nav_group",
        entity_id=group.id,
        after_json={
            **group_audit_payload(group),
            "changed_fields": sorted(group_payload.model_fields_set),
        },
    )
    return await links_response(
        AdminSiteNavGroupItem.model_validate(group),
        request=request,
        encryption_manager=encryption_manager,
    )


def _update_friend_link_group_command(
    payload: FriendLinkGroupUpdateRequest,
) -> UpdateFriendLinkGroupCommand:
    fields = payload.model_fields_set
    return UpdateFriendLinkGroupCommand(
        name=payload.name if "name" in fields else UNSET,
        slug=payload.slug if "slug" in fields else UNSET,
        sort_order=payload.sort_order if "sort_order" in fields else UNSET,
    )


def _update_site_nav_group_command(
    payload: SiteNavGroupUpdateRequest,
) -> UpdateSiteNavGroupCommand:
    fields = payload.model_fields_set
    return UpdateSiteNavGroupCommand(
        name=payload.name if "name" in fields else UNSET,
        slug=payload.slug if "slug" in fields else UNSET,
        description=payload.description if "description" in fields else UNSET,
        visibility=payload.visibility if "visibility" in fields else UNSET,
        sort_order=payload.sort_order if "sort_order" in fields else UNSET,
    )
