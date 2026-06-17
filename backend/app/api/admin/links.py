from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ValidationError

from app.api.admin.audit import record_admin_audit
from app.api.admin.dependencies import (
    AdminCsrfDependency,
    EncryptionSessionManagerDependency,
    LinkServiceDependency,
    LogServiceDependency,
    require_admin_permission,
)
from app.api.admin.encrypted_response import (
    decrypt_encrypted_request,
    encrypted_response,
)
from app.core.encryption import EncryptionProfile
from app.schemas.encryption import EncryptedApiRequest, EncryptedApiResponse
from app.schemas.links import (
    AdminFriendLinkItem,
    AdminFriendLinkListResponse,
    AdminSiteNavItem,
    AdminSiteNavItemListResponse,
    FriendLinkCreateRequest,
    FriendLinkReviewRequest,
    FriendLinkUpdateRequest,
    SiteNavItemCreateRequest,
    SiteNavItemUpdateRequest,
)
from app.services.auth import AuthenticatedUser
from app.services.encryption import EncryptionSessionManager
from app.services.links import (
    CreateFriendLinkCommand,
    CreateSiteNavItemCommand,
    InvalidFriendLinkStatusError,
    InvalidSiteNavItemValueError,
    LinkNotFoundError,
    SiteNavItemNotFoundError,
)

router = APIRouter(tags=["admin-links"])
FriendLinkReviewerDependency = Annotated[
    AuthenticatedUser,
    Depends(require_admin_permission("friend_link:review")),
]
SiteNavWriterDependency = Annotated[
    AuthenticatedUser,
    Depends(require_admin_permission("site_nav:write")),
]


@router.get("/friend-links", response_model=EncryptedApiResponse)
async def list_friend_links(
    _: FriendLinkReviewerDependency,
    request: Request,
    service: LinkServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
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
            changes=link_payload.model_dump(exclude_unset=True),
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
    offset: int = Query(default=0, ge=0),
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
            changes=item_payload.model_dump(exclude_unset=True),
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


def _friend_link_audit_payload(link: object) -> dict[str, object]:
    return {
        "name": getattr(link, "name", None),
        "url": getattr(link, "url", None),
        "status": getattr(link, "status", None),
        "sort_order": getattr(link, "sort_order", None),
    }


def _site_item_audit_payload(item: object) -> dict[str, object]:
    return {
        "title": getattr(item, "title", None),
        "url": getattr(item, "url", None),
        "visibility": getattr(item, "visibility", None),
        "open_target": getattr(item, "open_target", None),
        "sort_order": getattr(item, "sort_order", None),
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


def _invalid_site_item_value() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="invalid site nav item value",
    )
