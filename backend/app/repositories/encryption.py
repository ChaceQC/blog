from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import EncryptionSession


class EncryptionSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_session(
        self,
        *,
        session_id: str,
        scope: str,
        client_ip: str | None,
        key_material: bytes,
        expires_at: datetime,
    ) -> EncryptionSession:
        session = EncryptionSession(
            session_id=session_id,
            scope=scope,
            client_ip=client_ip,
            key_material=key_material,
            expires_at=expires_at,
        )
        self.session.add(session)
        await self.session.flush()
        return session

    async def count_active_sessions_by_client(
        self,
        *,
        scope: str,
        client_ip: str,
        now: datetime,
    ) -> int:
        result = await self.session.execute(
            select(func.count(EncryptionSession.id)).where(
                EncryptionSession.scope == scope,
                EncryptionSession.client_ip == client_ip,
                EncryptionSession.expires_at > now,
            ),
        )
        return int(result.scalar_one())

    async def get_active_session(
        self,
        *,
        session_id: str,
        now: datetime,
    ) -> EncryptionSession | None:
        result = await self.session.execute(
            select(EncryptionSession).where(
                EncryptionSession.session_id == session_id,
                EncryptionSession.expires_at > now,
            ),
        )
        return result.scalar_one_or_none()

    async def delete_expired_sessions(self, *, now: datetime) -> int:
        result = await self.session.execute(
            delete(EncryptionSession).where(EncryptionSession.expires_at <= now),
        )
        return result.rowcount or 0

    async def commit(self) -> None:
        await self.session.commit()
