"""add log retention indexes

Revision ID: 20260619_0008
Revises: 20260619_0007
Create Date: 2026-06-19 21:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260619_0008"
down_revision: str | None = "20260619_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "idx_audit_logs_created_at",
        "audit_logs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "idx_login_logs_created_at",
        "login_logs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "idx_security_events_created_at",
        "security_events",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_security_events_created_at", table_name="security_events")
    op.drop_index("idx_login_logs_created_at", table_name="login_logs")
    op.drop_index("idx_audit_logs_created_at", table_name="audit_logs")
