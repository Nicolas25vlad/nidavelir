"""add normalized attempt token usage

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-11

"""
import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("attempts", sa.Column("model", sa.String(length=160), nullable=True))
    op.add_column("attempts", sa.Column("input_tokens", sa.Integer(), nullable=True))
    op.add_column("attempts", sa.Column("cached_input_tokens", sa.Integer(), nullable=True))
    op.add_column("attempts", sa.Column("cache_write_input_tokens", sa.Integer(), nullable=True))
    op.add_column("attempts", sa.Column("output_tokens", sa.Integer(), nullable=True))
    op.add_column("attempts", sa.Column("reasoning_tokens", sa.Integer(), nullable=True))
    op.add_column("attempts", sa.Column("total_tokens", sa.Integer(), nullable=True))
    op.add_column("attempts", sa.Column("cache_hit_ratio", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("attempts", "cache_hit_ratio")
    op.drop_column("attempts", "total_tokens")
    op.drop_column("attempts", "reasoning_tokens")
    op.drop_column("attempts", "output_tokens")
    op.drop_column("attempts", "cache_write_input_tokens")
    op.drop_column("attempts", "cached_input_tokens")
    op.drop_column("attempts", "input_tokens")
    op.drop_column("attempts", "model")
