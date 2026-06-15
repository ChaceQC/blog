from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.repositories.auth import AuthRepository
from app.services.auth import AuthenticatedUser, AuthenticationError, AuthService

SessionDependency = Annotated[AsyncSession, Depends(get_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]
BearerCredentials = Annotated[
    HTTPAuthorizationCredentials | None,
    Depends(HTTPBearer(auto_error=False)),
]


def get_auth_service(
    session: SessionDependency,
    settings: SettingsDependency,
) -> AuthService:
    return AuthService(
        repository=AuthRepository(session),
        settings=settings,
    )


AuthServiceDependency = Annotated[AuthService, Depends(get_auth_service)]


async def get_current_admin_user(
    credentials: BearerCredentials,
    service: AuthServiceDependency,
) -> AuthenticatedUser:
    if credentials is None:
        raise unauthorized_exception("missing bearer token")

    try:
        return await service.authenticate_access_token(
            access_token=credentials.credentials,
        )
    except AuthenticationError as exc:
        raise unauthorized_exception("invalid bearer token") from exc


CurrentAdminUserDependency = Annotated[
    AuthenticatedUser,
    Depends(get_current_admin_user),
]


def unauthorized_exception(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )
