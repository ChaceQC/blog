from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.admin.dependencies import (
    AdminCsrfDependency,
    AuthServiceDependency,
    CurrentAdminUserDependency,
    EncryptionSessionManagerDependency,
    LogServiceDependency,
    RateLimitServiceDependency,
    SettingsDependency,
)
from app.api.admin.encrypted_response import (
    encrypted_response,
    require_encryption_session,
)
from app.api.admin.limits import enforce_rate_limit
from app.api.admin.session import (
    clear_admin_session_cookies,
    create_csrf_token,
    ensure_csrf_cookie,
    refresh_token_from_request,
    session_response,
    set_admin_session_cookies,
)
from app.core.encryption import EncryptionProfile
from app.core.request import client_ip
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    LogoutResponse,
    RefreshTokenRequest,
)
from app.schemas.encryption import EncryptedApiResponse
from app.services.auth import AuthenticationError
from app.services.rate_limit import RateLimitRule

router = APIRouter(prefix="/auth", tags=["admin-auth"])


@router.post("/login", response_model=EncryptedApiResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    service: AuthServiceDependency,
    settings: SettingsDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    rate_limiter: RateLimitServiceDependency,
    logs: LogServiceDependency,
) -> EncryptedApiResponse:
    require_encryption_session(request)
    limit_key = (
        f"admin-login:{client_ip(request) or 'unknown'}:"
        f"{payload.username.casefold()}"
    )
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
        detail_json={"username": payload.username},
    )
    try:
        tokens = await service.login(
            username=payload.username,
            password=payload.password,
            ip=client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
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


@router.post("/refresh", response_model=EncryptedApiResponse)
async def refresh(
    request: Request,
    response: Response,
    service: AuthServiceDependency,
    settings: SettingsDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    payload: RefreshTokenRequest | None = None,
) -> EncryptedApiResponse:
    require_encryption_session(request)
    refresh_token = (
        payload.refresh_token if payload is not None else None
    ) or refresh_token_from_request(request)
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
    payload: LogoutRequest | None = None,
) -> LogoutResponse:
    refresh_token = (
        payload.refresh_token if payload is not None else None
    ) or refresh_token_from_request(request)
    if refresh_token is not None:
        await service.logout(refresh_token=refresh_token)
    clear_admin_session_cookies(response, settings=settings)
    return LogoutResponse()


@router.get("/me", response_model=EncryptedApiResponse)
async def me(
    current_user: CurrentAdminUserDependency,
    request: Request,
    response: Response,
    settings: SettingsDependency,
    encryption_manager: EncryptionSessionManagerDependency,
) -> EncryptedApiResponse:
    require_encryption_session(request)
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
