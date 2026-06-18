"""persist encryption session scope

Revision ID: 20260618_0006
Revises: 20260617_0005
Create Date: 2026-06-18 03:50:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260618_0006"
down_revision: str | None = "20260617_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "encryption_sessions",
        sa.Column(
            "scope",
            sa.String(length=16),
            nullable=False,
            server_default="admin",
        ),
    )
    op.alter_column("encryption_sessions", "scope", server_default=None)


def downgrade() -> None:
    op.drop_column("encryption_sessions", "scope")
