from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ValidationError

from app.api.admin.audit import record_admin_audit
from app.api.admin.dependencies import (
    AdminCsrfDependency,
    LinkGroupServiceDependency,
    require_admin_permission,
)
from app.api.dependencies import (
    EncryptionSessionManagerDependency,
    LinkServiceDependency,
    LogServiceDependency,
)
from app.api.encrypted_response import (
    decrypt_encrypted_request,
    encrypted_response,
)
from app.core.encryption import EncryptionProfile
from app.schemas.encryption import EncryptedApiRequest, EncryptedApiResponse
from app.schemas.links import (
    AdminFriendLinkGroupItem,
    AdminFriendLinkGroupListResponse,
    AdminFriendLinkItem,
    AdminFriendLinkListResponse,
    AdminSiteNavGroupItem,
    AdminSiteNavGroupListResponse,
    AdminSiteNavItem,
    AdminSiteNavItemListResponse,
    FriendLinkCreateRequest,
    FriendLinkGroupCreateRequest,
    FriendLinkGroupUpdateRequest,
    FriendLinkReviewRequest,
    FriendLinkUpdateRequest,
    SiteNavGroupCreateRequest,
    SiteNavGroupUpdateRequest,
    SiteNavItemCreateRequest,
    SiteNavItemUpdateRequest,
)
from app.schemas.pagination import PAGE_OFFSET_MAX
from app.services.auth import AuthenticatedUser
from app.services.encryption import EncryptionSessionManager
from app.services.link_groups import (
    CreateFriendLinkGroupCommand,
    CreateSiteNavGroupCommand,
    InvalidLinkGroupValueError,
    LinkGroupNotFoundError,
    LinkGroupSlugExistsError,
    UpdateFriendLinkGroupCommand,
    UpdateSiteNavGroupCommand,
)
from app.services.links import (
    CreateFriendLinkCommand,
    CreateSiteNavItemCommand,
    InvalidFriendLinkStatusError,
    InvalidSiteNavItemValueError,
    LinkNotFoundError,
    SiteNavItemNotFoundError,
    UpdateFriendLinkCommand,
    UpdateSiteNavItemCommand,
)
from app.services.update_commands import UNSET

