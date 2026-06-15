from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.repositories.auth import AuthRepository
from app.schemas.auth import (
    AuthUserResponse,
    LoginRequest,
    LogoutRequest,
    LogoutResponse,
    RefreshTokenRequest,
    TokenPairResponse,
)
from app.services.auth import AuthenticationError, AuthService, TokenPair

router = APIRouter(prefix="/auth", tags=["admin-auth"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]


def get_auth_service(
    session: SessionDependency,
    settings: SettingsDependency,
) -> AuthService:
    return AuthService(
        repository=AuthRepository(session),
        settings=settings,
    )


AuthServiceDependency = Annotated[AuthService, Depends(get_auth_service)]


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


def _token_response(tokens: TokenPair) -> TokenPairResponse:
    return TokenPairResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
        user=AuthUserResponse(
            id=tokens.user.id,
            username=tokens.user.username,
            display_name=tokens.user.display_name,
            roles=tokens.user.roles,
            permissions=tokens.user.permissions,
        ),
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
