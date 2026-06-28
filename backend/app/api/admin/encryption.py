from fastapi import APIRouter, HTTPException, Request, WebSocket, status

from app.api.dependencies import (
    EncryptionSessionManagerDependency,
    LogServiceDependency,
    RateLimitServiceDependency,
    SaltLeaseServiceDependency,
    SettingsDependency,
)
from app.api.encryption_salts import salt_websocket
from app.api.limits import enforce_rate_limit
from app.api.telemetry import record_encryption_session_telemetry
from app.core.request import client_ip
from app.schemas.encryption import (
    CreateEncryptionSessionRequest,
    CreateEncryptionSessionResponse,
)
from app.services.encryption import (
    ActiveEncryptionSessionLimitExceeded,
    EncryptionSessionError,
)
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
    ip = client_ip(request)
    try:
        await enforce_rate_limit(
            request=request,
            limiter=rate_limiter,
            logs=logs,
            key=f"encryption-session:{ip or 'unknown'}",
            rule=RateLimitRule(
                max_attempts=settings.encryption_session_rate_limit_max_attempts,
                window_seconds=settings.encryption_session_rate_limit_window_seconds,
            ),
            event_type="rate_limit.encryption_session",
            detail_json={"profile": "sensitive-v1"},
        )
    except HTTPException as exc:
        if exc.status_code != status.HTTP_429_TOO_MANY_REQUESTS:
            raise
        _record_rejected_session(
            request=request,
            settings=settings,
            reason="rate_limited",
        )
        raise
    try:
        session = await manager.create_session(
            client_public_key=payload.client_public_key,
            scope="admin",
            client_ip=ip,
            active_session_limit=(
                settings.admin_encryption_session_active_limit_per_ip
            ),
        )
    except ActiveEncryptionSessionLimitExceeded as exc:
        await logs.record_security_event(
            event_type="rate_limit.encryption_session_active",
            severity="medium",
            ip=ip,
            user_agent=request.headers.get("user-agent"),
            path=str(request.url.path),
            detail_json={"scope": "admin", "profile": "sensitive-v1"},
        )
        telemetry = getattr(request.app.state, "telemetry_service", None)
        if telemetry is not None:
            record_encryption_session_telemetry(
                telemetry,
                scope="admin",
                profile="sensitive-v1",
                outcome="rejected",
                active_limit=settings.admin_encryption_session_active_limit_per_ip,
                reason="active_limited",
            )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many active encryption sessions",
        ) from exc
    except EncryptionSessionError as exc:
        telemetry = getattr(request.app.state, "telemetry_service", None)
        if telemetry is not None:
            record_encryption_session_telemetry(
                telemetry,
                scope="admin",
                profile="sensitive-v1",
                outcome="rejected",
                reason="invalid_public_key",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid encryption public key",
        ) from exc
    telemetry = getattr(request.app.state, "telemetry_service", None)
    if telemetry is not None:
        record_encryption_session_telemetry(
            telemetry,
            scope="admin",
            profile="sensitive-v1",
            outcome="created",
            active_limit=settings.admin_encryption_session_active_limit_per_ip,
        )
    return session


@router.websocket("/salts")
async def admin_encryption_salts(
    websocket: WebSocket,
    manager: EncryptionSessionManagerDependency,
    salt_leases: SaltLeaseServiceDependency,
) -> None:
    await salt_websocket(
        websocket,
        scope="admin",
        manager=manager,
        salt_leases=salt_leases,
    )


def _record_rejected_session(
    *,
    request: Request,
    settings: SettingsDependency,
    reason: str,
) -> None:
    telemetry = getattr(request.app.state, "telemetry_service", None)
    if telemetry is None:
        return
    record_encryption_session_telemetry(
        telemetry,
        scope="admin",
        profile="sensitive-v1",
        outcome="rejected",
        active_limit=settings.admin_encryption_session_active_limit_per_ip,
        reason=reason,
    )
