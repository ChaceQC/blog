from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.admin.dependencies import (
    AdminCsrfDependency,
    AuthServiceDependency,
    EncryptedCurrentAdminUserDependency,
)
from app.api.admin.session import (
    clear_admin_session_cookies,
    create_csrf_token,
    ensure_csrf_cookie,
    refresh_token_from_request,
    session_response,
    set_admin_session_cookies,
)
from app.api.dependencies import (
    EncryptionSessionManagerDependency,
    LogServiceDependency,
    RateLimitServiceDependency,
    SettingsDependency,
)
from app.api.encrypted_response import (
    encrypted_response,
    encryption_esid_salt_id_from_request,
    encryption_sid_from_request,
    mark_encryption_session_validated,
    require_encryption_session,
    validate_encryption_session,
)
from app.api.limits import enforce_rate_limit
from app.api.telemetry import record_auth_login_telemetry
from app.core.encryption import EncryptionProfile
from app.core.request import client_ip
from app.schemas.auth import (
    LoginCapsuleRequest,
    LogoutResponse,
)
from app.schemas.encryption import EncryptedApiResponse
from app.services.auth import AuthenticationError
from app.services.encryption import EncryptionSessionError
from app.services.rate_limit import RateLimitRule

router = APIRouter(prefix="/auth", tags=["admin-auth"])


@router.post("/login", response_model=EncryptedApiResponse)
async def login(
    payload: LoginCapsuleRequest,
    request: Request,
    response: Response,
    service: AuthServiceDependency,
    settings: SettingsDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    rate_limiter: RateLimitServiceDependency,
    logs: LogServiceDependency,
) -> EncryptedApiResponse:
    session_id = require_encryption_session(request)
    try:
        login_payload = await encryption_manager.decrypt_login_capsule(
            session_id=session_id,
            esid=encryption_sid_from_request(request),
            esid_salt_id=encryption_esid_salt_id_from_request(request),
            payload=payload,
            method=request.method,
            path=str(request.url.path),
        )
    except EncryptionSessionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid login capsule",
        ) from exc
    mark_encryption_session_validated(
        request,
        session_id=session_id,
        scope="admin",
        profile=EncryptionProfile.SENSITIVE,
    )

    client = client_ip(request) or "unknown"
    try:
        await enforce_rate_limit(
            request=request,
            limiter=rate_limiter,
            logs=logs,
            key=f"admin-login-ip:{client}",
            rule=RateLimitRule(
                max_attempts=settings.admin_login_rate_limit_max_attempts * 3,
                window_seconds=settings.admin_login_rate_limit_window_seconds,
            ),
            event_type="rate_limit.admin_login",
            detail_json={"credential": "ip"},
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            telemetry = getattr(request.app.state, "telemetry_service", None)
            if telemetry is not None:
                record_auth_login_telemetry(
                    telemetry,
                    outcome="limited",
                    reason_class="rate_limited",
                )
        raise
    limit_key = (
        f"admin-login:{client}:"
        f"{login_payload.username.casefold()}"
    )
    try:
        await enforce_rate_limit(
            request=request,
            limiter=rate_limiter,
            logs=logs,
            key=limit_key,
            rule=RateLimitRule(
                max_attempts=settings.admin_login_rate_limit_max_attempts,
                window_seconds=settings.admin_login_rate_limit_window_seconds,
            ),
            event_type="rate_limit.admin_login",
            detail_json={"credential": "username"},
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            telemetry = getattr(request.app.state, "telemetry_service", None)
            if telemetry is not None:
                record_auth_login_telemetry(
                    telemetry,
                    outcome="limited",
                    reason_class="rate_limited",
                )
        raise
    try:
        tokens = await service.login(
            username=login_payload.username,
            password=login_payload.password,
            ip=client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except AuthenticationError as exc:
        telemetry = getattr(request.app.state, "telemetry_service", None)
        if telemetry is not None:
            record_auth_login_telemetry(
                telemetry,
                outcome="error",
                reason_class="invalid_credentials",
            )
        raise _unauthorized() from exc

    csrf_token = create_csrf_token()
    set_admin_session_cookies(
        response,
        tokens=tokens,
        csrf_token=csrf_token,
        settings=settings,
    )
    telemetry = getattr(request.app.state, "telemetry_service", None)
    if telemetry is not None:
        record_auth_login_telemetry(
            telemetry,
            outcome="ok",
            reason_class="success",
            actor_id=tokens.user.id,
        )
    return await encrypted_response(
        session_response(
            user=tokens.user,
            csrf_token=csrf_token,
            expires_in=tokens.expires_in,
        ),
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.SENSITIVE,
    )


@router.post("/refresh", response_model=EncryptedApiResponse)
async def refresh(
    request: Request,
    response: Response,
    service: AuthServiceDependency,
    settings: SettingsDependency,
    encryption_manager: EncryptionSessionManagerDependency,
) -> EncryptedApiResponse:
    await validate_encryption_session(
        request,
        manager=encryption_manager,
        profile=EncryptionProfile.SENSITIVE,
    )
    refresh_token = refresh_token_from_request(request)
    if refresh_token is None:
        raise _unauthorized()

    try:
        tokens = await service.refresh(refresh_token=refresh_token)
    except AuthenticationError as exc:
        raise _unauthorized() from exc

    csrf_token = create_csrf_token()
    set_admin_session_cookies(
        response,
        tokens=tokens,
        csrf_token=csrf_token,
        settings=settings,
    )
    return await encrypted_response(
        session_response(
            user=tokens.user,
            csrf_token=csrf_token,
            expires_in=tokens.expires_in,
        ),
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.SENSITIVE,
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    response: Response,
    _: AdminCsrfDependency,
    service: AuthServiceDependency,
    settings: SettingsDependency,
) -> LogoutResponse:
    refresh_token = refresh_token_from_request(request)
    if refresh_token is not None:
        await service.logout(refresh_token=refresh_token)
    clear_admin_session_cookies(response, settings=settings)
    return LogoutResponse()


@router.get("/me", response_model=EncryptedApiResponse)
async def me(
    current_user: EncryptedCurrentAdminUserDependency,
    request: Request,
    response: Response,
    settings: SettingsDependency,
    encryption_manager: EncryptionSessionManagerDependency,
) -> EncryptedApiResponse:
    csrf_token = ensure_csrf_cookie(request, response, settings=settings)
    return await encrypted_response(
        session_response(
            user=current_user,
            csrf_token=csrf_token,
            expires_in=settings.access_token_expire_minutes * 60,
        ),
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.SENSITIVE,
    )


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
