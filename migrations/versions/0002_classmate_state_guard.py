"""classmate state guard: changes must be backed by checked evidence

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-31
"""
from alembic import op

from setu.store import sql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint("uq_classmate_rule_state_last_event_id", "classmate_rule_state", ["last_event_id"])
    for stmt in sql.CLASSMATE_GUARD:
        op.execute(stmt)


def downgrade() -> None:
    for stmt in sql.CLASSMATE_GUARD_DOWN:
        op.execute(stmt)
    op.drop_constraint("uq_classmate_rule_state_last_event_id", "classmate_rule_state", type_="unique")
