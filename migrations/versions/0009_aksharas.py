"""L1 aksharas; learners see one only when it and every letter in it are approved

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from setu.store import grants

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB(astext_type=sa.Text())
LEARNER_AKSHARA = """
CREATE VIEW learner_akshara AS
SELECT a.* FROM akshara a
WHERE a.review_status = 'approved'
  AND NOT EXISTS (
    SELECT 1 FROM jsonb_array_elements_text(a.letters) AS l(ch)
    WHERE NOT EXISTS (SELECT 1 FROM letter x WHERE x.telugu = l.ch AND x.review_status = 'approved'))
"""


def upgrade() -> None:
    op.create_table(
        "akshara",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("telugu", sa.Text(), nullable=False),
        sa.Column("devanagari", sa.Text(), nullable=False),
        sa.Column("twin_label_hi", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("family", sa.Text(), nullable=False),
        sa.Column("akshara_group", sa.Text(), nullable=False),
        sa.Column("group_hi", sa.Text(), nullable=False),
        sa.Column("letters", JSONB, nullable=False),
        sa.Column("unit_order", sa.Integer(), nullable=False),
        sa.Column("note_hi", sa.Text(), nullable=True),
        sa.Column("review_status", sa.Text(), server_default="draft", nullable=False),
        sa.Column("approvals", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("provenance", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=True),
        sa.CheckConstraint("kind IN ('sign', 'double', 'conjunct')", name=op.f("ck_akshara_kind_values")),
        sa.CheckConstraint("family IN ('vowel_signs', 'nasal_visarga', 'doubles', 'conjuncts')",
                           name=op.f("ck_akshara_family_values")),
        sa.CheckConstraint("review_status IN ('draft', 'in_review', 'approved', 'rejected')",
                           name=op.f("ck_akshara_review_status_values")),
        sa.CheckConstraint("review_status <> 'approved' OR jsonb_array_length(approvals) >= 2",
                           name=op.f("ck_akshara_approved_needs_two")),
        *[sa.CheckConstraint(f"setu_no_latin({c})", name=op.f(f"ck_akshara_{c}_no_latin"))
          for c in ("telugu", "devanagari", "twin_label_hi", "group_hi", "note_hi")],
        sa.PrimaryKeyConstraint("id", name=op.f("pk_akshara")),
        sa.UniqueConstraint("telugu", name=op.f("uq_akshara_telugu")),
        sa.UniqueConstraint("unit_order", name=op.f("uq_akshara_unit_order")),
    )
    op.execute(LEARNER_AKSHARA)
    for stmt in grants.grant_statements(grants.PLAN_V6, grants.VIEW_GRANTS_V3):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in grants.grant_statements(grants.PLAN_V5, grants.VIEW_GRANTS_V2):
        op.execute(stmt)
    op.execute("DROP VIEW IF EXISTS learner_akshara")
    op.drop_table("akshara")
