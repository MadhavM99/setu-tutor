"""Rule review decisions: decision and native-speaker declaration on each review, immutable reviews, variant review

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-31
"""
import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

OLD_KINDS = ("letter", "akshara", "lexeme", "chunk", "scene", "scene_script", "scene_line", "scene_reply_variant")
NEW_KINDS = (*OLD_KINDS, "accepted_variant")


def upgrade() -> None:
    op.add_column("rule_review", sa.Column("decision", sa.Text(), server_default="uncertain", nullable=False))
    op.alter_column("rule_review", "decision", server_default=None)
    op.add_column("rule_review", sa.Column("native_speaker", sa.Boolean(), server_default=sa.text("false"),
                                           nullable=False))
    op.add_column("rule_review", sa.Column("batch", sa.Text(), nullable=True))
    op.create_check_constraint(op.f("ck_rule_review_decision_values"), "rule_review",
                               "decision IN ('approve', 'reject', 'uncertain')")
    op.create_check_constraint(op.f("ck_rule_review_comments_hi_no_latin"), "rule_review", "setu_no_latin(comments_hi)")
    op.execute("CREATE TRIGGER rule_review_immutable BEFORE UPDATE OR DELETE ON rule_review "
               "FOR EACH ROW EXECUTE FUNCTION setu_forbid_mutation()")
    op.drop_constraint(op.f("ck_content_review_target_kind_values"), "content_review", type_="check")
    op.create_check_constraint(op.f("ck_content_review_target_kind_values"), "content_review",
                               f"target_kind IN {NEW_KINDS}")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_content_review_target_kind_values"), "content_review", type_="check")
    op.create_check_constraint(op.f("ck_content_review_target_kind_values"), "content_review",
                               f"target_kind IN {OLD_KINDS}")
    op.execute("DROP TRIGGER IF EXISTS rule_review_immutable ON rule_review")
    op.drop_constraint(op.f("ck_rule_review_comments_hi_no_latin"), "rule_review", type_="check")
    op.drop_constraint(op.f("ck_rule_review_decision_values"), "rule_review", type_="check")
    for c in ("batch", "native_speaker", "decision"):
        op.drop_column("rule_review", c)
