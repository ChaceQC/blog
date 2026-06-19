from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel, ValidationError

from app.api.admin.dependencies import require_admin_permission
from app.api.encrypted_response import decrypt_encrypted_request, encrypted_response
from app.core.encryption import EncryptionProfile
from app.schemas.encryption import EncryptedApiRequest, EncryptedApiResponse
from app.services.auth import AuthenticatedUser
from app.services.encryption import EncryptionSessionManager

FriendLinkReviewerDependency = Annotated[
    AuthenticatedUser,
    Depends(require_admin_permission("friend_link:review")),
]
SiteNavWriterDependency = Annotated[
    AuthenticatedUser,
    Depends(require_admin_permission("site_nav:write")),
]


async def links_response(
    payload: BaseModel,
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


async def decrypt_links_payload(
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


def validate_decrypted_payload[T: BaseModel](
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


def friend_link_audit_payload(link: object) -> dict[str, object]:
    return {
        "status": getattr(link, "status", None),
    }


def site_item_audit_payload(item: object) -> dict[str, object]:
    return {
        "visibility": getattr(item, "visibility", None),
    }


def group_audit_payload(group: object) -> dict[str, object]:
    return {
        "visibility": getattr(group, "visibility", None),
    }


def link_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="friend link not found",
    )


def invalid_status() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="invalid friend link status",
    )


def site_item_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="site nav item not found",
    )


def friend_link_group_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="friend link group not found",
    )


def site_group_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="site nav group not found",
    )


def group_slug_exists() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="group slug already exists",
    )


def invalid_group_value() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="invalid group value",
    )


def invalid_site_item_value() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="invalid site nav item value",
    )
