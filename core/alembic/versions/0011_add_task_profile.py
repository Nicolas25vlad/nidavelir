"""add requested task profile

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-14

"""
import sqlalchemy as sa

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("profile", sa.String(length=80), nullable=False, server_default="auto"),
    )


def downgrade() -> None:
    op.drop_column("tasks", "profile")
