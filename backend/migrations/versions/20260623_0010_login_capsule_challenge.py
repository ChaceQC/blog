"""add login capsule challenge fields

Revision ID: 20260623_0010
Revises: 20260619_0009
Create Date: 2026-06-23 23:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260623_0010"
down_revision: str | None = "20260619_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def datetime_6():
    return sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def upgrade() -> None:
    op.add_column(
        "encryption_sessions",
        sa.Column("login_challenge_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "encryption_sessions",
        sa.Column("login_challenge_salt", sa.LargeBinary(length=32), nullable=True),
    )
    op.add_column(
        "encryption_sessions",
        sa.Column("login_challenge_expires_at", datetime_6(), nullable=True),
    )
    op.add_column(
        "encryption_sessions",
        sa.Column("login_challenge_used_at", datetime_6(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("encryption_sessions", "login_challenge_used_at")
    op.drop_column("encryption_sessions", "login_challenge_expires_at")
    op.drop_column("encryption_sessions", "login_challenge_salt")
    op.drop_column("encryption_sessions", "login_challenge_id")
