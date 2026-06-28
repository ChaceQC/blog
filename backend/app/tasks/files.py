from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.config import Settings, get_settings
from app.core.database import AsyncSessionLocal
from app.core.storage import LocalStorageProvider
from app.repositories.files import FileRepository
from app.services.files import (
    DeletedFileCleanupResult,
    FileService,
    OrphanFileCleanupResult,
)
from app.tasks.telemetry import start_task_telemetry


@dataclass(frozen=True)
class DeletedFileCleanupCommand:
    older_than_days: int
    limit: int
    now: datetime | None = None


@dataclass(frozen=True)
class OrphanFileCleanupCommand:
    limit: int
    dry_run: bool = True


async def cleanup_deleted_files(
    command: DeletedFileCleanupCommand,
    *,
    settings: Settings | None = None,
) -> DeletedFileCleanupResult:
    """清理已软删除且无引用的本地文件，供 CLI 或定时任务调用。"""
    telemetry = start_task_telemetry()
    resolved_settings = settings or get_settings()
    now = command.now or datetime.now(UTC)
    deleted_before = now - timedelta(days=command.older_than_days)
    try:
        async with AsyncSessionLocal() as session:
            service = FileService(
                repository=FileRepository(session),
                storage=LocalStorageProvider(resolved_settings.upload_root),
            )
            result = await service.cleanup_deleted_files(
                upload_root=resolved_settings.upload_root,
                deleted_before=deleted_before,
                limit=command.limit,
            )
    except Exception:
        telemetry.finish(task_name="cleanup-deleted-files", outcome="error")
        raise
    telemetry.finish(
        task_name="cleanup-deleted-files",
        outcome="ok",
        deleted_rows={"files": result.deleted_records},
    )
    return result


async def cleanup_orphan_files(
    command: OrphanFileCleanupCommand,
    *,
    settings: Settings | None = None,
) -> OrphanFileCleanupResult:
    """扫描本地孤儿文件；默认 dry-run，显式确认后才删除。"""
    telemetry = start_task_telemetry()
    resolved_settings = settings or get_settings()
    try:
        async with AsyncSessionLocal() as session:
            service = FileService(
                repository=FileRepository(session),
                storage=LocalStorageProvider(resolved_settings.upload_root),
            )
            result = await service.cleanup_orphan_files(
                upload_root=resolved_settings.upload_root,
                limit=command.limit,
                dry_run=command.dry_run,
            )
    except Exception:
        telemetry.finish(task_name="cleanup-orphan-files", outcome="error")
        raise
    telemetry.finish(
        task_name="cleanup-orphan-files",
        outcome="ok",
        deleted_rows={"orphan_files": result.deleted_files},
    )
    return result
