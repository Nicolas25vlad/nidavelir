"""create worker attempt table

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-10

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


attempt_status = sa.Enum(
    "PREPARING",
    "RUNNING",
    "SUCCEEDED",
    "FAILED",
    "CANCELLED",
    "TIMED_OUT",
    name="attempt_status",
    native_enum=False,
    length=32,
)


def upgrade() -> None:
    op.create_table(
        "attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("status", attempt_status, nullable=False),
        sa.Column("harness", sa.String(length=80), nullable=False),
        sa.Column("harness_version", sa.String(length=120), nullable=True),
        sa.Column("container_name", sa.String(length=200), nullable=False),
        sa.Column("volume_name", sa.String(length=200), nullable=False),
        sa.Column("branch_name", sa.String(length=240), nullable=False),
        sa.Column("commit_sha", sa.String(length=64), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("logs", sa.Text(), nullable=False),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("container_name"),
        sa.UniqueConstraint("task_id", "number", name="uq_attempt_task_number"),
        sa.UniqueConstraint("volume_name"),
    )
    op.create_index("ix_attempts_task_id", "attempts", ["task_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_attempts_task_id", table_name="attempts")
    op.drop_table("attempts")
