from fastapi import HTTPException, Request, status
from pydantic import BaseModel

from app.core.encryption import EncryptionProfile
from app.schemas.encryption import EncryptedApiResponse
from app.services.encryption import EncryptionSessionError, EncryptionSessionManager


def maybe_encrypt_response(
    payload: BaseModel,
    *,
    request: Request,
    manager: EncryptionSessionManager,
    profile: EncryptionProfile,
) -> BaseModel | EncryptedApiResponse:
    session_id = request.headers.get("x-encryption-session")
    if session_id is None:
        return payload

    try:
        return manager.encrypt_response(
            session_id=session_id,
            profile=profile,
            payload=payload.model_dump(mode="json"),
        )
    except EncryptionSessionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid encryption session",
        ) from exc
