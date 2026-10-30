"""content provenance, validation issues, no-Latin and anchored-pattern guards, learner-visible views

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from setu.store import grants, sql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

JSONB_EMPTY = sa.text("'[]'::jsonb")

NO_LATIN = {
    "rule_version": ("title_hi", "l1_explanation_hi"),
    "item_version": ("template", "hindi_meaning", "wrong_form", "correct_form", "no_error_equivalent"),
    "accepted_variant": ("form",),
    "hint": ("text_hi",),
    "lexeme": ("telugu", "hindi_gloss", "false_friend_note_hi", "cognate_of"),
    "scene": ("title_hi", "setup_hi"),
    "scene_line": ("telugu",),
    "own_task": ("goal_hi",),
    "memory_aid": ("text_hi", "alt_text_hi"),
    "visual_asset": ("alt_text_hi",),
}
NEW_COLUMNS = {
    "rule_version": ("provenance", "validation_issues", "content_hash"),
    "item_version": ("provenance", "validation_issues", "content_hash"),
    "accepted_variant": ("provenance",),
    "lexeme": ("provenance", "content_hash"),
    "scene": ("provenance", "content_hash"),
}
CHECKS = [
    ("rule_version", "verified_needs_l1_text",
     "lifecycle NOT IN ('verified', 'active') OR (title_hi IS NOT NULL AND l1_explanation_hi IS NOT NULL)"),
    ("rule_version", "verified_has_no_issues", "validity <> 'verified' OR validation_issues = '[]'::jsonb"),
    ("item_version", "approved_has_no_issues", "review_status <> 'approved' OR validation_issues = '[]'::jsonb"),
    ("item_version", "patterns_anchored",
     "setu_patterns_anchored(accept_patterns) AND setu_patterns_anchored(wrong_patterns)"),
]


def _col(name):
    if name == "content_hash":
        return sa.Column(name, sa.Text(), nullable=True)
    return sa.Column(name, postgresql.JSONB(astext_type=sa.Text()), server_default=JSONB_EMPTY, nullable=False)


def upgrade() -> None:
    for stmt in sql.CONTENT_FUNCTIONS:
        op.execute(stmt)
    for table, cols in NEW_COLUMNS.items():
        for c in cols:
            op.add_column(table, _col(c))
    op.alter_column("rule_version", "title_hi", existing_type=sa.Text(), nullable=True)
    op.alter_column("rule_version", "l1_explanation_hi", existing_type=sa.Text(), nullable=True)
    for table, name, expr in CHECKS:
        op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, expr)
    for table, cols in NO_LATIN.items():
        for c in cols:
            op.create_check_constraint(op.f(f"ck_{table}_{c}_no_latin"), table, f"setu_no_latin({c})")
    for stmt in sql.LEARNER_VIEWS:
        op.execute(stmt)
    for stmt in grants.grant_statements(grants.PLAN_V2, grants.VIEW_GRANTS):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in grants.grant_statements(grants.PLAN_V1, views={}):
        op.execute(stmt)
    for stmt in sql.LEARNER_VIEWS_DOWN:
        op.execute(stmt)
    for table, cols in NO_LATIN.items():
        for c in cols:
            op.drop_constraint(op.f(f"ck_{table}_{c}_no_latin"), table, type_="check")
    for table, name, _ in CHECKS:
        op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    # Fails if a draft rule version without learner text exists (rule versions are immutable, so they cannot be
    # back-filled); downgrade only databases without such rows.
    op.alter_column("rule_version", "l1_explanation_hi", existing_type=sa.Text(), nullable=False)
    op.alter_column("rule_version", "title_hi", existing_type=sa.Text(), nullable=False)
    for table, cols in NEW_COLUMNS.items():
        for c in cols:
            op.drop_column(table, c)
    for stmt in sql.CONTENT_FUNCTIONS_DOWN:
        op.execute(stmt)
