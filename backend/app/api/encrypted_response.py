from fastapi import HTTPException, Request, status
from pydantic import BaseModel

from app.core.encryption import EncryptionProfile
from app.core.encryption_sid import ESID_COOKIE_NAME
from app.schemas.encryption import (
    ENCRYPTION_SALT_ID_MAX_LENGTH,
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
    cached_validation = _cached_validation(
        request,
        session_id=session_id,
        scope=scope,
        profile=profile,
    )

    try:
        if cached_validation:
            return await manager.encrypt_response_for_validated_session(
                session_id=session_id,
                scope=scope,
                profile=profile,
                payload=payload.model_dump(mode="json"),
                response_salt_id=require_response_salt_id(request),
            )
        response = await manager.encrypt_response(
            session_id=session_id,
            esid=encryption_sid_from_request(request),
            esid_salt_id=encryption_esid_salt_id_from_request(request),
            scope=scope,
            profile=profile,
            payload=payload.model_dump(mode="json"),
            response_salt_id=require_response_salt_id(request),
        )
        _cache_validation(request, session_id=session_id, scope=scope, profile=profile)
        return response
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
            esid_salt_id=encryption_esid_salt_id_from_request(request),
            scope=scope,
            profile=profile,
        )
        _cache_validation(request, session_id=session_id, scope=scope, profile=profile)
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
        decrypted = await manager.decrypt_request(
            session_id=session_id,
            esid=encryption_sid_from_request(request),
            esid_salt_id=encryption_esid_salt_id_from_request(request),
            scope=scope,
            profile=profile,
            payload=payload,
        )
        _cache_validation(request, session_id=session_id, scope=scope, profile=profile)
        return decrypted
    except EncryptionSessionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid encrypted request",
        ) from exc


def encryption_sid_from_request(request: Request) -> str | None:
    return request.cookies.get(ESID_COOKIE_NAME)


def encryption_esid_salt_id_from_request(request: Request) -> str | None:
    salt_id = request.headers.get("x-encryption-esid-salt")
    if salt_id is None:
        return None
    if not salt_id or len(salt_id) > ENCRYPTION_SALT_ID_MAX_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid encryption salt",
        )
    return salt_id


def mark_encryption_session_validated(
    request: Request,
    *,
    session_id: str,
    scope: EncryptionSessionScope,
    profile: EncryptionProfile,
) -> None:
    _cache_validation(request, session_id=session_id, scope=scope, profile=profile)


def require_response_salt_id(request: Request) -> str:
    salt_id = request.headers.get("x-encryption-response-salt")
    if salt_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="missing encryption salt",
        )
    if not salt_id or len(salt_id) > ENCRYPTION_SALT_ID_MAX_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid encryption salt",
        )
    return salt_id


def _cache_validation(
    request: Request,
    *,
    session_id: str,
    scope: EncryptionSessionScope,
    profile: EncryptionProfile,
) -> None:
    request.state.encryption_validation = (session_id, scope, profile.value)


def _cached_validation(
    request: Request,
    *,
    session_id: str,
    scope: EncryptionSessionScope,
    profile: EncryptionProfile,
) -> bool:
    return getattr(request.state, "encryption_validation", None) == (
        session_id,
        scope,
        profile.value,
    )
