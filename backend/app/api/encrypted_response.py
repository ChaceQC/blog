from fastapi import HTTPException, Request, status
from pydantic import BaseModel

from app.core.encryption import EncryptionProfile
from app.core.encryption_sid import ESID_COOKIE_NAME
from app.schemas.encryption import (
    ENCRYPTION_SESSION_ID_MAX_LENGTH,
    EncryptedApiRequest,
    EncryptedApiResponse,
    EncryptionSessionScope,
    JsonObject,
)
from app.services.encryption import EncryptionSessionError, EncryptionSessionManager


async def encrypted_response(
    payload: BaseModel,
    *,
    request: Request,
    manager: EncryptionSessionManager,
    profile: EncryptionProfile,
    scope: EncryptionSessionScope = "admin",
) -> EncryptedApiResponse:
    session_id = require_encryption_session(request)

    try:
        return await manager.encrypt_response(
            session_id=session_id,
            esid=encryption_sid_from_request(request),
            scope=scope,
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
    if not session_id or len(session_id) > ENCRYPTION_SESSION_ID_MAX_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid encryption session",
        )
    return session_id


async def validate_encryption_session(
    request: Request,
    *,
    manager: EncryptionSessionManager,
    profile: EncryptionProfile,
    scope: EncryptionSessionScope = "admin",
) -> None:
    session_id = require_encryption_session(request)
    try:
        await manager.validate_session(
            session_id=session_id,
            esid=encryption_sid_from_request(request),
            scope=scope,
            profile=profile,
        )
    except EncryptionSessionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid encryption session",
        ) from exc


async def decrypt_encrypted_request(
    payload: EncryptedApiRequest,
    *,
    request: Request,
    manager: EncryptionSessionManager,
    profile: EncryptionProfile,
    scope: EncryptionSessionScope = "admin",
) -> JsonObject:
    session_id = require_encryption_session(request)
    try:
        return await manager.decrypt_request(
            session_id=session_id,
            esid=encryption_sid_from_request(request),
            scope=scope,
            profile=profile,
            payload=payload,
        )
    except EncryptionSessionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid encrypted request",
        ) from exc


def encryption_sid_from_request(request: Request) -> str | None:
    return request.cookies.get(ESID_COOKIE_NAME)
