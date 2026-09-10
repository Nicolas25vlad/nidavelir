"""create task and transition tables

Revision ID: 0001
Revises:
Create Date: 2026-09-10

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


task_state = sa.Enum(
    "BACKLOG",
    "QUEUED",
    "RUNNING",
    "AGENT_DONE",
    "VALIDATING",
    "NEEDS_CHANGES",
    "APPROVED",
    "MERGED",
    "CLOSED",
    "CANCELLED",
    name="task_state",
    native_enum=False,
    length=32,
)


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("repository", sa.String(length=500), nullable=False),
        sa.Column("base_branch", sa.String(length=200), nullable=False),
        sa.Column("acceptance_criteria", sa.JSON(), nullable=False),
        sa.Column("state", task_state, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "task_transitions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("from_state", task_state, nullable=False),
        sa.Column("to_state", task_state, nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_task_transitions_task_id",
        "task_transitions",
        ["task_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_task_transitions_task_id", table_name="task_transitions")
    op.drop_table("task_transitions")
    op.drop_table("tasks")
