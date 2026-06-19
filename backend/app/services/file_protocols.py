from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from app.models.file import BlogFile


class FileRepositoryProtocol(Protocol):
    async def list_files(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[tuple[BlogFile, int]]: ...

    async def list_public_listed_files(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[BlogFile]: ...

    async def count_public_listed_files(self) -> int: ...

    async def get_file(self, file_id: int) -> BlogFile | None: ...

    async def get_file_by_sha256(self, sha256: str) -> BlogFile | None: ...

    async def list_storage_object_keys(self) -> Sequence[str]: ...

    async def list_deleted_files_for_cleanup(
        self,
        *,
        deleted_before: datetime,
        limit: int,
    ) -> Sequence[tuple[BlogFile, int]]: ...

    async def delete_file_record(self, file_id: int) -> None: ...

    async def create_file(
        self,
        *,
        storage: str,
        bucket: str | None,
        object_key: str,
        public_url: str | None,
        original_name: str,
        mime_type: str,
        extension: str,
        size_bytes: int,
        sha256: str,
        width: int | None,
        height: int | None,
        alt_text: str | None,
        uploader_id: int | None,
        visibility: str,
        public_listed: bool,
    ) -> BlogFile: ...

    async def commit(self) -> None: ...

    async def refresh(self, instance: object) -> None: ...
