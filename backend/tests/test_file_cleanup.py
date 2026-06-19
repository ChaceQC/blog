import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.services.files import FileService, FileValidationError, UploadFileCommand


class FakeCleanupRepository:
    def __init__(
        self,
        files: list[tuple[object, int]],
        object_keys: list[str] | None = None,
    ) -> None:
        self.files = files
        self.object_keys = object_keys or []
        self.deleted_ids: list[int] = []
        self.commit_count = 0

    async def list_storage_object_keys(self) -> list[str]:
        return self.object_keys

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

    async def get_file_by_sha256(self, sha256: str) -> object | None:
        return getattr(self, "existing_file", None)

    async def create_file(self, **payload: object) -> object:
        self.created_payload = payload
        return SimpleNamespace(
            id=99,
            status="active",
            created_at=datetime(2026, 6, 19, tzinfo=UTC),
            updated_at=datetime(2026, 6, 19, tzinfo=UTC),
            **payload,
        )

    async def refresh(self, instance: object) -> None:
        return None


class FakeStorage:
    async def save(self, source_path, object_key: str) -> object:
        data = source_path.read_bytes()
        return SimpleNamespace(
            object_key=object_key,
            public_url=None,
            size_bytes=len(data),
            sha256="e" * 64,
        )


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


def test_cleanup_orphan_files_dry_run_keeps_local_files(tmp_path) -> None:
    tracked_file = tmp_path / "public" / "2026" / "06" / "tracked.png"
    orphan_file = tmp_path / "private" / "2026" / "06" / "orphan.pdf"
    thumbnail_file = tmp_path / ".thumbs" / "orphan-thumb.jpg"
    tracked_file.parent.mkdir(parents=True)
    orphan_file.parent.mkdir(parents=True)
    thumbnail_file.parent.mkdir(parents=True)
    tracked_file.write_bytes(b"\x89PNG\r\n\x1a\n")
    orphan_file.write_bytes(b"%PDF-1.7\n")
    thumbnail_file.write_bytes(b"thumb")
    repository = FakeCleanupRepository(
        [],
        object_keys=["public/2026/06/tracked.png"],
    )
    service = FileService(repository=repository, storage=FakeStorage())

    result = asyncio.run(
        service.cleanup_orphan_files(
            upload_root=tmp_path,
            limit=10,
            dry_run=True,
        ),
    )

    assert result.scanned_files == 2
    assert result.tracked_files == 1
    assert result.orphan_files == 1
    assert result.deleted_files == 0
    assert result.skipped_files == 0
    assert result.dry_run is True
    assert result.orphan_object_keys == ("private/2026/06/orphan.pdf",)
    assert orphan_file.exists()
    assert thumbnail_file.exists()


def test_cleanup_orphan_files_delete_removes_only_untracked_managed_files(
    tmp_path,
) -> None:
    tracked_file = tmp_path / "public" / "2026" / "06" / "tracked.png"
    orphan_file = tmp_path / "private" / "2026" / "06" / "orphan.pdf"
    unknown_file = tmp_path / "manual" / "note.txt"
    tracked_file.parent.mkdir(parents=True)
    orphan_file.parent.mkdir(parents=True)
    unknown_file.parent.mkdir(parents=True)
    tracked_file.write_bytes(b"\x89PNG\r\n\x1a\n")
    orphan_file.write_bytes(b"%PDF-1.7\n")
    unknown_file.write_text("keep", encoding="utf-8")
    repository = FakeCleanupRepository(
        [],
        object_keys=["public/2026/06/tracked.png"],
    )
    service = FileService(repository=repository, storage=FakeStorage())

    result = asyncio.run(
        service.cleanup_orphan_files(
            upload_root=tmp_path,
            limit=10,
            dry_run=False,
        ),
    )

    assert result.scanned_files == 2
    assert result.tracked_files == 1
    assert result.orphan_files == 1
    assert result.deleted_files == 1
    assert result.skipped_files == 0
    assert tracked_file.exists()
    assert not orphan_file.exists()
    assert unknown_file.exists()
    assert repository.commit_count == 0


