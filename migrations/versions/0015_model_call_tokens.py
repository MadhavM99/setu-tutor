"""Token usage on each model call (P-COST-04)

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-31
"""
import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("model_call", sa.Column("prompt_tokens", sa.Integer(), nullable=True))
    op.add_column("model_call", sa.Column("completion_tokens", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("model_call", "completion_tokens")
    op.drop_column("model_call", "prompt_tokens")
