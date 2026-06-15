from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.log import AuditLog, LoginLog, SecurityEvent


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

    async def commit(self) -> None:
        await self.session.commit()
