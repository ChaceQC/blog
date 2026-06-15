from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BIGINT_UNSIGNED, DATETIME_6, Base, pk_column


class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[int] = pk_column()
    key_name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    value_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    group_name: Mapped[str] = mapped_column(String(64), nullable=False)
    is_public: Mapped[bool] = mapped_column(default=False, nullable=False)
    updated_by: Mapped[int | None] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(DATETIME_6, nullable=False)
