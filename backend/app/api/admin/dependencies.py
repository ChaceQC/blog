from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.session import (
    access_token_from_request,
    csrf_token_from_request,
    verify_csrf_tokens,
)
from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.core.storage import LocalStorageProvider
from app.policies.auth import AuthPolicy
from app.repositories.auth import AuthRepository
from app.repositories.content import ContentRepository
from app.repositories.encryption import EncryptionSessionRepository
from app.repositories.files import FileRepository
from app.repositories.link_groups import LinkGroupRepository
from app.repositories.links import LinkRepository
from app.repositories.logs import LogRepository
from app.repositories.settings import SettingRepository
from app.services.auth import AuthenticatedUser, AuthenticationError, AuthService
from app.services.content import ContentService
from app.services.encryption import EncryptionSessionManager
from app.services.files import FileService
from app.services.link_groups import LinkGroupService
from app.services.links import LinkService
from app.services.logs import LogService
from app.services.rate_limit import RateLimitService, create_rate_limit_service
from app.services.settings import SettingService

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


def get_content_service(session: SessionDependency) -> ContentService:
    return ContentService(repository=ContentRepository(session))


ContentServiceDependency = Annotated[ContentService, Depends(get_content_service)]


def get_file_service(
    session: SessionDependency,
    settings: SettingsDependency,
) -> FileService:
    return FileService(
        repository=FileRepository(session),
        storage=LocalStorageProvider(settings.upload_root),
    )


FileServiceDependency = Annotated[FileService, Depends(get_file_service)]


def get_link_service(session: SessionDependency) -> LinkService:
    return LinkService(repository=LinkRepository(session))


LinkServiceDependency = Annotated[LinkService, Depends(get_link_service)]


def get_link_group_service(session: SessionDependency) -> LinkGroupService:
    return LinkGroupService(repository=LinkGroupRepository(session))


LinkGroupServiceDependency = Annotated[
    LinkGroupService,
    Depends(get_link_group_service),
]


def get_encryption_session_manager(
    session: SessionDependency,
    settings: SettingsDependency,
) -> EncryptionSessionManager:
    return EncryptionSessionManager(
        repository=EncryptionSessionRepository(session),
        settings=settings,
    )


EncryptionSessionManagerDependency = Annotated[
    EncryptionSessionManager,
    Depends(get_encryption_session_manager),
]


def get_log_service(session: SessionDependency) -> LogService:
    return LogService(repository=LogRepository(session))


LogServiceDependency = Annotated[LogService, Depends(get_log_service)]


def get_setting_service(session: SessionDependency) -> SettingService:
    return SettingService(repository=SettingRepository(session))


SettingServiceDependency = Annotated[SettingService, Depends(get_setting_service)]


_rate_limit_service: RateLimitService | None = None
_rate_limit_signature: tuple[str, str | None, str] | None = None


def get_rate_limit_service(settings: SettingsDependency) -> RateLimitService:
    global _rate_limit_service, _rate_limit_signature
    signature = (
        settings.rate_limit_backend,
        settings.redis_url,
        settings.redis_key_prefix,
    )
    if _rate_limit_service is None or _rate_limit_signature != signature:
        _rate_limit_service = create_rate_limit_service(settings)
        _rate_limit_signature = signature
    return _rate_limit_service


RateLimitServiceDependency = Annotated[
    RateLimitService,
    Depends(get_rate_limit_service),
]


async def get_current_admin_user(
    credentials: BearerCredentials,
    request: Request,
    service: AuthServiceDependency,
) -> AuthenticatedUser:
    access_token = (
        credentials.credentials
        if credentials is not None
        else access_token_from_request(request)
    )
    if access_token is None:
        raise unauthorized_exception("missing bearer token")

    try:
        return await service.authenticate_access_token(
            access_token=access_token,
        )
    except AuthenticationError as exc:
        raise unauthorized_exception("invalid bearer token") from exc


CurrentAdminUserDependency = Annotated[
    AuthenticatedUser,
    Depends(get_current_admin_user),
]


def verify_admin_csrf(request: Request) -> None:
    verify_csrf_tokens(
        header_token=request.headers.get("x-csrf-token"),
        cookie_token=csrf_token_from_request(request),
    )


AdminCsrfDependency = Annotated[None, Depends(verify_admin_csrf)]


def require_admin_permission(
    code: str,
) -> Callable[[AuthenticatedUser], Awaitable[AuthenticatedUser]]:
    async def dependency(
        current_user: CurrentAdminUserDependency,
    ) -> AuthenticatedUser:
        if not AuthPolicy().has_permission(set(current_user.permissions), code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="missing permission",
            )
        return current_user

    return dependency


def unauthorized_exception(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )
