from fastapi import APIRouter, HTTPException, status

from app.api.admin.dependencies import EncryptionSessionManagerDependency
from app.schemas.encryption import (
    CreateEncryptionSessionRequest,
    CreateEncryptionSessionResponse,
)
from app.services.encryption import EncryptionSessionError

router = APIRouter(prefix="/encryption", tags=["public-encryption"])


@router.post("/sessions", response_model=CreateEncryptionSessionResponse)
async def create_public_encryption_session(
    payload: CreateEncryptionSessionRequest,
    manager: EncryptionSessionManagerDependency,
) -> CreateEncryptionSessionResponse:
    try:
        return await manager.create_session(
            client_public_key=payload.client_public_key,
            scope="public",
        )
    except EncryptionSessionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid encryption public key",
        ) from exc
