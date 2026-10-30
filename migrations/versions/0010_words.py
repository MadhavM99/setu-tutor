"""L2 words: two native approvals per word, ladder order and letters, false-friend look-alikes; learners see a
word only when it and every letter in it are approved

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB(astext_type=sa.Text())
LEARNER_LEXEME = """
CREATE OR REPLACE VIEW learner_lexeme AS
SELECT l.* FROM lexeme l
WHERE l.review_status = 'approved'
  AND NOT EXISTS (
    SELECT 1 FROM jsonb_array_elements_text(l.letters) AS x(ch)
    WHERE NOT EXISTS (SELECT 1 FROM letter y WHERE y.telugu = x.ch AND y.review_status = 'approved'))
"""


def upgrade() -> None:
    op.add_column("lexeme", sa.Column("looks_like_hi", sa.Text(), nullable=True))
    op.add_column("lexeme", sa.Column("word_group", sa.Text(), nullable=True))
    op.add_column("lexeme", sa.Column("ladder_order", sa.Integer(), nullable=True))
    op.add_column("lexeme", sa.Column("letters", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.add_column("lexeme", sa.Column("approvals", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.create_check_constraint(op.f("ck_lexeme_approved_needs_two"), "lexeme",
                               "review_status <> 'approved' OR jsonb_array_length(approvals) >= 2")
    op.create_check_constraint(op.f("ck_lexeme_looks_like_hi_no_latin"), "lexeme", "setu_no_latin(looks_like_hi)")
    op.execute(LEARNER_LEXEME)


def downgrade() -> None:
    op.execute("DROP VIEW learner_lexeme")
    op.drop_constraint(op.f("ck_lexeme_looks_like_hi_no_latin"), "lexeme", type_="check")
    op.drop_constraint(op.f("ck_lexeme_approved_needs_two"), "lexeme", type_="check")
    for col in ("approvals", "letters", "ladder_order", "word_group", "looks_like_hi"):
        op.drop_column("lexeme", col)
    op.execute("CREATE VIEW learner_lexeme AS SELECT * FROM lexeme WHERE review_status = 'approved'")
    op.execute("GRANT SELECT ON learner_lexeme TO setu_read, setu_app, setu_writer")
