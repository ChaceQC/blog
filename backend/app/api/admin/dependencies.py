from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.admin.session import (
    access_token_from_request,
    csrf_token_from_request,
    verify_csrf_tokens,
)
from app.api.dependencies import (
    EncryptionSessionManagerDependency,
    SessionDependency,
    SettingsDependency,
)
from app.api.encrypted_response import validate_encryption_session
from app.core.encryption import EncryptionProfile
from app.policies.auth import AuthPolicy
from app.repositories.auth import AuthRepository
from app.repositories.link_groups import LinkGroupRepository
from app.services.auth import AuthenticatedUser, AuthenticationError, AuthService
from app.services.link_groups import LinkGroupService

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


def get_link_group_service(session: SessionDependency) -> LinkGroupService:
    return LinkGroupService(repository=LinkGroupRepository(session))


LinkGroupServiceDependency = Annotated[
    LinkGroupService,
    Depends(get_link_group_service),
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


async def get_current_admin_user_with_encryption(
    credentials: BearerCredentials,
    request: Request,
    service: AuthServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
) -> AuthenticatedUser:
    await validate_encryption_session(
        request,
        manager=encryption_manager,
        profile=EncryptionProfile.SENSITIVE,
    )
    return await get_current_admin_user(
        credentials=credentials,
        request=request,
        service=service,
    )


EncryptedCurrentAdminUserDependency = Annotated[
    AuthenticatedUser,
    Depends(get_current_admin_user_with_encryption),
]


async def validate_admin_content_encryption_session(
    request: Request,
    encryption_manager: EncryptionSessionManagerDependency,
) -> None:
    await validate_encryption_session(
        request,
        manager=encryption_manager,
        profile=EncryptionProfile.CONTENT,
    )


AdminContentEncryptionDependency = Annotated[
    None,
    Depends(validate_admin_content_encryption_session),
]


async def validate_admin_sensitive_encryption_session(
    request: Request,
    encryption_manager: EncryptionSessionManagerDependency,
) -> None:
    await validate_encryption_session(
        request,
        manager=encryption_manager,
        profile=EncryptionProfile.SENSITIVE,
    )


AdminSensitiveEncryptionDependency = Annotated[
    None,
    Depends(validate_admin_sensitive_encryption_session),
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
