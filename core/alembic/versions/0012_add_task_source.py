"""add task source metadata

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-19
"""

import sqlalchemy as sa

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("source_key", sa.String(length=600), nullable=True))
    op.add_column("tasks", sa.Column("source", sa.JSON(), nullable=True))
    op.create_index("ix_tasks_source_key", "tasks", ["source_key"])


def downgrade() -> None:
    op.drop_index("ix_tasks_source_key", table_name="tasks")
    op.drop_column("tasks", "source")
    op.drop_column("tasks", "source_key")
