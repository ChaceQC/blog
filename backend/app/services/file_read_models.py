from dataclasses import dataclass
from datetime import datetime

from app.models.file import BlogFile


@dataclass(frozen=True)
class AdminFileRead:
    id: int
    storage: str
    bucket: str | None
    object_key: str
    original_name: str
    mime_type: str
    extension: str
    size_bytes: int
    sha256: str
    width: int | None
    height: int | None
    alt_text: str | None
    uploader_id: int | None
    visibility: str
    public_listed: bool
    status: str
    usage_count: int
    created_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True)
class PublicFileRead:
    id: int
    original_name: str
    mime_type: str
    extension: str
    size_bytes: int
    width: int | None
    height: int | None
    alt_text: str | None
    created_at: datetime | None
    updated_at: datetime | None


def public_file_read(file: BlogFile) -> PublicFileRead:
    return PublicFileRead(
        id=file.id,
        original_name=file.original_name,
        mime_type=file.mime_type,
        extension=file.extension,
        size_bytes=file.size_bytes,
        width=file.width,
        height=file.height,
        alt_text=file.alt_text,
        created_at=file.created_at,
        updated_at=file.updated_at,
    )


def admin_file_read(file: BlogFile, *, usage_count: int) -> AdminFileRead:
    return AdminFileRead(
        id=file.id,
        storage=file.storage,
        bucket=file.bucket,
        object_key=file.object_key,
        original_name=file.original_name,
        mime_type=file.mime_type,
        extension=file.extension,
        size_bytes=file.size_bytes,
        sha256=file.sha256,
        width=file.width,
        height=file.height,
        alt_text=file.alt_text,
        uploader_id=file.uploader_id,
        visibility=file.visibility,
        public_listed=file.public_listed,
        status=file.status,
        usage_count=usage_count,
        created_at=file.created_at,
        updated_at=file.updated_at,
    )
