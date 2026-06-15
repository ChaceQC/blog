from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.admin.dependencies import LogServiceDependency, require_admin_permission
from app.schemas.logs import (
    AuditLogItem,
    AuditLogListResponse,
    LoginLogItem,
    LoginLogListResponse,
    SecurityEventItem,
    SecurityEventListResponse,
)
from app.services.auth import AuthenticatedUser

router = APIRouter(tags=["admin-logs"])
AuditReaderDependency = Annotated[
    AuthenticatedUser,
    Depends(require_admin_permission("audit_log:read")),
]


@router.get("/audit-logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    _: AuditReaderDependency,
    service: LogServiceDependency,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> AuditLogListResponse:
    logs = await service.list_audit_logs(limit=limit, offset=offset)
    return AuditLogListResponse(
        items=[AuditLogItem.model_validate(item) for item in logs],
    )


@router.get("/login-logs", response_model=LoginLogListResponse)
async def list_login_logs(
    _: AuditReaderDependency,
    service: LogServiceDependency,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> LoginLogListResponse:
    logs = await service.list_login_logs(limit=limit, offset=offset)
    return LoginLogListResponse(
        items=[LoginLogItem.model_validate(item) for item in logs],
    )


@router.get("/security-events", response_model=SecurityEventListResponse)
async def list_security_events(
    _: AuditReaderDependency,
    service: LogServiceDependency,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> SecurityEventListResponse:
    events = await service.list_security_events(limit=limit, offset=offset)
    return SecurityEventListResponse(
        items=[SecurityEventItem.model_validate(item) for item in events],
    )
