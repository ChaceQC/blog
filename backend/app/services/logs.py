from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from app.api.telemetry import record_access_telemetry
from app.core.config import get_settings
from app.models.log import AccessLog, AuditLog, LoginLog, SecurityEvent
from app.services.access_log_dedupe import (
    AccessLogDedupeBackend,
    AccessLogDedupeRule,
    InMemoryAccessLogDedupeBackend,
    RedisAccessLogDedupeBackend,
    build_access_log_dedupe_key,
    create_access_log_dedupe_backend,
)
from app.services.log_sanitizers import (
    sanitize_access_log_detail,
    sanitize_audit_log_payload,
    sanitize_log_ip,
    sanitize_log_path,
    sanitize_log_user_agent,
    sanitize_security_event_detail,
)

__all__ = (
    "AccessLogDedupeBackend",
    "AccessLogDedupeRule",
    "AccessLogRead",
    "AuditLogRead",
    "InMemoryAccessLogDedupeBackend",
    "LoginLogRead",
    "LogService",
    "RedisAccessLogDedupeBackend",
    "SecurityEventRead",
    "build_access_log_dedupe_key",
    "create_access_log_dedupe_backend",
    "sanitize_access_log_detail",
    "sanitize_audit_log_payload",
    "sanitize_security_event_detail",
)


@dataclass(frozen=True)
class AuditLogRead:
    id: int
    actor_id: int | None
    action: str
    entity_type: str
    entity_id: int | None
    before_json: dict[str, Any] | None
    after_json: dict[str, Any] | None
    ip: str | None
    user_agent: str | None
    created_at: datetime


@dataclass(frozen=True)
class AccessLogRead:
    id: int
    access_type: str
    method: str
    path: str
    status_code: int
    entity_type: str | None
    entity_id: int | None
    ip: str | None
    user_agent: str | None
    detail_json: dict[str, Any] | None
    created_at: datetime


@dataclass(frozen=True)
class LoginLogRead:
    id: int
    user_id: int | None
    username: str
    success: bool
    ip: str | None
    user_agent: str | None
    reason: str | None
    created_at: datetime


@dataclass(frozen=True)
class SecurityEventRead:
    id: int
    event_type: str
    severity: str
    actor_id: int | None
    ip: str | None
    user_agent: str | None
    path: str | None
    detail_json: dict[str, Any] | None
    created_at: datetime


