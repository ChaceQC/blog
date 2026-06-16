"""增加访问日志表

Revision ID: 20260616_0003
Revises: 20260615_0002
Create Date: 2026-06-16 14:40:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "20260616_0003"
down_revision: str | Sequence[str] | None = "20260615_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def bigint_unsigned():
    return sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql")


def datetime_6():
    return sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "access_logs",
        sa.Column("id", bigint_unsigned(), autoincrement=True, nullable=False),
        sa.Column("access_type", sa.String(length=64), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("path", sa.String(length=500), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=True),
        sa.Column("entity_id", bigint_unsigned(), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("detail_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            datetime_6(),
            server_default=sa.text("CURRENT_TIMESTAMP(6)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_access_logs")),
    )
    op.create_index(
        "idx_access_logs_created_at",
        "access_logs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "idx_access_logs_type",
        "access_logs",
        ["access_type"],
        unique=False,
    )
    op.create_index(
        "idx_access_logs_entity",
        "access_logs",
        ["entity_type", "entity_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_access_logs_entity", table_name="access_logs")
    op.drop_index("idx_access_logs_type", table_name="access_logs")
    op.drop_index("idx_access_logs_created_at", table_name="access_logs")
    op.drop_table("access_logs")
