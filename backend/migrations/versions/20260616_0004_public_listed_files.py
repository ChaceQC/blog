"""增加公开文件栏标记

Revision ID: 20260616_0004
Revises: 20260616_0003
Create Date: 2026-06-16 15:20:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260616_0004"
down_revision: str | Sequence[str] | None = "20260616_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "files",
        sa.Column(
            "public_listed",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_files_public_listed",
        "files",
        ["visibility", "public_listed", "status"],
        unique=False,
    )
    op.alter_column("files", "public_listed", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_files_public_listed", table_name="files")
    op.drop_column("files", "public_listed")
