from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.models.file import BlogFile
from app.services.file_errors import (
    FileAccessDeniedError,
    InvalidFileAccessTokenError,
    ManagedFileNotFoundError,
)
from app.services.file_storage import (
    article_render_reference_exists,
    create_thumbnail,
    resolve_storage_path,
    thumbnail_path,
)
from app.services.file_tokens import (
    verify_admin_file_preview_token,
    verify_file_token,
)


@dataclass(frozen=True)
class FileDownload:
    path: Path
    media_type: str
    filename: str


class FileDownloadRepository(Protocol):
    async def get_file(self, file_id: int) -> BlogFile | None: ...


async def prepare_public_download(
    repository: FileDownloadRepository,
    *,
    file_id: int,
    token: str,
    secret_key: str,
    upload_root: Path,
) -> FileDownload:
    file = await _active_file(repository, file_id=file_id)
    if file.visibility != "public":
        raise FileAccessDeniedError("file is not public")
    if not verify_file_token(
        token,
        file_id=file.id,
        sha256=file.sha256,
        secret_key=secret_key,
    ):
        raise InvalidFileAccessTokenError("invalid temporary file token")

    return _stored_download(file, upload_root=upload_root)


async def prepare_admin_download(
    repository: FileDownloadRepository,
    *,
    file_id: int,
    upload_root: Path,
) -> FileDownload:
    file = await _active_file(repository, file_id=file_id)
    return _stored_download(file, upload_root=upload_root, public_only=False)


async def prepare_article_render(
    repository: FileDownloadRepository,
    *,
    file_id: int,
    post_slug: str,
    post_cover_file_id: int | None,
    post_content_md: str,
    post_content_html: str,
    upload_root: Path,
) -> FileDownload:
    file = await _active_image_file(repository, file_id=file_id)
    _ensure_public_file(file)
    _ensure_article_reference(
        file,
        post_slug=post_slug,
        post_cover_file_id=post_cover_file_id,
        post_content_md=post_content_md,
        post_content_html=post_content_html,
    )
    return _stored_download(file, upload_root=upload_root)


async def prepare_article_thumbnail(
    repository: FileDownloadRepository,
    *,
    file_id: int,
    post_slug: str,
    post_cover_file_id: int | None,
    post_content_md: str,
    post_content_html: str,
    upload_root: Path,
    max_side: int = 360,
) -> FileDownload:
    file = await _active_image_file(repository, file_id=file_id)
    _ensure_public_file(file)
    _ensure_article_reference(
        file,
        post_slug=post_slug,
        post_cover_file_id=post_cover_file_id,
        post_content_md=post_content_md,
        post_content_html=post_content_html,
    )
    return _thumbnail_download(
        file,
        upload_root=upload_root,
        max_side=max_side,
        public_only=True,
    )


async def prepare_admin_preview(
    repository: FileDownloadRepository,
    *,
    file_id: int,
    token: str,
    expires: int,
    secret_key: str,
    upload_root: Path,
) -> FileDownload:
    file = await _active_image_file(repository, file_id=file_id)
    if not verify_admin_file_preview_token(
        token=token,
        expires=expires,
        file_id=file.id,
        secret_key=secret_key,
    ):
        raise InvalidFileAccessTokenError("invalid preview token")
    return _stored_download(file, upload_root=upload_root, public_only=False)


async def prepare_admin_thumbnail(
    repository: FileDownloadRepository,
    *,
    file_id: int,
    upload_root: Path,
    max_side: int = 360,
) -> FileDownload:
    file = await _active_image_file(repository, file_id=file_id)
    return _thumbnail_download(
        file,
        upload_root=upload_root,
        max_side=max_side,
        public_only=False,
    )


async def _active_file(
    repository: FileDownloadRepository,
    *,
    file_id: int,
) -> BlogFile:
    file = await repository.get_file(file_id)
    if file is None:
        raise ManagedFileNotFoundError("file not found")
    if file.status != "active":
        raise FileAccessDeniedError("file is not downloadable")
    return file


async def _active_image_file(
    repository: FileDownloadRepository,
    *,
    file_id: int,
) -> BlogFile:
    file = await _active_file(repository, file_id=file_id)
    if not file.mime_type.startswith("image/"):
        raise FileAccessDeniedError("file is not renderable")
    return file


def _ensure_article_reference(
    file: BlogFile,
    *,
    post_slug: str,
    post_cover_file_id: int | None,
    post_content_md: str,
    post_content_html: str,
) -> None:
    if not article_render_reference_exists(
        post_slug=post_slug,
        file_id=file.id,
        cover_file_id=post_cover_file_id,
        content_md=post_content_md,
        content_html=post_content_html,
    ):
        raise FileAccessDeniedError("file is not referenced by post")


def _ensure_public_file(file: BlogFile) -> None:
    if file.visibility != "public":
        raise FileAccessDeniedError("file is not public")


def _stored_download(
    file: BlogFile,
    *,
    upload_root: Path,
    public_only: bool = True,
) -> FileDownload:
    path = resolve_storage_path(
        upload_root,
        file.object_key,
        public_only=public_only,
    )
    if path is None or not path.is_file():
        raise ManagedFileNotFoundError("stored file not found")
    return FileDownload(
        path=path,
        media_type=file.mime_type,
        filename=file.original_name,
    )


def _thumbnail_download(
    file: BlogFile,
    *,
    upload_root: Path,
    max_side: int,
    public_only: bool,
) -> FileDownload:
    source_path = resolve_storage_path(
        upload_root,
        file.object_key,
        public_only=public_only,
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
