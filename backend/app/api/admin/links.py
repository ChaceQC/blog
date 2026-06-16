from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ValidationError

from app.api.admin.dependencies import (
    AdminCsrfDependency,
    EncryptionSessionManagerDependency,
    LinkServiceDependency,
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
    FriendLinkReviewRequest,
)
from app.services.auth import AuthenticatedUser
from app.services.encryption import EncryptionSessionManager
from app.services.links import (
    InvalidFriendLinkStatusError,
    LinkNotFoundError,
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


@router.patch("/friend-links/{link_id}/review", response_model=EncryptedApiResponse)
async def review_friend_link(
    link_id: int,
    payload: EncryptedApiRequest,
    _: AdminCsrfDependency,
    __: FriendLinkReviewerDependency,
    request: Request,
    service: LinkServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="friend link not found",
        ) from exc
    except InvalidFriendLinkStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid friend link status",
        ) from exc

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


async def _links_response(
    payload: (
        AdminFriendLinkItem
        | AdminFriendLinkListResponse
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