router = APIRouter(tags=["admin-links"])
FriendLinkReviewerDependency = Annotated[
    AuthenticatedUser,
    Depends(require_admin_permission("friend_link:review")),
]
SiteNavWriterDependency = Annotated[
    AuthenticatedUser,
    Depends(require_admin_permission("site_nav:write")),
]


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
    return await _links_response(
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
    decrypted_payload = await decrypt_encrypted_request(
        payload,
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
    )
    group_payload = _validate_decrypted_payload(
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
        raise _group_slug_exists() from exc

    await record_admin_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="friend_link_group.create",
        entity_type="friend_link_group",
        entity_id=group.id,
        after_json=_group_audit_payload(group),
    )
    return await _links_response(
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
    decrypted_payload = await decrypt_encrypted_request(
        payload,
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
    )
    group_payload = _validate_decrypted_payload(
        FriendLinkGroupUpdateRequest,
        decrypted_payload,
    )
    try:
        group = await service.update_friend_link_group(
            group_id=group_id,
            command=_update_friend_link_group_command(group_payload),
        )
    except LinkGroupNotFoundError as exc:
        raise _friend_link_group_not_found() from exc
    except LinkGroupSlugExistsError as exc:
        raise _group_slug_exists() from exc

    await record_admin_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="friend_link_group.update",
        entity_type="friend_link_group",
        entity_id=group.id,
        after_json={
            **_group_audit_payload(group),
            "changed_fields": sorted(group_payload.model_fields_set),
        },
    )
    return await _links_response(
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
    return await _links_response(
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
    decrypted_payload = await decrypt_encrypted_request(
        payload,
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
    )
    group_payload = _validate_decrypted_payload(
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
        raise _group_slug_exists() from exc
    except InvalidLinkGroupValueError as exc:
        raise _invalid_group_value() from exc

    await record_admin_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="site_nav_group.create",
        entity_type="site_nav_group",
        entity_id=group.id,
        after_json=_group_audit_payload(group),
    )
    return await _links_response(
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
    decrypted_payload = await decrypt_encrypted_request(
        payload,
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
    )
    group_payload = _validate_decrypted_payload(
        SiteNavGroupUpdateRequest,
        decrypted_payload,
    )
    try:
        group = await service.update_site_nav_group(
            group_id=group_id,
            command=_update_site_nav_group_command(group_payload),
        )
    except LinkGroupNotFoundError as exc:
        raise _site_group_not_found() from exc
    except LinkGroupSlugExistsError as exc:
        raise _group_slug_exists() from exc
    except InvalidLinkGroupValueError as exc:
        raise _invalid_group_value() from exc

    await record_admin_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="site_nav_group.update",
        entity_type="site_nav_group",
        entity_id=group.id,
        after_json={
            **_group_audit_payload(group),
            "changed_fields": sorted(group_payload.model_fields_set),
        },
    )
    return await _links_response(
        AdminSiteNavGroupItem.model_validate(group),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.get("/friend-links", response_model=EncryptedApiResponse)
async def list_friend_links(
    _: FriendLinkReviewerDependency,
    request: Request,
    service: LinkServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=PAGE_OFFSET_MAX),
) -> EncryptedApiResponse:
    links = await service.list_friend_links(limit=limit, offset=offset)
    return await _links_response(
        AdminFriendLinkListResponse(
            items=[AdminFriendLinkItem.model_validate(link) for link in links],
        ),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.post("/friend-links", response_model=EncryptedApiResponse)
async def create_friend_link(
    payload: EncryptedApiRequest,
    _: AdminCsrfDependency,
    current_user: FriendLinkReviewerDependency,
    request: Request,
    service: LinkServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
) -> EncryptedApiResponse:
    decrypted_payload = await decrypt_encrypted_request(
        payload,
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
    )
    link_payload = _validate_decrypted_payload(
        FriendLinkCreateRequest,
        decrypted_payload,
    )
    try:
        link = await service.create_friend_link(
            CreateFriendLinkCommand(
                group_id=link_payload.group_id,
                name=link_payload.name,
                url=link_payload.url,
                avatar_url=link_payload.avatar_url,
                description=link_payload.description,
                rss_url=link_payload.rss_url,
                status=link_payload.status,
                sort_order=link_payload.sort_order,
            ),
        )
    except InvalidFriendLinkStatusError as exc:
        raise _invalid_status() from exc

    await record_admin_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="friend_link.create",
        entity_type="friend_link",
        entity_id=link.id,
        after_json=_friend_link_audit_payload(link),
    )
    return await _links_response(
        AdminFriendLinkItem.model_validate(link),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.patch("/friend-links/{link_id}", response_model=EncryptedApiResponse)
async def update_friend_link(
    link_id: int,
    payload: EncryptedApiRequest,
    _: AdminCsrfDependency,
    current_user: FriendLinkReviewerDependency,
    request: Request,
    service: LinkServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
) -> EncryptedApiResponse:
    decrypted_payload = await decrypt_encrypted_request(
        payload,
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
    )
    link_payload = _validate_decrypted_payload(
        FriendLinkUpdateRequest,
        decrypted_payload,
    )
    try:
        link = await service.update_friend_link(
            link_id=link_id,
            command=_update_friend_link_command(link_payload),
        )
    except LinkNotFoundError as exc:
        raise _link_not_found() from exc
    except InvalidFriendLinkStatusError as exc:
        raise _invalid_status() from exc

    await record_admin_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="friend_link.update",
        entity_type="friend_link",
        entity_id=link.id,
        after_json={
            **_friend_link_audit_payload(link),
            "changed_fields": sorted(link_payload.model_fields_set),
        },
    )
    return await _links_response(
        AdminFriendLinkItem.model_validate(link),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.patch("/friend-links/{link_id}/review", response_model=EncryptedApiResponse)
async def review_friend_link(
    link_id: int,
    payload: EncryptedApiRequest,
    _: AdminCsrfDependency,
    current_user: FriendLinkReviewerDependency,
    request: Request,
    service: LinkServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    logs: LogServiceDependency,
) -> EncryptedApiResponse:
    decrypted_payload = await decrypt_encrypted_request(
        payload,
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
    )
    review_payload = _validate_decrypted_payload(
        FriendLinkReviewRequest,
        decrypted_payload,
    )
    try:
        link = await service.review_friend_link(
            link_id=link_id,
            status=review_payload.status,
        )
    except LinkNotFoundError as exc:
        raise _link_not_found() from exc
    except InvalidFriendLinkStatusError as exc:
        raise _invalid_status() from exc

    await record_admin_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="friend_link.review",
        entity_type="friend_link",
        entity_id=link.id,
        after_json={
            **_friend_link_audit_payload(link),
            "review_status": review_payload.status,
        },
    )
    return await _links_response(
        AdminFriendLinkItem.model_validate(link),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.get("/site-items", response_model=EncryptedApiResponse)
async def list_site_nav_items(
    _: SiteNavWriterDependency,
    request: Request,
    service: LinkServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=PAGE_OFFSET_MAX),
) -> EncryptedApiResponse:
    items = await service.list_site_nav_items(limit=limit, offset=offset)
    return await _links_response(
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
    decrypted_payload = await decrypt_encrypted_request(
        payload,
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
    )
    item_payload = _validate_decrypted_payload(
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
        raise _invalid_site_item_value() from exc

    await record_admin_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="site_nav.create",
        entity_type="site_nav_item",
        entity_id=item.id,
        after_json=_site_item_audit_payload(item),
    )
    return await _links_response(
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
    decrypted_payload = await decrypt_encrypted_request(
        payload,
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
    )
    item_payload = _validate_decrypted_payload(
        SiteNavItemUpdateRequest,
        decrypted_payload,
    )
    try:
        item = await service.update_site_nav_item(
            item_id=item_id,
            command=_update_site_nav_item_command(item_payload),
        )
    except SiteNavItemNotFoundError as exc:
        raise _site_item_not_found() from exc
    except InvalidSiteNavItemValueError as exc:
        raise _invalid_site_item_value() from exc

    await record_admin_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="site_nav.update",
        entity_type="site_nav_item",
        entity_id=item.id,
        after_json={
            **_site_item_audit_payload(item),
            "changed_fields": sorted(item_payload.model_fields_set),
        },
    )
    return await _links_response(
        AdminSiteNavItem.model_validate(item),
        request=request,
        encryption_manager=encryption_manager,
    )


async def _links_response(
    payload: (
        AdminFriendLinkGroupItem
        | AdminFriendLinkGroupListResponse
        | AdminSiteNavGroupItem
        | AdminSiteNavGroupListResponse
        |
        AdminFriendLinkItem
        | AdminFriendLinkListResponse
        | AdminSiteNavItem
        | AdminSiteNavItemListResponse
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


def _update_friend_link_command(
    payload: FriendLinkUpdateRequest,
) -> UpdateFriendLinkCommand:
    fields = payload.model_fields_set
    return UpdateFriendLinkCommand(
        group_id=payload.group_id if "group_id" in fields else UNSET,
        name=payload.name if "name" in fields else UNSET,
        url=payload.url if "url" in fields else UNSET,
        avatar_url=payload.avatar_url if "avatar_url" in fields else UNSET,
        description=payload.description if "description" in fields else UNSET,
        rss_url=payload.rss_url if "rss_url" in fields else UNSET,
        status=payload.status if "status" in fields else UNSET,
        sort_order=payload.sort_order if "sort_order" in fields else UNSET,
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


def _friend_link_audit_payload(link: object) -> dict[str, object]:
    return {
        "name": getattr(link, "name", None),
        "url": getattr(link, "url", None),
        "status": getattr(link, "status", None),
        "sort_order": getattr(link, "sort_order", None),
    }


def _site_item_audit_payload(item: object) -> dict[str, object]:
    return {
        "group_id": getattr(item, "group_id", None),
        "title": getattr(item, "title", None),
        "url": getattr(item, "url", None),
        "icon_url": getattr(item, "icon_url", None),
        "tags_json": getattr(item, "tags_json", None),
        "visibility": getattr(item, "visibility", None),
        "open_target": getattr(item, "open_target", None),
        "sort_order": getattr(item, "sort_order", None),
    }


def _group_audit_payload(group: object) -> dict[str, object]:
    return {
        "name": getattr(group, "name", None),
        "slug": getattr(group, "slug", None),
        "visibility": getattr(group, "visibility", None),
        "sort_order": getattr(group, "sort_order", None),
    }


def _link_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="friend link not found",
    )


def _invalid_status() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="invalid friend link status",
    )


def _site_item_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="site nav item not found",
    )


def _friend_link_group_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="friend link group not found",
    )


def _site_group_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="site nav group not found",
    )


def _group_slug_exists() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="group slug already exists",
    )


def _invalid_group_value() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="invalid group value",
    )


def _invalid_site_item_value() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="invalid site nav item value",
    )
