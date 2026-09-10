"""add review decisions and merge result

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-10

"""
import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("merge_commit_sha", sa.String(length=64), nullable=True))
    op.create_table(
        "review_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("actor", sa.String(length=160), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["attempts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_decisions_task_id", "review_decisions", ["task_id"])
    op.create_index("ix_review_decisions_attempt_id", "review_decisions", ["attempt_id"])


def downgrade() -> None:
    op.drop_index("ix_review_decisions_attempt_id", table_name="review_decisions")
    op.drop_index("ix_review_decisions_task_id", table_name="review_decisions")
    op.drop_table("review_decisions")
    op.drop_column("tasks", "merge_commit_sha")
