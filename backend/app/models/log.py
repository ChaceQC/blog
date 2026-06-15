from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BIGINT_UNSIGNED, DATETIME_6, Base, pk_column


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = pk_column()
    actor_id: Mapped[int | None] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(BIGINT_UNSIGNED, nullable=True)
    before_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME_6,
        server_default=func.now(),
        nullable=False,
    )


class LoginLog(Base):
    __tablename__ = "login_logs"

    id: Mapped[int] = pk_column()
    user_id: Mapped[int | None] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    success: Mapped[bool] = mapped_column(default=False, nullable=False)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME_6,
        server_default=func.now(),
        nullable=False,
    )


class SecurityEvent(Base):
    __tablename__ = "security_events"

    id: Mapped[int] = pk_column()
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[int | None] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    detail_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME_6,
        server_default=func.now(),
        nullable=False,
    )
