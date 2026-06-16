from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.config import Settings, get_settings
from app.core.database import AsyncSessionLocal
from app.core.storage import LocalStorageProvider
from app.repositories.files import FileRepository
from app.services.files import DeletedFileCleanupResult, FileService


@dataclass(frozen=True)
class DeletedFileCleanupCommand:
    older_than_days: int
    limit: int
    now: datetime | None = None


async def cleanup_deleted_files(
    command: DeletedFileCleanupCommand,
    *,
    settings: Settings | None = None,
) -> DeletedFileCleanupResult:
    """清理已软删除且无引用的本地文件，供 CLI 或定时任务调用。"""
    resolved_settings = settings or get_settings()
    now = command.now or datetime.now(UTC)
    deleted_before = now - timedelta(days=command.older_than_days)
    async with AsyncSessionLocal() as session:
        service = FileService(
            repository=FileRepository(session),
            storage=LocalStorageProvider(resolved_settings.upload_root),
        )
        return await service.cleanup_deleted_files(
            upload_root=resolved_settings.upload_root,
            deleted_before=deleted_before,
            limit=command.limit,
        )
