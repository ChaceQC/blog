"""add post interactions

Revision ID: 20260626_0012
Revises: 20260624_0011
Create Date: 2026-06-26 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260626_0012"
down_revision: str | None = "20260624_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def bigint_unsigned():
    return sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql")


def datetime_6():
    return sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def pk_column() -> sa.Column:
    return sa.Column("id", bigint_unsigned(), autoincrement=True, nullable=False)


def created_at_column() -> sa.Column:
    return sa.Column(
        "created_at",
        datetime_6(),
        server_default=sa.text("CURRENT_TIMESTAMP(6)"),
        nullable=False,
    )


def updated_at_column() -> sa.Column:
    return sa.Column(
        "updated_at",
        datetime_6(),
        server_default=sa.text("CURRENT_TIMESTAMP(6)"),
        nullable=False,
    )


def upgrade() -> None:
    op.add_column(
        "posts",
        sa.Column(
            "like_count",
            bigint_unsigned(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.create_table(
        "post_likes",
        pk_column(),
        sa.Column("post_id", bigint_unsigned(), nullable=False),
        sa.Column("visitor_hash", sa.String(length=64), nullable=False),
        sa.Column("fingerprint_hash", sa.String(length=64), nullable=False),
        sa.Column("risk_hash", sa.String(length=64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        created_at_column(),
        updated_at_column(),
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["posts.id"],
            name=op.f("fk_post_likes_post_id_posts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_post_likes")),
        sa.UniqueConstraint(
            "post_id",
            "visitor_hash",
            name=op.f("uq_post_likes_post_visitor"),
        ),
    )
    op.create_index(
        "idx_post_likes_post_active",
        "post_likes",
        ["post_id", "active"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_post_likes_post_active", table_name="post_likes")
    op.drop_table("post_likes")
    op.drop_column("posts", "like_count")
