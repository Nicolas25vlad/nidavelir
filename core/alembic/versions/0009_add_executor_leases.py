"""add durable executor leases

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-11

"""
import sqlalchemy as sa

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("attempts", sa.Column("lease_owner", sa.String(length=160), nullable=True))
    op.add_column(
        "attempts",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "attempts",
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_attempts_lease_owner", "attempts", ["lease_owner"])
    op.create_index(
        "ix_attempts_queue_claim",
        "attempts",
        ["status", "lease_expires_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_attempts_queue_claim", table_name="attempts")
    op.drop_index("ix_attempts_lease_owner", table_name="attempts")
    op.drop_column("attempts", "heartbeat_at")
    op.drop_column("attempts", "lease_expires_at")
    op.drop_column("attempts", "lease_owner")
