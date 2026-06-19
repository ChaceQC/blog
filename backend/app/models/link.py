from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BIGINT_UNSIGNED, DATETIME_6, Base, TimestampMixin, pk_column


class FriendLinkGroup(Base):
    __tablename__ = "friend_link_groups"

    id: Mapped[int] = pk_column()
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME_6,
        server_default=func.now(),
        nullable=False,
    )


class FriendLink(TimestampMixin, Base):
    __tablename__ = "friend_links"
    __table_args__ = (Index("idx_friend_links_status", "status"),)

    id: Mapped[int] = pk_column()
    group_id: Mapped[int | None] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("friend_link_groups.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    avatar_file_id: Mapped[int | None] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("files.id", ondelete="SET NULL"),
        nullable=True,
    )
    avatar_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rss_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DATETIME_6, nullable=True)
    last_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
