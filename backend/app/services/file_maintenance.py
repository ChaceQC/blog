from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from app.models.file import BlogFile
from app.services.file_storage import (
    iter_managed_storage_files,
    resolve_storage_path,
    storage_path_to_object_key,
    thumbnail_path,
)


@dataclass(frozen=True)
class DeletedFileCleanupResult:
    scanned_files: int
    deleted_records: int
    deleted_objects: int
    missing_objects: int
    skipped_files: int


@dataclass(frozen=True)
class OrphanFileCleanupResult:
    scanned_files: int
    tracked_files: int
    orphan_files: int
    deleted_files: int
    skipped_files: int
    dry_run: bool
    orphan_object_keys: tuple[str, ...]


class FileMaintenanceRepository(Protocol):
    async def list_storage_object_keys(self) -> Sequence[str]: ...

    async def list_deleted_files_for_cleanup(
        self,
        *,
        deleted_before: datetime,
        limit: int,
    ) -> Sequence[tuple[BlogFile, int]]: ...

    async def delete_file_record(self, file_id: int) -> None: ...

    async def commit(self) -> None: ...


async def cleanup_deleted_files(
    repository: FileMaintenanceRepository,
    *,
    upload_root: Path,
    deleted_before: datetime,
    limit: int,
) -> DeletedFileCleanupResult:
    candidates = await repository.list_deleted_files_for_cleanup(
        deleted_before=deleted_before,
        limit=limit,
    )
    deleted_records = 0
    deleted_objects = 0
    missing_objects = 0
    skipped_files = 0

    for file, usage_count in candidates:
        if usage_count > 0:
            skipped_files += 1
            continue

        path = resolve_storage_path(
            upload_root,
            file.object_key,
            public_only=False,
        )
        if path is None:
            skipped_files += 1
            continue

        if path.is_file():
            path.unlink()
            deleted_objects += 1
        else:
            missing_objects += 1

        file_thumbnail_path = thumbnail_path(upload_root, file)
        if file_thumbnail_path.is_file():
            file_thumbnail_path.unlink()

        await repository.delete_file_record(file.id)
        deleted_records += 1

    if deleted_records > 0:
        await repository.commit()

    return DeletedFileCleanupResult(
        scanned_files=len(candidates),
        deleted_records=deleted_records,
        deleted_objects=deleted_objects,
        missing_objects=missing_objects,
        skipped_files=skipped_files,
    )


async def cleanup_orphan_files(
    repository: FileMaintenanceRepository,
    *,
    upload_root: Path,
    limit: int,
    dry_run: bool = True,
) -> OrphanFileCleanupResult:
    tracked_object_keys = set(await repository.list_storage_object_keys())
    scanned_files = 0
    tracked_files = 0
    orphan_files = 0
    deleted_files = 0
    skipped_files = 0
    orphan_object_keys: list[str] = []

    for path in iter_managed_storage_files(upload_root):
        if scanned_files >= limit:
            break
        scanned_files += 1

        object_key = storage_path_to_object_key(upload_root, path)
        if object_key is None:
            skipped_files += 1
            continue

        if object_key in tracked_object_keys:
            tracked_files += 1
            continue

        orphan_files += 1
        orphan_object_keys.append(object_key)
        if dry_run:
            continue

        resolved_path = resolve_storage_path(
            upload_root,
            object_key,
            public_only=False,
        )
        if resolved_path != path:
            skipped_files += 1
            continue
        path.unlink()
        deleted_files += 1

    return OrphanFileCleanupResult(
        scanned_files=scanned_files,
        tracked_files=tracked_files,
        orphan_files=orphan_files,
        deleted_files=deleted_files,
        skipped_files=skipped_files,
        dry_run=dry_run,
        orphan_object_keys=tuple(orphan_object_keys),
    )
