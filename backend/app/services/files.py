import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol

from app.core.auth import utc_now
from app.core.storage import StorageProvider
from app.models.file import BlogFile
from app.services.file_errors import (
    FileAccessDeniedError,
    FileTooLargeError,
    FileValidationError,
    InvalidFileAccessTokenError,
    InvalidFileTypeError,
    InvalidFileVisibilityError,
    ManagedFileNotFoundError,
)
from app.services.file_read_models import (
    AdminFileRead,
    PublicFileRead,
    admin_file_read,
    public_file_read,
)
from app.services.file_storage import (
    article_render_reference_exists,
    create_thumbnail,
    iter_managed_storage_files,
    resolve_storage_path,
    storage_path_to_object_key,
    thumbnail_path,
)
from app.services.file_tokens import (
    ArticleRenderToken,
    create_admin_file_preview_token,
    create_article_render_token,
    sign_admin_preview_image_urls,
    sign_article_render_urls,
    sign_file_token,
    verify_admin_file_preview_token,
    verify_article_render_token,
    verify_file_token,
)
from app.services.file_uploads import (
    UploadFileCommand,
    build_object_key,
    can_reuse_existing_upload,
    extract_extension,
    normalize_original_name,
    read_image_size,
    validate_image_dimensions,
    validate_size,
    validate_type,
    validate_visibility,
    write_temp_file,
)

__all__ = (
    "ArticleRenderToken",
    "DeletedFileCleanupResult",
    "FileAccessDeniedError",
    "FileDownload",
    "FileService",
    "FileTooLargeError",
    "FileValidationError",
    "FileWithUsage",
    "InvalidFileAccessTokenError",
    "InvalidFileTypeError",
    "InvalidFileVisibilityError",
    "ManagedFileNotFoundError",
    "OrphanFileCleanupResult",
    "TemporaryFileAccess",
    "UploadFileCommand",
    "create_admin_file_preview_token",
    "create_article_render_token",
    "sign_admin_preview_image_urls",
    "sign_article_render_urls",
    "verify_admin_file_preview_token",
    "verify_article_render_token",
)


@dataclass(frozen=True)
class FileWithUsage:
    file: BlogFile
    usage_count: int

    def __getattr__(self, name: str) -> object:
        return getattr(self.file, name)


@dataclass(frozen=True)
class TemporaryFileAccess:
    file: BlogFile
    token: str
    expires_at: datetime


@dataclass(frozen=True)
class FileDownload:
    path: Path
    media_type: str
    filename: str


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


