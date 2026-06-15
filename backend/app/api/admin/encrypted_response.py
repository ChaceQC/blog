from fastapi import HTTPException, Request, status
from pydantic import BaseModel

from app.core.encryption import EncryptionProfile
from app.schemas.encryption import EncryptedApiRequest, EncryptedApiResponse, JsonObject
from app.services.encryption import EncryptionSessionError, EncryptionSessionManager


async def encrypted_response(
    payload: BaseModel,
    *,
    request: Request,
    manager: EncryptionSessionManager,
    profile: EncryptionProfile,
) -> EncryptedApiResponse:
    session_id = require_encryption_session(request)

    try:
        return await manager.encrypt_response(
            session_id=session_id,
            profile=profile,
            payload=payload.model_dump(mode="json"),
        )
    except EncryptionSessionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid encryption session",
        ) from exc


def require_encryption_session(request: Request) -> str:
    session_id = request.headers.get("x-encryption-session")
    if session_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="missing encryption session",
        )
    return session_id


async def decrypt_encrypted_request(
    payload: EncryptedApiRequest,
    *,
    request: Request,
    manager: EncryptionSessionManager,
    profile: EncryptionProfile,
) -> JsonObject:
    session_id = require_encryption_session(request)
    try:
        return await manager.decrypt_request(
            session_id=session_id,
            profile=profile,
            payload=payload,
        )
    except EncryptionSessionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid encrypted request",
        ) from exc
