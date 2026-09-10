"""add validation commands and check results

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-10

"""
import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels = None
depends_on = None


check_status = sa.Enum(
    "PENDING",
    "RUNNING",
    "PASSED",
    "FAILED",
    "TIMED_OUT",
    name="validation_check_status",
    native_enum=False,
    length=32,
)


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("validation_commands", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.create_table(
        "validation_checks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("check_type", sa.String(length=32), nullable=False),
        sa.Column("command", sa.Text(), nullable=False),
        sa.Column("status", check_status, nullable=False),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("output", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["attempts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attempt_id", "position", name="uq_validation_attempt_position"),
    )
    op.create_index("ix_validation_checks_task_id", "validation_checks", ["task_id"])
    op.create_index("ix_validation_checks_attempt_id", "validation_checks", ["attempt_id"])


def downgrade() -> None:
    op.drop_index("ix_validation_checks_attempt_id", table_name="validation_checks")
    op.drop_index("ix_validation_checks_task_id", table_name="validation_checks")
    op.drop_table("validation_checks")
    op.drop_column("tasks", "validation_commands")
