from collections.abc import Sequence
from typing import Any, Protocol

from app.models.log import AuditLog, LoginLog, SecurityEvent


class LogRepositoryProtocol(Protocol):
    async def list_audit_logs(self, *, limit: int, offset: int) -> Sequence[AuditLog]:
        ...

    async def list_login_logs(self, *, limit: int, offset: int) -> Sequence[LoginLog]:
        ...

    async def list_security_events(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[SecurityEvent]: ...

    async def record_security_event(
        self,
        *,
        event_type: str,
        severity: str,
        actor_id: int | None,
        ip: str | None,
        user_agent: str | None,
        path: str | None,
        detail_json: dict[str, Any] | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class LogService:
    def __init__(self, repository: LogRepositoryProtocol) -> None:
        self.repository = repository

    async def list_audit_logs(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[AuditLog]:
        return await self.repository.list_audit_logs(limit=limit, offset=offset)

    async def list_login_logs(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[LoginLog]:
        return await self.repository.list_login_logs(limit=limit, offset=offset)

    async def list_security_events(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[SecurityEvent]:
        return await self.repository.list_security_events(limit=limit, offset=offset)

    async def record_security_event(
        self,
        *,
        event_type: str,
        severity: str,
        ip: str | None,
        user_agent: str | None,
        path: str | None,
        detail_json: dict[str, Any] | None,
        actor_id: int | None = None,
    ) -> None:
        await self.repository.record_security_event(
            event_type=event_type,
            severity=severity,
            actor_id=actor_id,
            ip=ip,
            user_agent=user_agent,
            path=path,
            detail_json=detail_json,
        )
        await self.repository.commit()
