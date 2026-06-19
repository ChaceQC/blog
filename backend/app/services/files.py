import hashlib
from datetime import datetime, timedelta
from pathlib import Path

from app.core.auth import utc_now
from app.core.storage import StorageProvider
from app.services import file_downloads
from app.services.file_access import TemporaryFileAccess
from app.services.file_downloads import FileDownload
from app.services.file_errors import (
    FileAccessDeniedError,
    FileTooLargeError,
    FileValidationError,
    InvalidFileAccessTokenError,
    InvalidFileTypeError,
    InvalidFileVisibilityError,
    ManagedFileNotFoundError,
)
from app.services.file_maintenance import (
    DeletedFileCleanupResult,
    OrphanFileCleanupResult,
    cleanup_deleted_files,
    cleanup_orphan_files,
)
from app.services.file_protocols import FileRepositoryProtocol
from app.services.file_read_models import (
    AdminFileRead,
    PublicFileRead,
    admin_file_read,
    public_file_read,
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


class FileService:
    def __init__(
        self,
        *,
        repository: FileRepositoryProtocol,
        storage: StorageProvider,
    ) -> None:
        self.repository = repository
        self.storage = storage

    async def list_files(self, *, limit: int, offset: int) -> list[AdminFileRead]:
        files = await self.repository.list_files(limit=limit, offset=offset)
        return [admin_file_read(file, usage_count=count) for file, count in files]

    async def list_admin_files(
        self,
        *,
        limit: int,
        offset: int,
    ) -> list[AdminFileRead]:
        return await self.list_files(limit=limit, offset=offset)

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

    async def upload_file(self, command: UploadFileCommand) -> AdminFileRead:
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
            return admin_file_read(existing_file, usage_count=0)

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
        return admin_file_read(file, usage_count=0)

    async def cleanup_deleted_files(
        self,
        *,
        upload_root: Path,
        deleted_before: datetime,
        limit: int,
    ) -> DeletedFileCleanupResult:
        return await cleanup_deleted_files(
            self.repository,
            upload_root=upload_root,
            deleted_before=deleted_before,
            limit=limit,
        )

    async def cleanup_orphan_files(
        self,
        *,
        upload_root: Path,
        limit: int,
        dry_run: bool = True,
    ) -> OrphanFileCleanupResult:
        return await cleanup_orphan_files(
            self.repository,
            upload_root=upload_root,
            limit=limit,
            dry_run=dry_run,
        )

    async def delete_file(self, file_id: int) -> AdminFileRead:
        file = await self.repository.get_file(file_id)
        if file is None:
            raise ManagedFileNotFoundError("file not found")

        file.status = "deleted"
        file.deleted_at = utc_now()
        await self.repository.commit()
        await self.repository.refresh(file)
        return admin_file_read(file, usage_count=0)

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
        return await file_downloads.prepare_public_download(
            self.repository,
            file_id=file_id,
            token=token,
            secret_key=secret_key,
            upload_root=upload_root,
        )

    async def prepare_admin_download(
        self,
        *,
        file_id: int,
        upload_root: Path,
    ) -> FileDownload:
        return await file_downloads.prepare_admin_download(
            self.repository,
            file_id=file_id,
            upload_root=upload_root,
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
        return await file_downloads.prepare_article_render(
            self.repository,
            file_id=file_id,
            post_slug=post_slug,
            post_cover_file_id=post_cover_file_id,
            post_content_md=post_content_md,
            post_content_html=post_content_html,
            upload_root=upload_root,
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
        return await file_downloads.prepare_article_thumbnail(
            self.repository,
            file_id=file_id,
            post_slug=post_slug,
            post_cover_file_id=post_cover_file_id,
            post_content_md=post_content_md,
            post_content_html=post_content_html,
            upload_root=upload_root,
            max_side=max_side,
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
        return await file_downloads.prepare_admin_preview(
            self.repository,
            file_id=file_id,
            token=token,
            expires=expires,
            secret_key=secret_key,
            upload_root=upload_root,
        )

    async def prepare_admin_thumbnail(
        self,
        *,
        file_id: int,
        upload_root: Path,
        max_side: int = 360,
    ) -> FileDownload:
        return await file_downloads.prepare_admin_thumbnail(
            self.repository,
            file_id=file_id,
            upload_root=upload_root,
            max_side=max_side,
        )
