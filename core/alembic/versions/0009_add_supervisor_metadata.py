"""add supervisor metadata to tasks

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-13

"""
import sqlalchemy as sa

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("supervisor_client", sa.String(length=80), nullable=True))
    op.add_column(
        "tasks",
        sa.Column("supervisor_session_id", sa.String(length=200), nullable=True),
    )
    op.add_column("tasks", sa.Column("project_id", sa.String(length=200), nullable=True))
    op.create_index("ix_tasks_supervisor_client", "tasks", ["supervisor_client"])
    op.create_index(
        "ix_tasks_supervisor_session_id",
        "tasks",
        ["supervisor_session_id"],
    )
    op.create_index("ix_tasks_project_id", "tasks", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_tasks_project_id", table_name="tasks")
    op.drop_index("ix_tasks_supervisor_session_id", table_name="tasks")
    op.drop_index("ix_tasks_supervisor_client", table_name="tasks")
    op.drop_column("tasks", "project_id")
    op.drop_column("tasks", "supervisor_session_id")
    op.drop_column("tasks", "supervisor_client")