class FileService:
    def __init__(
        self,
        *,
        repository: FileRepositoryProtocol,
        storage: StorageProvider,
    ) -> None:
        self.repository = repository
        self.storage = storage

    async def list_files(self, *, limit: int, offset: int) -> list[FileWithUsage]:
        files = await self.repository.list_files(limit=limit, offset=offset)
        return [FileWithUsage(file=file, usage_count=count) for file, count in files]

    async def list_admin_files(
        self,
        *,
        limit: int,
        offset: int,
    ) -> list[AdminFileRead]:
        files = await self.list_files(limit=limit, offset=offset)
        return [self.admin_file_response(file) for file in files]

    def admin_file_response(self, file: FileWithUsage) -> AdminFileRead:
        return admin_file_read(file.file, usage_count=file.usage_count)

    async def list_public_files(
        self,
        *,
        limit: int,
        offset: int,
    ) -> list[PublicFileRead]:
        files = await self.repository.list_public_listed_files(
            limit=limit,
            offset=offset,
        )
        return [public_file_read(file) for file in files]

    async def count_public_files(self) -> int:
        return await self.repository.count_public_listed_files()

    async def upload_file(self, command: UploadFileCommand) -> FileWithUsage:
        validate_size(command.data, command.max_size_bytes)
        validate_visibility(command.visibility)

        original_name = normalize_original_name(command.original_name)
        extension = extract_extension(original_name)
        expected_mime = validate_type(
            extension=extension,
            content_type=command.content_type,
            data=command.data,
        )
        sha256 = hashlib.sha256(command.data).hexdigest()
        existing_file = await self.repository.get_file_by_sha256(sha256)
        if existing_file is not None and can_reuse_existing_upload(
            existing_file,
            command=command,
            original_name=original_name,
            expected_mime=expected_mime,
            extension=extension,
        ):
            return FileWithUsage(file=existing_file, usage_count=0)

        object_key = build_object_key(
            visibility=command.visibility,
            extension=extension,
            sha256=sha256,
        )
        width, height = read_image_size(command.data, expected_mime)
        validate_image_dimensions(width=width, height=height)
        temp_path = write_temp_file(command.data)
        try:
            stored_object = await self.storage.save(temp_path, object_key)
        finally:
            temp_path.unlink(missing_ok=True)

        file = await self.repository.create_file(
            storage="local",
            bucket=None,
            object_key=stored_object.object_key,
            public_url=stored_object.public_url,
            original_name=original_name,
            mime_type=expected_mime,
            extension=extension.removeprefix("."),
            size_bytes=stored_object.size_bytes,
            sha256=stored_object.sha256,
            width=width,
            height=height,
            alt_text=command.alt_text,
            uploader_id=command.uploader_id,
            visibility=command.visibility,
            public_listed=(
                command.public_listed and command.visibility == "public"
            ),
        )
        await self.repository.commit()
        await self.repository.refresh(file)
        return FileWithUsage(file=file, usage_count=0)

    async def cleanup_deleted_files(
        self,
        *,
        upload_root: Path,
        deleted_before: datetime,
        limit: int,
    ) -> DeletedFileCleanupResult:
        candidates = await self.repository.list_deleted_files_for_cleanup(
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

            await self.repository.delete_file_record(file.id)
            deleted_records += 1

        if deleted_records > 0:
            await self.repository.commit()

        return DeletedFileCleanupResult(
            scanned_files=len(candidates),
            deleted_records=deleted_records,
            deleted_objects=deleted_objects,
            missing_objects=missing_objects,
            skipped_files=skipped_files,
        )

    async def cleanup_orphan_files(
        self,
        *,
        upload_root: Path,
        limit: int,
        dry_run: bool = True,
    ) -> OrphanFileCleanupResult:
        tracked_object_keys = set(await self.repository.list_storage_object_keys())
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

    async def delete_file(self, file_id: int) -> FileWithUsage:
        file = await self.repository.get_file(file_id)
        if file is None:
            raise ManagedFileNotFoundError("file not found")

        file.status = "deleted"
        file.deleted_at = utc_now()
        await self.repository.commit()
        await self.repository.refresh(file)
        return FileWithUsage(file=file, usage_count=0)

    async def create_temporary_access(
        self,
        *,
        file_id: int,
        secret_key: str,
        expires_seconds: int,
    ) -> TemporaryFileAccess:
        file = await self.repository.get_file(file_id)
        if file is None:
            raise ManagedFileNotFoundError("file not found")
        if file.visibility != "public" or file.status != "active":
            raise FileAccessDeniedError("file is not public")

        expires_at = utc_now() + timedelta(seconds=expires_seconds)
        token = sign_file_token(
            file_id=file.id,
            sha256=file.sha256,
            expires_at=expires_at,
            secret_key=secret_key,
        )
        return TemporaryFileAccess(file=file, token=token, expires_at=expires_at)

    async def create_public_temporary_access(
        self,
        *,
        file_id: int,
        secret_key: str,
        expires_seconds: int,
    ) -> TemporaryFileAccess:
        access = await self.create_temporary_access(
            file_id=file_id,
            secret_key=secret_key,
            expires_seconds=expires_seconds,
        )
        if not access.file.public_listed:
            raise FileAccessDeniedError("file is not listed public")
        return access

    async def prepare_public_download(
        self,
        *,
        file_id: int,
        token: str,
        secret_key: str,
        upload_root: Path,
    ) -> FileDownload:
        file = await self.repository.get_file(file_id)
        if file is None:
            raise ManagedFileNotFoundError("file not found")
        if file.visibility != "public" or file.status != "active":
            raise FileAccessDeniedError("file is not public")
        if not verify_file_token(
            token,
            file_id=file.id,
            sha256=file.sha256,
            secret_key=secret_key,
        ):
            raise InvalidFileAccessTokenError("invalid temporary file token")

        path = resolve_storage_path(upload_root, file.object_key)
        if path is None or not path.is_file():
            raise ManagedFileNotFoundError("stored file not found")

        return FileDownload(
            path=path,
            media_type=file.mime_type,
            filename=file.original_name,
        )

    async def prepare_admin_download(
        self,
        *,
        file_id: int,
        upload_root: Path,
    ) -> FileDownload:
        file = await self.repository.get_file(file_id)
        if file is None:
            raise ManagedFileNotFoundError("file not found")
        if file.status != "active":
            raise FileAccessDeniedError("file is not downloadable")

        path = resolve_storage_path(upload_root, file.object_key, public_only=False)
        if path is None or not path.is_file():
            raise ManagedFileNotFoundError("stored file not found")

        return FileDownload(
            path=path,
            media_type=file.mime_type,
            filename=file.original_name,
        )

    async def prepare_article_render(
        self,
        *,
        file_id: int,
        post_slug: str,
        post_cover_file_id: int | None,
        post_content_md: str,
        post_content_html: str,
        upload_root: Path,
    ) -> FileDownload:
        file = await self.repository.get_file(file_id)
        if file is None:
            raise ManagedFileNotFoundError("file not found")
        if (
            file.visibility != "public"
            or file.status != "active"
            or not file.mime_type.startswith("image/")
        ):
            raise FileAccessDeniedError("file is not renderable")
        if not article_render_reference_exists(
            post_slug=post_slug,
            file_id=file.id,
            cover_file_id=post_cover_file_id,
            content_md=post_content_md,
            content_html=post_content_html,
        ):
            raise FileAccessDeniedError("file is not referenced by post")

        path = resolve_storage_path(upload_root, file.object_key)
        if path is None or not path.is_file():
            raise ManagedFileNotFoundError("stored file not found")

        return FileDownload(
            path=path,
            media_type=file.mime_type,
            filename=file.original_name,
        )

    async def prepare_article_thumbnail(
        self,
        *,
        file_id: int,
        post_slug: str,
        post_cover_file_id: int | None,
        post_content_md: str,
        post_content_html: str,
        upload_root: Path,
        max_side: int = 360,
    ) -> FileDownload:
        file = await self.repository.get_file(file_id)
        if file is None:
            raise ManagedFileNotFoundError("file not found")
        if (
            file.visibility != "public"
            or file.status != "active"
            or not file.mime_type.startswith("image/")
        ):
            raise FileAccessDeniedError("file is not thumbnailable")
        if not article_render_reference_exists(
            post_slug=post_slug,
            file_id=file.id,
            cover_file_id=post_cover_file_id,
            content_md=post_content_md,
            content_html=post_content_html,
        ):
            raise FileAccessDeniedError("file is not referenced by post")

        source_path = resolve_storage_path(upload_root, file.object_key)
        if source_path is None or not source_path.is_file():
            raise ManagedFileNotFoundError("stored file not found")

        file_thumbnail_path = thumbnail_path(upload_root, file)
        if not file_thumbnail_path.is_file():
            create_thumbnail(
                source_path=source_path,
                target_path=file_thumbnail_path,
                max_side=max_side,
            )

        return FileDownload(
            path=file_thumbnail_path,
            media_type="image/jpeg",
            filename=f"{Path(file.original_name).stem}-thumb.jpg",
        )

    async def prepare_admin_preview(
        self,
        *,
        file_id: int,
        token: str,
        expires: int,
        secret_key: str,
        upload_root: Path,
    ) -> FileDownload:
        file = await self.repository.get_file(file_id)
        if file is None:
            raise ManagedFileNotFoundError("file not found")
        if file.status != "active" or not file.mime_type.startswith("image/"):
            raise FileAccessDeniedError("file is not previewable")
        if not verify_admin_file_preview_token(
            token=token,
            expires=expires,
            file_id=file.id,
            secret_key=secret_key,
        ):
            raise InvalidFileAccessTokenError("invalid preview token")

        path = resolve_storage_path(upload_root, file.object_key, public_only=False)
        if path is None or not path.is_file():
            raise ManagedFileNotFoundError("stored file not found")

        return FileDownload(
            path=path,
            media_type=file.mime_type,
            filename=file.original_name,
        )

    async def prepare_admin_thumbnail(
        self,
        *,
        file_id: int,
        upload_root: Path,
        max_side: int = 360,
    ) -> FileDownload:
        file = await self.repository.get_file(file_id)
        if file is None:
            raise ManagedFileNotFoundError("file not found")
        if file.status != "active" or not file.mime_type.startswith("image/"):
            raise FileAccessDeniedError("file is not thumbnailable")

        source_path = resolve_storage_path(
            upload_root,
            file.object_key,
            public_only=False,
        )
        if source_path is None or not source_path.is_file():
            raise ManagedFileNotFoundError("stored file not found")

        file_thumbnail_path = thumbnail_path(upload_root, file)
        if not file_thumbnail_path.is_file():
            create_thumbnail(
                source_path=source_path,
                target_path=file_thumbnail_path,
                max_side=max_side,
            )

        return FileDownload(
            path=file_thumbnail_path,
            media_type="image/jpeg",
            filename=f"{Path(file.original_name).stem}-thumb.jpg",
        )
