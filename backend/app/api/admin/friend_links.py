from fastapi import APIRouter, Query, Request

from app.api.admin.audit import record_admin_audit
from app.api.admin.dependencies import (
    AdminContentEncryptionDependency,
    AdminCsrfDependency,
)
from app.api.admin.links_common import (
    FriendLinkReviewerDependency,
    decrypt_links_payload,
    friend_link_audit_payload,
    invalid_status,
    link_not_found,
    links_response,
    validate_decrypted_payload,
)
from app.api.dependencies import (
    EncryptionSessionManagerDependency,
    LinkServiceDependency,
    LogServiceDependency,
)
from app.schemas.encryption import EncryptedApiRequest, EncryptedApiResponse
from app.schemas.links import (
    AdminFriendLinkItem,
    AdminFriendLinkListResponse,
    FriendLinkCreateRequest,
    FriendLinkReviewRequest,
    FriendLinkUpdateRequest,
)
from app.schemas.pagination import PAGE_OFFSET_MAX
from app.services.links import (
    CreateFriendLinkCommand,
    InvalidFriendLinkStatusError,
    LinkNotFoundError,
    UpdateFriendLinkCommand,
)
from app.services.update_commands import UNSET

router = APIRouter(tags=["admin-friend-links"])


@router.get("/friend-links", response_model=EncryptedApiResponse)
async def list_friend_links(
    _: FriendLinkReviewerDependency,
    __: AdminContentEncryptionDependency,
    request: Request,
    service: LinkServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=PAGE_OFFSET_MAX),
) -> EncryptedApiResponse:
    links = await service.list_friend_links(limit=limit, offset=offset)
    return await links_response(
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
    decrypted_payload = await decrypt_links_payload(
        payload,
        request=request,
        encryption_manager=encryption_manager,
    )
    link_payload = validate_decrypted_payload(
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
        raise invalid_status() from exc

    await record_admin_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="friend_link.create",
        entity_type="friend_link",
        entity_id=link.id,
        after_json=friend_link_audit_payload(link),
    )
    return await links_response(
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
    decrypted_payload = await decrypt_links_payload(
        payload,
        request=request,
        encryption_manager=encryption_manager,
    )
    link_payload = validate_decrypted_payload(
        FriendLinkUpdateRequest,
        decrypted_payload,
    )
    try:
        link = await service.update_friend_link(
            link_id=link_id,
            command=_update_friend_link_command(link_payload),
        )
    except LinkNotFoundError as exc:
        raise link_not_found() from exc
    except InvalidFriendLinkStatusError as exc:
        raise invalid_status() from exc

    await record_admin_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="friend_link.update",
        entity_type="friend_link",
        entity_id=link.id,
        after_json={
            **friend_link_audit_payload(link),
            "changed_fields": sorted(link_payload.model_fields_set),
        },
    )
    return await links_response(
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
    decrypted_payload = await decrypt_links_payload(
        payload,
        request=request,
        encryption_manager=encryption_manager,
    )
    review_payload = validate_decrypted_payload(
        FriendLinkReviewRequest,
        decrypted_payload,
    )
    try:
        link = await service.review_friend_link(
            link_id=link_id,
            status=review_payload.status,
        )
    except LinkNotFoundError as exc:
        raise link_not_found() from exc
    except InvalidFriendLinkStatusError as exc:
        raise invalid_status() from exc

    await record_admin_audit(
        logs=logs,
        request=request,
        actor=current_user,
        action="friend_link.review",
        entity_type="friend_link",
        entity_id=link.id,
        after_json={
            **friend_link_audit_payload(link),
            "review_status": review_payload.status,
        },
    )
    return await links_response(
        AdminFriendLinkItem.model_validate(link),
        request=request,
        encryption_manager=encryption_manager,
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
