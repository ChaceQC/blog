"""add encryption context seed

Revision ID: 20260624_0011
Revises: 20260623_0010
Create Date: 2026-06-24 05:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260624_0011"
down_revision: str | None = "20260623_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "encryption_sessions",
        sa.Column("context_seed", sa.LargeBinary(length=32), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE encryption_sessions "
            "SET context_seed = RANDOM_BYTES(32) WHERE context_seed IS NULL",
        ),
    )
    op.alter_column(
        "encryption_sessions",
        "context_seed",
        existing_type=sa.LargeBinary(length=32),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("encryption_sessions", "context_seed")