def test_cleanup_orphan_files_respects_scan_limit(tmp_path) -> None:
    for index in range(3):
        path = tmp_path / "public" / "2026" / "06" / f"orphan-{index}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\x89PNG\r\n\x1a\n")
    repository = FakeCleanupRepository([], object_keys=[])
    service = FileService(repository=repository, storage=FakeStorage())

    result = asyncio.run(
        service.cleanup_orphan_files(
            upload_root=tmp_path,
            limit=2,
            dry_run=True,
        ),
    )

    assert result.scanned_files == 2
    assert result.orphan_files == 2
    assert len(result.orphan_object_keys) == 2


def test_upload_rejects_image_with_too_many_pixels() -> None:
    repository = FakeCleanupRepository([])
    service = FileService(repository=repository, storage=FakeStorage())

    with pytest.raises(FileValidationError):
        asyncio.run(
            service.upload_file(
                UploadFileCommand(
                    original_name="huge.png",
                    content_type="image/png",
                    data=_png_header(width=12001, height=12001),
                    visibility="public",
                    public_listed=False,
                    uploader_id=1,
                    alt_text=None,
                    max_size_bytes=1024,
                ),
            ),
        )


def test_upload_reuses_existing_file_only_when_metadata_matches() -> None:
    existing = _uploaded_file_item(
        file_id=7,
        visibility="public",
        public_listed=True,
        original_name="same.pdf",
        mime_type="application/pdf",
        extension="pdf",
        alt_text="资料",
    )
    repository = FakeCleanupRepository([])
    repository.existing_file = existing
    service = FileService(repository=repository, storage=FakeStorage())

    result = asyncio.run(
        service.upload_file(
            UploadFileCommand(
                original_name="same.pdf",
                content_type="application/pdf",
                data=b"%PDF-1.7\n",
                visibility="public",
                public_listed=True,
                uploader_id=1,
                alt_text="资料",
                max_size_bytes=1024,
            ),
        ),
    )

    assert result.id == existing.id
    assert result.usage_count == 0
    assert not hasattr(repository, "created_payload")


def test_upload_creates_new_record_when_duplicate_visibility_differs() -> None:
    repository = FakeCleanupRepository([])
    repository.existing_file = _uploaded_file_item(
        file_id=7,
        visibility="private",
        public_listed=False,
        original_name="same.pdf",
        mime_type="application/pdf",
        extension="pdf",
        alt_text=None,
    )
    service = FileService(repository=repository, storage=FakeStorage())

    result = asyncio.run(
        service.upload_file(
            UploadFileCommand(
                original_name="same.pdf",
                content_type="application/pdf",
                data=b"%PDF-1.7\n",
                visibility="public",
                public_listed=True,
                uploader_id=1,
                alt_text=None,
                max_size_bytes=1024,
            ),
        ),
    )

    assert result.id == 99
    assert result.usage_count == 0
    assert repository.created_payload["visibility"] == "public"
    assert repository.created_payload["public_listed"] is True


def _png_header(*, width: int, height: int) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + b"\x08\x02\x00\x00\x00"
        + b"\x90wS\xde"
    )


def _file_item(file_id: int, object_key: str, sha256: str) -> object:
    return SimpleNamespace(
        id=file_id,
        object_key=object_key,
        sha256=sha256,
        status="deleted",
        deleted_at=datetime(2026, 6, 1, tzinfo=UTC) - timedelta(days=file_id),
    )


def _uploaded_file_item(file_id: int, **overrides: object) -> object:
    values = {
        "id": file_id,
        "storage": "local",
        "bucket": None,
        "object_key": "public/2026/06/same.pdf",
        "public_url": None,
        "original_name": "same.pdf",
        "mime_type": "application/pdf",
        "extension": "pdf",
        "size_bytes": 9,
        "sha256": "e" * 64,
        "width": None,
        "height": None,
        "alt_text": None,
        "uploader_id": 1,
        "visibility": "public",
        "public_listed": True,
        "status": "active",
        "created_at": datetime(2026, 6, 19, tzinfo=UTC),
        "updated_at": datetime(2026, 6, 19, tzinfo=UTC),
    }
    values.update(overrides)
    return SimpleNamespace(**values)
