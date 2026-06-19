"""add friend link status index

Revision ID: 20260619_0009
Revises: 20260619_0008
Create Date: 2026-06-19 21:30:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260619_0009"
down_revision: str | None = "20260619_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "idx_friend_links_status",
        "friend_links",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_friend_links_status", table_name="friend_links")
