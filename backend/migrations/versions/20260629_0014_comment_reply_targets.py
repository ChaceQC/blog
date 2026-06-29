"""add comment reply target snapshots

Revision ID: 20260629_0014
Revises: 20260629_0013
Create Date: 2026-06-29 03:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260629_0014"
down_revision: str | None = "20260629_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def bigint_unsigned():
    return sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql")


def upgrade() -> None:
    op.add_column(
        "post_comments",
        sa.Column("reply_to_id", bigint_unsigned(), nullable=True),
    )
    op.add_column(
        "post_comments",
        sa.Column("reply_to_display_name", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "post_comments",
        sa.Column("display_name_base", sa.String(length=32), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_post_comments_reply_to_id_post_comments"),
        "post_comments",
        "post_comments",
        ["reply_to_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(
        sa.text(
            """
            UPDATE post_comments
            SET display_name_base = display_name
            WHERE display_name IS NOT NULL
              AND display_name NOT LIKE '匿名读者 #%'
            """,
        ),
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_post_comments_reply_to_id_post_comments"),
        "post_comments",
        type_="foreignkey",
    )
    op.drop_column("post_comments", "display_name_base")
    op.drop_column("post_comments", "reply_to_display_name")
    op.drop_column("post_comments", "reply_to_id")
