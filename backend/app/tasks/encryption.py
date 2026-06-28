from datetime import UTC, datetime

from app.core.config import Settings, get_settings
from app.core.database import AsyncSessionLocal
from app.repositories.encryption import EncryptionSessionRepository
from app.services.encryption import EncryptionSessionManager
from app.tasks.telemetry import start_task_telemetry


async def cleanup_expired_encryption_sessions(
    *,
    now: datetime | None = None,
    settings: Settings | None = None,
) -> int:
    """清理已过期的应用层加密会话，供 CLI 或定时任务调用。"""
    telemetry = start_task_telemetry()
    cleanup_time = now or datetime.now(UTC)
    try:
        async with AsyncSessionLocal() as session:
            manager = EncryptionSessionManager(
                repository=EncryptionSessionRepository(session),
                settings=settings or get_settings(),
            )
            deleted_count = await manager.cleanup_expired_sessions(now=cleanup_time)
    except Exception:
        telemetry.finish(task_name="cleanup-encryption-sessions", outcome="error")
        raise
    telemetry.finish(
        task_name="cleanup-encryption-sessions",
        outcome="ok",
        deleted_rows={"sessions": deleted_count},
    )
    return deleted_count
