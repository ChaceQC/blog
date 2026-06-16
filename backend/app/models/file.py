from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    BIGINT_UNSIGNED,
    DATETIME_6,
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    pk_column,
)


class BlogFile(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "files"
    __table_args__ = (
        Index("idx_files_uploader", "uploader_id"),
        Index("idx_files_mime", "mime_type"),
    )

    id: Mapped[int] = pk_column()
    storage: Mapped[str] = mapped_column(String(32), default="local", nullable=False)
    bucket: Mapped[str | None] = mapped_column(String(128), nullable=True)
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    public_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    extension: Mapped[str] = mapped_column(String(32), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BIGINT_UNSIGNED, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    alt_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    uploader_id: Mapped[int | None] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    visibility: Mapped[str] = mapped_column(
        String(32),
        default="public",
        nullable=False,
    )
    public_listed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class FileUsage(Base):
    __tablename__ = "file_usages"

    id: Mapped[int] = pk_column()
    file_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[int] = mapped_column(BIGINT_UNSIGNED, nullable=False)
    purpose: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME_6,
        server_default=func.now(),
        nullable=False,
    )
