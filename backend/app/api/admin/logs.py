from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.api.admin.dependencies import (
    require_admin_permission,
)
from app.api.dependencies import (
    EncryptionSessionManagerDependency,
    LogServiceDependency,
)
from app.api.encrypted_response import encrypted_response
from app.core.encryption import EncryptionProfile
from app.schemas.encryption import EncryptedApiResponse
from app.schemas.logs import (
    AccessLogItem,
    AccessLogListResponse,
    AuditLogItem,
    AuditLogListResponse,
    LoginLogItem,
    LoginLogListResponse,
    SecurityEventItem,
    SecurityEventListResponse,
)
from app.schemas.pagination import PAGE_OFFSET_MAX
from app.services.auth import AuthenticatedUser
from app.services.encryption import EncryptionSessionManager

router = APIRouter(tags=["admin-logs"])
AuditReaderDependency = Annotated[
    AuthenticatedUser,
    Depends(require_admin_permission("audit_log:read")),
]


@router.get("/audit-logs", response_model=EncryptedApiResponse)
async def list_audit_logs(
    _: AuditReaderDependency,
    request: Request,
    service: LogServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=PAGE_OFFSET_MAX),
) -> EncryptedApiResponse:
    logs = await service.list_audit_logs(limit=limit, offset=offset)
    return await _logs_response(
        AuditLogListResponse(
            items=[AuditLogItem.model_validate(item) for item in logs],
        ),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.get("/access-logs", response_model=EncryptedApiResponse)
async def list_access_logs(
    _: AuditReaderDependency,
    request: Request,
    service: LogServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=PAGE_OFFSET_MAX),
) -> EncryptedApiResponse:
    logs = await service.list_access_logs(limit=limit, offset=offset)
    return await _logs_response(
        AccessLogListResponse(
            items=[AccessLogItem.model_validate(item) for item in logs],
        ),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.get("/login-logs", response_model=EncryptedApiResponse)
async def list_login_logs(
    _: AuditReaderDependency,
    request: Request,
    service: LogServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=PAGE_OFFSET_MAX),
) -> EncryptedApiResponse:
    logs = await service.list_login_logs(limit=limit, offset=offset)
    return await _logs_response(
        LoginLogListResponse(
            items=[LoginLogItem.model_validate(item) for item in logs],
        ),
        request=request,
        encryption_manager=encryption_manager,
    )


@router.get("/security-events", response_model=EncryptedApiResponse)
async def list_security_events(
    _: AuditReaderDependency,
    request: Request,
    service: LogServiceDependency,
    encryption_manager: EncryptionSessionManagerDependency,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=PAGE_OFFSET_MAX),
) -> EncryptedApiResponse:
    events = await service.list_security_events(limit=limit, offset=offset)
    return await _logs_response(
        SecurityEventListResponse(
            items=[SecurityEventItem.model_validate(item) for item in events],
        ),
        request=request,
        encryption_manager=encryption_manager,
    )


async def _logs_response(
    payload: (
        AccessLogListResponse
        | AuditLogListResponse
        | LoginLogListResponse
        | SecurityEventListResponse
    ),
    *,
    request: Request,
    encryption_manager: EncryptionSessionManager,
) -> EncryptedApiResponse:
    return await encrypted_response(
        payload,
        request=request,
        manager=encryption_manager,
        profile=EncryptionProfile.SENSITIVE,
    )
