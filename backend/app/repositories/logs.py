from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.log import AccessLog, AuditLog, LoginLog, SecurityEvent


class LogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_audit_logs(self, *, limit: int, offset: int) -> Sequence[AuditLog]:
        result = await self.session.execute(
            select(AuditLog)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(limit)
            .offset(offset),
        )
        return result.scalars().all()

    async def list_access_logs(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[AccessLog]:
        result = await self.session.execute(
            select(AccessLog)
            .order_by(AccessLog.created_at.desc(), AccessLog.id.desc())
            .limit(limit)
            .offset(offset),
        )
        return result.scalars().all()

    async def list_login_logs(self, *, limit: int, offset: int) -> Sequence[LoginLog]:
        result = await self.session.execute(
            select(LoginLog)
            .order_by(LoginLog.created_at.desc(), LoginLog.id.desc())
            .limit(limit)
            .offset(offset),
        )
        return result.scalars().all()

    async def list_security_events(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[SecurityEvent]:
        result = await self.session.execute(
            select(SecurityEvent)
            .order_by(SecurityEvent.created_at.desc(), SecurityEvent.id.desc())
            .limit(limit)
            .offset(offset),
        )
        return result.scalars().all()

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
    ) -> None:
        self.session.add(
            SecurityEvent(
                event_type=event_type,
                severity=severity,
                actor_id=actor_id,
                ip=ip,
                user_agent=user_agent,
                path=path,
                detail_json=detail_json,
            ),
        )

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
    ) -> None:
        self.session.add(
            AuditLog(
                actor_id=actor_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                before_json=before_json,
                after_json=after_json,
                ip=ip,
                user_agent=user_agent,
            ),
        )

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
    ) -> None:
        self.session.add(
            AccessLog(
                access_type=access_type,
                method=method,
                path=path,
                status_code=status_code,
                entity_type=entity_type,
                entity_id=entity_id,
                ip=ip,
                user_agent=user_agent,
                detail_json=detail_json,
            ),
        )

    async def commit(self) -> None:
        await self.session.commit()
