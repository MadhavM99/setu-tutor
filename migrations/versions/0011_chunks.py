"""L3 chunks per scene; learners see one only when it, its scene and every letter in it are approved

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from setu.store import grants

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB(astext_type=sa.Text())
LEARNER_CHUNK = """
CREATE VIEW learner_chunk AS
SELECT ch.* FROM chunk ch JOIN learner_scene s ON s.id = ch.scene_id
WHERE ch.review_status = 'approved'
  AND NOT EXISTS (
    SELECT 1 FROM jsonb_array_elements_text(ch.letters) AS x(c)
    WHERE NOT EXISTS (SELECT 1 FROM letter y WHERE y.telugu = x.c AND y.review_status = 'approved'))
"""


def upgrade() -> None:
    op.create_table(
        "chunk",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("scene_id", sa.Text(), nullable=False),
        sa.Column("telugu", sa.Text(), nullable=False),
        sa.Column("hindi_meaning", sa.Text(), nullable=False),
        sa.Column("register", sa.Text(), nullable=False),
        sa.Column("letters", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("unit_order", sa.Integer(), nullable=False),
        sa.Column("review_status", sa.Text(), server_default="draft", nullable=False),
        sa.Column("approvals", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("provenance", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=True),
        sa.CheckConstraint("register IN ('standard', 'spoken')", name=op.f("ck_chunk_register_values")),
        sa.CheckConstraint("review_status IN ('draft', 'in_review', 'approved', 'rejected')",
                           name=op.f("ck_chunk_review_status_values")),
        sa.CheckConstraint("review_status <> 'approved' OR jsonb_array_length(approvals) >= 2",
                           name=op.f("ck_chunk_approved_needs_two")),
        *[sa.CheckConstraint(f"setu_no_latin({c})", name=op.f(f"ck_chunk_{c}_no_latin"))
          for c in ("telugu", "hindi_meaning")],
        sa.ForeignKeyConstraint(["scene_id"], ["scene.id"], name=op.f("fk_chunk_scene_id_scene")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chunk")),
        sa.UniqueConstraint("unit_order", name=op.f("uq_chunk_unit_order")),
    )
    op.execute(LEARNER_CHUNK)
    for stmt in grants.grant_statements(grants.PLAN_V7, grants.VIEW_GRANTS_V4):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in grants.grant_statements(grants.PLAN_V6, grants.VIEW_GRANTS_V3):
        op.execute(stmt)
    op.execute("DROP VIEW IF EXISTS learner_chunk")
    op.drop_table("chunk")
