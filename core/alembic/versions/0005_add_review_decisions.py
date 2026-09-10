"""add review decisions and transition audit metadata

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
    op.add_column("task_transitions", sa.Column("attempt_id", sa.Uuid(), nullable=True))
    op.add_column("task_transitions", sa.Column("actor", sa.String(length=200), nullable=True))
    op.create_foreign_key(
        "fk_task_transitions_attempt_id",
        "task_transitions",
        "attempts",
        ["attempt_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "review_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("actor", sa.String(length=200), nullable=False),
        sa.Column("feedback", sa.JSON(), nullable=True),
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
    op.drop_constraint("fk_task_transitions_attempt_id", "task_transitions", type_="foreignkey")
    op.drop_column("task_transitions", "actor")
    op.drop_column("task_transitions", "attempt_id")
