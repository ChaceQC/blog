from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel, ValidationError

from app.api.admin.dependencies import require_admin_permission
from app.api.encrypted_response import decrypt_encrypted_request, encrypted_response
from app.core.encryption import EncryptionProfile
from app.schemas.encryption import EncryptedApiRequest, EncryptedApiResponse
from app.services.auth import AuthenticatedUser
from app.services.encryption import EncryptionSessionManager

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


async def content_response(
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


async def decrypt_content_payload(
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


def not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def slug_conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
