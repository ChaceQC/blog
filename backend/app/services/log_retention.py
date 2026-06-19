from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol


class DeleteLogBatchFunc(Protocol):
    async def __call__(
        self,
        *,
        created_before: datetime,
        limit: int,
    ) -> int: ...


class LogRetentionRepositoryProtocol(Protocol):
    async def delete_access_logs_before(
        self,
        *,
        created_before: datetime,
        limit: int,
    ) -> int: ...

    async def delete_audit_logs_before(
        self,
        *,
        created_before: datetime,
        limit: int,
    ) -> int: ...

    async def delete_login_logs_before(
        self,
        *,
        created_before: datetime,
        limit: int,
    ) -> int: ...

    async def delete_security_events_before(
        self,
        *,
        created_before: datetime,
        limit: int,
    ) -> int: ...

    async def commit(self) -> None: ...


@dataclass(frozen=True)
class LogRetentionResult:
    access_logs: int
    audit_logs: int
    login_logs: int
    security_events: int

    @property
    def total_deleted(self) -> int:
        return (
            self.access_logs
            + self.audit_logs
            + self.login_logs
            + self.security_events
        )


class LogRetentionService:
    def __init__(self, repository: LogRetentionRepositoryProtocol) -> None:
        self.repository = repository

    async def cleanup_old_logs(
        self,
        *,
        now: datetime,
        access_days: int,
        audit_days: int,
        login_days: int,
        security_days: int,
        limit: int,
    ) -> LogRetentionResult:
        access_logs = await self._delete_before(
            days=access_days,
            now=now,
            limit=limit,
            delete_func=self.repository.delete_access_logs_before,
        )
        audit_logs = await self._delete_before(
            days=audit_days,
            now=now,
            limit=limit,
            delete_func=self.repository.delete_audit_logs_before,
        )
        login_logs = await self._delete_before(
            days=login_days,
            now=now,
            limit=limit,
            delete_func=self.repository.delete_login_logs_before,
        )
        security_events = await self._delete_before(
            days=security_days,
            now=now,
            limit=limit,
            delete_func=self.repository.delete_security_events_before,
        )
        result = LogRetentionResult(
            access_logs=access_logs,
            audit_logs=audit_logs,
            login_logs=login_logs,
            security_events=security_events,
        )
        if result.total_deleted > 0:
            await self.repository.commit()
        return result

    async def _delete_before(
        self,
        *,
        days: int,
        now: datetime,
        limit: int,
        delete_func: DeleteLogBatchFunc,
    ) -> int:
        if days <= 0:
            return 0
        created_before = now - timedelta(days=days)
        return await delete_func(created_before=created_before, limit=limit)
