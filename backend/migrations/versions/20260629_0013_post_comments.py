"""add anonymous post comments

Revision ID: 20260629_0013
Revises: 20260626_0012
Create Date: 2026-06-29 01:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260629_0013"
down_revision: str | None = "20260626_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def bigint_unsigned():
    return sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql")


def datetime_6():
    return sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def long_text():
    return sa.Text().with_variant(mysql.LONGTEXT(), "mysql")


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
            "comment_count",
            bigint_unsigned(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.create_table(
        "post_comments",
        pk_column(),
        sa.Column("post_id", bigint_unsigned(), nullable=False),
        sa.Column("parent_id", bigint_unsigned(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=64), nullable=True),
        sa.Column("author_public_id", sa.String(length=32), nullable=False),
        sa.Column("author_key_hash", sa.String(length=64), nullable=False),
        sa.Column("fingerprint_hash", sa.String(length=64), nullable=False),
        sa.Column("risk_hash", sa.String(length=64), nullable=False),
        sa.Column("delete_token_hash", sa.String(length=64), nullable=True),
        sa.Column("body_text", long_text(), nullable=False),
        sa.Column("body_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "reply_count",
            bigint_unsigned(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        created_at_column(),
        updated_at_column(),
        sa.Column("reviewed_at", datetime_6(), nullable=True),
        sa.Column("reviewed_by", bigint_unsigned(), nullable=True),
        sa.Column("deleted_at", datetime_6(), nullable=True),
        sa.Column("deleted_reason", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["post_comments.id"],
            name=op.f("fk_post_comments_parent_id_post_comments"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["posts.id"],
            name=op.f("fk_post_comments_post_id_posts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"],
            ["users.id"],
            name=op.f("fk_post_comments_reviewed_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_post_comments")),
    )
    op.create_index(
        "idx_post_comments_post_status_created",
        "post_comments",
        ["post_id", "status", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "idx_post_comments_post_parent_status_created",
        "post_comments",
        ["post_id", "parent_id", "status", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "idx_post_comments_author_created",
        "post_comments",
        ["author_key_hash", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_post_comments_risk_created",
        "post_comments",
        ["risk_hash", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_post_comments_post_body_created",
        "post_comments",
        ["post_id", "body_hash", "created_at"],
        unique=False,
    )
    op.execute(
        sa.text(
            """
            INSERT INTO permissions (code, name, group_name)
            SELECT 'comment:review', '评论审核', '评论'
            WHERE NOT EXISTS (
                SELECT 1 FROM permissions WHERE code = 'comment:review'
            )
            """,
        ),
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM permissions WHERE code = 'comment:review'"),
    )
    op.drop_index("idx_post_comments_post_body_created", table_name="post_comments")
    op.drop_index("idx_post_comments_risk_created", table_name="post_comments")
    op.drop_index("idx_post_comments_author_created", table_name="post_comments")
    op.drop_index(
        "idx_post_comments_post_parent_status_created",
        table_name="post_comments",
    )
    op.drop_index("idx_post_comments_post_status_created", table_name="post_comments")
    op.drop_table("post_comments")
    op.drop_column("posts", "comment_count")
