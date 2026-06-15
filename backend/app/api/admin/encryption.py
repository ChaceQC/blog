from fastapi import APIRouter, HTTPException, status

from app.api.admin.dependencies import EncryptionSessionManagerDependency
from app.schemas.encryption import (
    CreateEncryptionSessionRequest,
    CreateEncryptionSessionResponse,
)
from app.services.encryption import EncryptionSessionError

router = APIRouter(prefix="/encryption", tags=["admin-encryption"])


@router.post("/sessions", response_model=CreateEncryptionSessionResponse)
async def create_encryption_session(
    payload: CreateEncryptionSessionRequest,
    manager: EncryptionSessionManagerDependency,
) -> CreateEncryptionSessionResponse:
    try:
        return await manager.create_session(client_public_key=payload.client_public_key)
    except EncryptionSessionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid encryption public key",
        ) from exc
