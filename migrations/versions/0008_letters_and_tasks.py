"""L0 letters (approval needs two speakers; learners see approved letters only) and server-held tasks on exchanges

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from setu.store import grants

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "letter",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("telugu", sa.Text(), nullable=False),
        sa.Column("devanagari", sa.Text(), nullable=False),
        sa.Column("twin_label_hi", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("letter_group", sa.Text(), nullable=False),
        sa.Column("group_hi", sa.Text(), nullable=False),
        sa.Column("varnamala_order", sa.Integer(), nullable=False),
        sa.Column("new_for_hindi", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("note_hi", sa.Text(), nullable=True),
        sa.Column("review_status", sa.Text(), server_default="draft", nullable=False),
        sa.Column("approvals", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("provenance", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=True),
        sa.CheckConstraint("kind IN ('vowel', 'consonant')", name=op.f("ck_letter_kind_values")),
        sa.CheckConstraint("review_status IN ('draft', 'in_review', 'approved', 'rejected')",
                           name=op.f("ck_letter_review_status_values")),
        sa.CheckConstraint("review_status <> 'approved' OR jsonb_array_length(approvals) >= 2",
                           name=op.f("ck_letter_approved_needs_two")),
        *[sa.CheckConstraint(f"setu_no_latin({c})", name=op.f(f"ck_letter_{c}_no_latin"))
          for c in ("telugu", "devanagari", "twin_label_hi", "group_hi", "note_hi")],
        sa.PrimaryKeyConstraint("id", name=op.f("pk_letter")),
        sa.UniqueConstraint("telugu", name=op.f("uq_letter_telugu")),
        sa.UniqueConstraint("varnamala_order", name=op.f("uq_letter_varnamala_order")),
    )
    op.add_column("exchange", sa.Column("task", JSONB, nullable=True))
    op.execute("CREATE VIEW learner_letter AS SELECT * FROM letter WHERE review_status = 'approved'")
    for stmt in grants.grant_statements(grants.PLAN_V5, grants.VIEW_GRANTS_V2):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in grants.grant_statements(grants.PLAN_V4, grants.VIEW_GRANTS):
        op.execute(stmt)
    op.execute("GRANT SELECT ON classmate_vl TO setu_read, setu_app, setu_writer")
    op.execute("DROP VIEW IF EXISTS learner_letter")
    op.drop_column("exchange", "task")
    op.drop_table("letter")
