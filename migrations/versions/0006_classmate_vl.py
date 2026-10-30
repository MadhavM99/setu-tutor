"""classmate_vl view: the words each learner has met (bounds classmate sentences, TMR = 0)

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-31
"""
from alembic import op

from setu.store import sql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for stmt in sql.CLASSMATE_VL:
        op.execute(stmt)


def downgrade() -> None:
    for stmt in sql.CLASSMATE_VL_DOWN:
        op.execute(stmt)
