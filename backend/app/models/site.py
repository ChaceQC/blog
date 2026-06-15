from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BIGINT_UNSIGNED, DATETIME_6, Base, TimestampMixin, pk_column


class SiteNavGroup(Base):
    __tablename__ = "site_nav_groups"

    id: Mapped[int] = pk_column()
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    visibility: Mapped[str] = mapped_column(
        String(32),
        default="public",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DATETIME_6,
        server_default=func.now(),
        nullable=False,
    )


class SiteNavItem(TimestampMixin, Base):
    __tablename__ = "site_nav_items"

    id: Mapped[int] = pk_column()
    group_id: Mapped[int | None] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("site_nav_groups.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    icon_file_id: Mapped[int | None] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("files.id", ondelete="SET NULL"),
        nullable=True,
    )
    icon_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tags_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    open_target: Mapped[str] = mapped_column(
        String(32),
        default="blank",
        nullable=False,
    )
    visibility: Mapped[str] = mapped_column(
        String(32),
        default="public",
        nullable=False,
    )
    click_count: Mapped[int] = mapped_column(BIGINT_UNSIGNED, default=0, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
