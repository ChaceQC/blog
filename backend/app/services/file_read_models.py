from dataclasses import dataclass
from datetime import datetime

from app.models.file import BlogFile


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
