"""add post seo keywords

Revision ID: 20260617_0005
Revises: 20260616_0004
Create Date: 2026-06-17 05:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260617_0005"
down_revision: str | None = "20260616_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "posts",
        sa.Column("seo_keywords", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("posts", "seo_keywords")
