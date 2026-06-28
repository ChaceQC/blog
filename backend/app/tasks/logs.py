from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.database import AsyncSessionLocal
from app.repositories.logs import LogRepository
from app.services.log_retention import LogRetentionResult, LogRetentionService
from app.tasks.telemetry import start_task_telemetry


@dataclass(frozen=True)
class LogCleanupCommand:
    access_days: int
    audit_days: int
    login_days: int
    security_days: int
    limit: int
    now: datetime | None = None


async def cleanup_logs(command: LogCleanupCommand) -> LogRetentionResult:
    """按保留天数清理日志表，供 CLI 或定时任务调用。"""
    telemetry = start_task_telemetry()
    cleanup_time = command.now or datetime.now(UTC)
    try:
        async with AsyncSessionLocal() as session:
            service = LogRetentionService(repository=LogRepository(session))
            result = await service.cleanup_old_logs(
                now=cleanup_time,
                access_days=command.access_days,
                audit_days=command.audit_days,
                login_days=command.login_days,
                security_days=command.security_days,
                limit=command.limit,
            )
    except Exception:
        telemetry.finish(task_name="cleanup-logs", outcome="error")
        raise
    telemetry.finish(
        task_name="cleanup-logs",
        outcome="ok",
        deleted_rows={
            "access": result.access_logs,
            "audit": result.audit_logs,
            "login": result.login_logs,
            "security": result.security_events,
        },
    )
    return result
