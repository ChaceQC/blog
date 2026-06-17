from fastapi import APIRouter, HTTPException, Request, status

from app.api.admin.dependencies import (
    EncryptionSessionManagerDependency,
    LogServiceDependency,
    RateLimitServiceDependency,
    SettingsDependency,
)
from app.api.admin.limits import enforce_rate_limit
from app.core.request import client_ip
from app.schemas.encryption import (
    CreateEncryptionSessionRequest,
    CreateEncryptionSessionResponse,
)
from app.services.encryption import EncryptionSessionError
from app.services.rate_limit import RateLimitRule

router = APIRouter(prefix="/encryption", tags=["admin-encryption"])


@router.post("/sessions", response_model=CreateEncryptionSessionResponse)
async def create_encryption_session(
    payload: CreateEncryptionSessionRequest,
    request: Request,
    manager: EncryptionSessionManagerDependency,
    settings: SettingsDependency,
    rate_limiter: RateLimitServiceDependency,
    logs: LogServiceDependency,
) -> CreateEncryptionSessionResponse:
    await enforce_rate_limit(
        request=request,
        limiter=rate_limiter,
        logs=logs,
        key=f"encryption-session:{client_ip(request) or 'unknown'}",
        rule=RateLimitRule(
            max_attempts=settings.encryption_session_rate_limit_max_attempts,
            window_seconds=settings.encryption_session_rate_limit_window_seconds,
        ),
        event_type="rate_limit.encryption_session",
        detail_json={"profile": "sensitive-v1"},
    )
    try:
        return await manager.create_session(
            client_public_key=payload.client_public_key,
            scope="admin",
        )
    except EncryptionSessionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid encryption public key",
        ) from exc
