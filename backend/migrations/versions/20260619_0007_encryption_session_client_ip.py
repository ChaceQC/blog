"""track encryption session client ip

Revision ID: 20260619_0007
Revises: 20260618_0006
Create Date: 2026-06-19 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260619_0007"
down_revision: str | None = "20260618_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "encryption_sessions",
        sa.Column("client_ip", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_encryption_sessions_scope_client_ip_expires_at",
        "encryption_sessions",
        ["scope", "client_ip", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_encryption_sessions_scope_client_ip_expires_at",
        table_name="encryption_sessions",
    )
    op.drop_column("encryption_sessions", "client_ip")
