"""add resolved validation plan to attempts

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-11

"""
import sqlalchemy as sa

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "attempts",
        sa.Column(
            "validation_mode",
            sa.String(length=32),
            nullable=False,
            server_default="unresolved",
        ),
    )
    op.add_column(
        "attempts",
        sa.Column("validation_reason", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "attempts",
        sa.Column(
            "resolved_validation_commands",
            sa.JSON(),
            nullable=False,
            server_default="[]",
        ),
    )


def downgrade() -> None:
    op.drop_column("attempts", "resolved_validation_commands")
    op.drop_column("attempts", "validation_reason")
    op.drop_column("attempts", "validation_mode")
