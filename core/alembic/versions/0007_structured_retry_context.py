"""add structured retry context snapshots

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-11

"""
import sqlalchemy as sa

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("retry_context", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "tasks",
        sa.Column("retry_review_ids", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "attempts",
        sa.Column("retry_context", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "attempts",
        sa.Column("retry_review_ids", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("attempts", "retry_review_ids")
    op.drop_column("attempts", "retry_context")
    op.drop_column("tasks", "retry_review_ids")
    op.drop_column("tasks", "retry_context")
