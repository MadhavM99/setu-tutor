"""input methods (R-INPUT): response mode and assistance on every attempt; only independent, cue-free fixes teach

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from setu.store import sql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

ATTEMPT_CHECKS = [
    ("response_mode_values",
     "response_mode IN ('multiple_choice', 'tiles', 'onscreen_keyboard', 'typed', 'spoken')"),
    ("assistance_values", "setu_assistance_valid(assistance)"),
    ("cue_level_matches_aids", "(cue_level = 0) = (setu_recall_cues(assistance) = 0)"),
    ("choices_recorded", "response_mode <> 'multiple_choice' OR assistance ? 'choices'"),
    ("tiles_recorded", "response_mode <> 'tiles' OR assistance ? 'tiles'"),
]
OLD_KINDS = "kind IN ('fix', 'no_error', 'explanation', 'own', 'recall')"
NEW_KINDS = "kind IN ('fix', 'no_error', 'explanation', 'own', 'recall', 'recognition')"


def upgrade() -> None:
    for stmt in sql.INPUT_FUNCTIONS:
        op.execute(stmt)
    op.add_column("attempt", sa.Column("response_mode", sa.Text(), server_default="typed", nullable=False))
    op.add_column("attempt", sa.Column("assistance", postgresql.JSONB(astext_type=sa.Text()),
                                       server_default=sa.text("'[]'::jsonb"), nullable=False))
    for name, expr in ATTEMPT_CHECKS:
        op.create_check_constraint(op.f(f"ck_attempt_{name}"), "attempt", expr)
    op.drop_constraint(op.f("ck_verdict_kind_values"), "verdict", type_="check")
    op.create_check_constraint(op.f("ck_verdict_kind_values"), "verdict", NEW_KINDS)
    op.execute(sql.CLASSMATE_GUARD_V2)
    for stmt in sql.FSRS_CUE_GUARD:
        op.execute(stmt)


def downgrade() -> None:
    for stmt in sql.INPUT_DOWN:
        op.execute(stmt)
    op.execute(sql.CLASSMATE_GUARD_V1_REPLACE)
    op.drop_constraint(op.f("ck_verdict_kind_values"), "verdict", type_="check")
    op.create_check_constraint(op.f("ck_verdict_kind_values"), "verdict", OLD_KINDS)
    for name, _ in ATTEMPT_CHECKS:
        op.drop_constraint(op.f(f"ck_attempt_{name}"), "attempt", type_="check")
    op.drop_column("attempt", "assistance")
    op.drop_column("attempt", "response_mode")
    for stmt in sql.INPUT_FUNCTIONS_DOWN:
        op.execute(stmt)
