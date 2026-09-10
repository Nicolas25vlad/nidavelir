"""persist attempt git diff

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-10

"""
import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("attempts", sa.Column("base_commit_sha", sa.String(length=64), nullable=True))
    op.add_column("attempts", sa.Column("diff_stat", sa.Text(), nullable=True))
    op.add_column("attempts", sa.Column("diff_patch", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("attempts", "diff_patch")
    op.drop_column("attempts", "diff_stat")
    op.drop_column("attempts", "base_commit_sha")
