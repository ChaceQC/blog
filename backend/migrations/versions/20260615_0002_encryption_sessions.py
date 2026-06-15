"""增加应用层加密会话表

Revision ID: 20260615_0002
Revises: 20260615_0001
Create Date: 2026-06-15 23:20:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "20260615_0002"
down_revision: str | Sequence[str] | None = "20260615_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def bigint_unsigned():
    return sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql")


def datetime_6():
    return sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "encryption_sessions",
        sa.Column("id", bigint_unsigned(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("key_material", sa.LargeBinary(length=64), nullable=False),
        sa.Column("expires_at", datetime_6(), nullable=False),
        sa.Column(
            "created_at",
            datetime_6(),
            server_default=sa.text("CURRENT_TIMESTAMP(6)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_encryption_sessions")),
        sa.UniqueConstraint(
            "session_id",
            name=op.f("uq_encryption_sessions_session_id"),
        ),
    )
    op.create_index(
        "idx_encryption_sessions_expires_at",
        "encryption_sessions",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "idx_encryption_sessions_expires_at",
        table_name="encryption_sessions",
    )
    op.drop_table("encryption_sessions")