class LogRepositoryProtocol(Protocol):
    async def list_audit_logs(self, *, limit: int, offset: int) -> Sequence[AuditLog]:
        ...

    async def count_audit_logs(self) -> int: ...

    async def list_access_logs(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[AccessLog]: ...

    async def count_access_logs(self) -> int: ...

    async def list_login_logs(self, *, limit: int, offset: int) -> Sequence[LoginLog]:
        ...

    async def count_login_logs(self) -> int: ...

    async def list_security_events(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[SecurityEvent]: ...

    async def count_security_events(self) -> int: ...

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

    async def record_audit_log(
        self,
        *,
        action: str,
        entity_type: str,
        entity_id: int | None,
        actor_id: int | None,
        ip: str | None,
        user_agent: str | None,
        before_json: dict[str, Any] | None,
        after_json: dict[str, Any] | None,
    ) -> None: ...

    async def record_access_log(
        self,
        *,
        access_type: str,
        method: str,
        path: str,
        status_code: int,
        entity_type: str | None,
        entity_id: int | None,
        ip: str | None,
        user_agent: str | None,
        detail_json: dict[str, Any] | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class LogService:
    def __init__(
        self,
        repository: LogRepositoryProtocol,
        dedupe_backend: AccessLogDedupeBackend | None = None,
        telemetry: object | None = None,
    ) -> None:
        self.repository = repository
        self._dedupe_backend = dedupe_backend or InMemoryAccessLogDedupeBackend()
        self._telemetry = telemetry

    async def list_audit_logs(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[AuditLogRead]:
        logs = await self.repository.list_audit_logs(limit=limit, offset=offset)
        return [audit_log_read(log) for log in logs]

    async def count_audit_logs(self) -> int:
        return await self.repository.count_audit_logs()

    async def list_access_logs(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[AccessLogRead]:
        logs = await self.repository.list_access_logs(limit=limit, offset=offset)
        return [access_log_read(log) for log in logs]

    async def count_access_logs(self) -> int:
        return await self.repository.count_access_logs()

    async def list_login_logs(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[LoginLogRead]:
        logs = await self.repository.list_login_logs(limit=limit, offset=offset)
        return [login_log_read(log) for log in logs]

    async def count_login_logs(self) -> int:
        return await self.repository.count_login_logs()

    async def list_security_events(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[SecurityEventRead]:
        events = await self.repository.list_security_events(
            limit=limit,
            offset=offset,
        )
        return [security_event_read(event) for event in events]

    async def count_security_events(self) -> int:
        return await self.repository.count_security_events()

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
            ip=sanitize_log_ip(ip),
            user_agent=sanitize_log_user_agent(user_agent),
            path=sanitize_log_path(path),
            detail_json=sanitize_security_event_detail(detail_json),
        )
        await self.repository.commit()

    async def record_audit_log(
        self,
        *,
        action: str,
        entity_type: str,
        entity_id: int | None,
        actor_id: int | None,
        ip: str | None,
        user_agent: str | None,
        before_json: dict[str, Any] | None = None,
        after_json: dict[str, Any] | None = None,
    ) -> None:
        await self.repository.record_audit_log(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
            ip=sanitize_log_ip(ip),
            user_agent=sanitize_log_user_agent(user_agent),
            before_json=sanitize_audit_log_payload(before_json),
            after_json=sanitize_audit_log_payload(after_json),
        )
        await self.repository.commit()

    async def record_access_log(
        self,
        *,
        access_type: str,
        method: str,
        path: str,
        status_code: int,
        ip: str | None,
        user_agent: str | None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        detail_json: dict[str, Any] | None = None,
    ) -> bool:
        if not self._should_record_access_log(
            method=method,
            path=path,
            status_code=status_code,
            ip=ip,
        ):
            return False
        await self.repository.record_access_log(
            access_type=access_type,
            method=method,
            path=sanitize_log_path(path),
            status_code=status_code,
            entity_type=entity_type,
            entity_id=entity_id,
            ip=sanitize_log_ip(ip),
            user_agent=sanitize_log_user_agent(user_agent),
            detail_json=sanitize_access_log_detail(detail_json),
        )
        await self.repository.commit()
        if self._telemetry is not None:
            record_access_telemetry(
                self._telemetry,
                access_type=access_type,
                status_code=status_code,
                entity_type=entity_type,
                entity_id=entity_id,
            )
        return True

    def _should_record_access_log(
        self,
        *,
        method: str,
        path: str,
        status_code: int,
        ip: str | None,
    ) -> bool:
        settings = get_settings()
        if status_code < 200 or status_code >= 400:
            return True
        if method.upper() not in {"GET", "HEAD"}:
            return True
        if settings.access_log_dedupe_seconds <= 0:
            return True

        dedupe_key = build_access_log_dedupe_key(
            ip=ip,
            method=method,
            path=path,
        )
        return self._dedupe_backend.should_record(
            key=dedupe_key,
            rule=AccessLogDedupeRule(
                window_seconds=settings.access_log_dedupe_seconds,
            ),
        )


def audit_log_read(log: AuditLog) -> AuditLogRead:
    return AuditLogRead(
        id=log.id,
        actor_id=log.actor_id,
        action=log.action,
        entity_type=log.entity_type,
        entity_id=log.entity_id,
        before_json=sanitize_audit_log_payload(log.before_json),
        after_json=sanitize_audit_log_payload(log.after_json),
        ip=log.ip,
        user_agent=log.user_agent,
        created_at=log.created_at,
    )


def access_log_read(log: AccessLog) -> AccessLogRead:
    return AccessLogRead(
        id=log.id,
        access_type=log.access_type,
        method=log.method,
        path=log.path,
        status_code=log.status_code,
        entity_type=log.entity_type,
        entity_id=log.entity_id,
        ip=log.ip,
        user_agent=log.user_agent,
        detail_json=sanitize_access_log_detail(log.detail_json),
        created_at=log.created_at,
    )


def login_log_read(log: LoginLog) -> LoginLogRead:
    return LoginLogRead(
        id=log.id,
        user_id=log.user_id,
        username=log.username,
        success=log.success,
        ip=log.ip,
        user_agent=log.user_agent,
        reason=log.reason,
        created_at=log.created_at,
    )


def security_event_read(event: SecurityEvent) -> SecurityEventRead:
    return SecurityEventRead(
        id=event.id,
        event_type=event.event_type,
        severity=event.severity,
        actor_id=event.actor_id,
        ip=event.ip,
        user_agent=event.user_agent,
        path=event.path,
        detail_json=sanitize_security_event_detail(event.detail_json),
        created_at=event.created_at,
    )
