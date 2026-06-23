from datetime import datetime

from sqlalchemy import ForeignKey, LargeBinary, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    BIGINT_UNSIGNED,
    DATETIME_6,
    Base,
    TimestampMixin,
    pk_column,
)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = pk_column()
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    avatar_file_id: Mapped[int | None] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("files.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    status: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DATETIME_6, nullable=True)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = pk_column()
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME_6,
        server_default=func.now(),
        nullable=False,
    )


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = pk_column()
    code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    group_name: Mapped[str] = mapped_column(String(64), nullable=False)


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    )


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    permission_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = pk_column()
    user_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DATETIME_6, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DATETIME_6, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME_6,
        server_default=func.now(),
        nullable=False,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class EncryptionSession(Base):
    __tablename__ = "encryption_sessions"

    id: Mapped[int] = pk_column()
    session_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    client_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    key_material: Mapped[bytes] = mapped_column(LargeBinary(64), nullable=False)
    context_seed: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    login_challenge_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    login_challenge_salt: Mapped[bytes | None] = mapped_column(
        LargeBinary(32),
        nullable=True,
    )
    login_challenge_expires_at: Mapped[datetime | None] = mapped_column(
        DATETIME_6,
        nullable=True,
    )
    login_challenge_used_at: Mapped[datetime | None] = mapped_column(
        DATETIME_6,
        nullable=True,
    )
    expires_at: Mapped[datetime] = mapped_column(DATETIME_6, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME_6,
        server_default=func.now(),
        nullable=False,
    )
