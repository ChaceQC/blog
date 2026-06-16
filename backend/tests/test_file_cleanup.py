import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.services.files import FileService


class FakeCleanupRepository:
    def __init__(self, files: list[tuple[object, int]]) -> None:
        self.files = files
        self.deleted_ids: list[int] = []
        self.commit_count = 0

    async def list_deleted_files_for_cleanup(
        self,
        *,
        deleted_before: datetime,
        limit: int,
    ) -> list[tuple[object, int]]:
        assert deleted_before == datetime(2026, 6, 10, tzinfo=UTC)
        assert limit == 10
        return self.files[:limit]

    async def delete_file_record(self, file_id: int) -> None:
        self.deleted_ids.append(file_id)

    async def commit(self) -> None:
        self.commit_count += 1


class FakeStorage:
    pass


def test_cleanup_deleted_files_removes_unreferenced_local_files(tmp_path) -> None:
    source_file = tmp_path / "private" / "2026" / "06" / "deleted.pdf"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"%PDF-1.7\n")
    thumbnail_file = tmp_path / ".thumbs" / f"{'a' * 32}-360.jpg"
    thumbnail_file.parent.mkdir(parents=True)
    thumbnail_file.write_bytes(b"thumb")
    repository = FakeCleanupRepository(
        [
            (_file_item(1, "private/2026/06/deleted.pdf", "a" * 64), 0),
        ],
    )
    service = FileService(repository=repository, storage=FakeStorage())

    result = asyncio.run(
        service.cleanup_deleted_files(
            upload_root=tmp_path,
            deleted_before=datetime(2026, 6, 10, tzinfo=UTC),
            limit=10,
        ),
    )

    assert result.scanned_files == 1
    assert result.deleted_records == 1
    assert result.deleted_objects == 1
    assert result.missing_objects == 0
    assert result.skipped_files == 0
    assert repository.deleted_ids == [1]
    assert repository.commit_count == 1
    assert not source_file.exists()
    assert not thumbnail_file.exists()


def test_cleanup_deleted_files_removes_missing_object_record(tmp_path) -> None:
    repository = FakeCleanupRepository(
        [
            (_file_item(2, "public/2026/06/missing.png", "b" * 64), 0),
        ],
    )
    service = FileService(repository=repository, storage=FakeStorage())

    result = asyncio.run(
        service.cleanup_deleted_files(
            upload_root=tmp_path,
            deleted_before=datetime(2026, 6, 10, tzinfo=UTC),
            limit=10,
        ),
    )

    assert result.deleted_records == 1
    assert result.deleted_objects == 0
    assert result.missing_objects == 1
    assert result.skipped_files == 0
    assert repository.deleted_ids == [2]
    assert repository.commit_count == 1


def test_cleanup_deleted_files_skips_referenced_and_unsafe_paths(tmp_path) -> None:
    referenced = _file_item(3, "private/2026/06/referenced.pdf", "c" * 64)
    unsafe = _file_item(4, "../outside.pdf", "d" * 64)
    repository = FakeCleanupRepository([(referenced, 1), (unsafe, 0)])
    service = FileService(repository=repository, storage=FakeStorage())

    result = asyncio.run(
        service.cleanup_deleted_files(
            upload_root=tmp_path,
            deleted_before=datetime(2026, 6, 10, tzinfo=UTC),
            limit=10,
        ),
    )

    assert result.scanned_files == 2
    assert result.deleted_records == 0
    assert result.deleted_objects == 0
    assert result.missing_objects == 0
    assert result.skipped_files == 2
    assert repository.deleted_ids == []
    assert repository.commit_count == 0


def _file_item(file_id: int, object_key: str, sha256: str) -> object:
    return SimpleNamespace(
        id=file_id,
        object_key=object_key,
        sha256=sha256,
        status="deleted",
        deleted_at=datetime(2026, 6, 1, tzinfo=UTC) - timedelta(days=file_id),
    )
