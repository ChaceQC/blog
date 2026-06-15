from fastapi import APIRouter, HTTPException, Request, status

from app.api.admin.dependencies import (
    AuthServiceDependency,
    CurrentAdminUserDependency,
)
from app.schemas.auth import (
    AuthUserResponse,
    LoginRequest,
    LogoutRequest,
    LogoutResponse,
    RefreshTokenRequest,
    TokenPairResponse,
)
from app.services.auth import AuthenticatedUser, AuthenticationError, TokenPair

router = APIRouter(prefix="/auth", tags=["admin-auth"])


@router.post("/login", response_model=TokenPairResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    service: AuthServiceDependency,
) -> TokenPairResponse:
    try:
        tokens = await service.login(
            username=payload.username,
            password=payload.password,
            ip=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except AuthenticationError as exc:
        raise _unauthorized() from exc
    return _token_response(tokens)


@router.post("/refresh", response_model=TokenPairResponse)
async def refresh(
    payload: RefreshTokenRequest,
    service: AuthServiceDependency,
) -> TokenPairResponse:
    try:
        tokens = await service.refresh(refresh_token=payload.refresh_token)
    except AuthenticationError as exc:
        raise _unauthorized() from exc
    return _token_response(tokens)


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    payload: LogoutRequest,
    service: AuthServiceDependency,
) -> LogoutResponse:
    await service.logout(refresh_token=payload.refresh_token)
    return LogoutResponse()


@router.get("/me", response_model=AuthUserResponse)
async def me(current_user: CurrentAdminUserDependency) -> AuthUserResponse:
    return _user_response(current_user)


def _token_response(tokens: TokenPair) -> TokenPairResponse:
    return TokenPairResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
        user=_user_response(tokens.user),
    )


def _user_response(user: AuthenticatedUser) -> AuthUserResponse:
    return AuthUserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        roles=user.roles,
        permissions=user.permissions,
    )


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _client_ip(request: Request) -> str | None:
    if request.client is None:
        return None
    return request.client.host
