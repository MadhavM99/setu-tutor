"""scheduler state: FSRS card state and step, mastery tracker parameters, skill evidence

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-31
"""
import sqlalchemy as sa
from alembic import op

from setu.store import grants

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("learner_lexeme_card", sa.Column("fsrs_state", sa.Integer(), nullable=True))
    op.add_column("learner_lexeme_card", sa.Column("fsrs_step", sa.Integer(), nullable=True))
    for name, default in (("tracker_alpha", "1"), ("tracker_beta", "1"), ("half_life_days", "1")):
        op.add_column("learner_skill_state", sa.Column(name, sa.Float(), server_default=sa.text(default),
                                                       nullable=False))
    op.add_column("learner_skill_state", sa.Column("tracker_version", sa.Text(), nullable=True))
    op.create_table(
        "skill_evidence",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("learner_id", sa.UUID(), nullable=False),
        sa.Column("skill_id", sa.Text(), nullable=False),
        sa.Column("verdict_id", sa.UUID(), nullable=False),
        sa.Column("item_ref", sa.Text(), nullable=False),
        sa.Column("task_type", sa.Text(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("cue_level", sa.Integer(), nullable=False),
        sa.Column("after_reveal", sa.Boolean(), nullable=False),
        sa.Column("production", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("outcome IN ('correct', 'partial', 'wrong')", name=op.f("ck_skill_evidence_outcome_values")),
        sa.CheckConstraint("cue_level BETWEEN 0 AND 3", name=op.f("ck_skill_evidence_cue_level")),
        sa.ForeignKeyConstraint(["learner_id"], ["learner.id"], name=op.f("fk_skill_evidence_learner_id_learner")),
        sa.ForeignKeyConstraint(["skill_id"], ["skill.id"], name=op.f("fk_skill_evidence_skill_id_skill")),
        sa.ForeignKeyConstraint(["verdict_id"], ["verdict.id"], name=op.f("fk_skill_evidence_verdict_id_verdict")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_skill_evidence")),
        sa.UniqueConstraint("verdict_id", "skill_id", name="uq_skill_evidence_verdict_skill"),
    )
    op.execute("CREATE TRIGGER skill_evidence_immutable BEFORE UPDATE OR DELETE ON skill_evidence "
               "FOR EACH ROW EXECUTE FUNCTION setu_forbid_mutation()")
    for stmt in grants.grant_statements(grants.PLAN_V4, grants.VIEW_GRANTS):
        op.execute(stmt)
    op.execute("GRANT SELECT ON classmate_vl TO setu_read, setu_app, setu_writer")  # re-grant after the reset


def downgrade() -> None:
    for stmt in grants.grant_statements(grants.PLAN_V3, grants.VIEW_GRANTS):
        op.execute(stmt)
    op.execute("GRANT SELECT ON classmate_vl TO setu_read, setu_app, setu_writer")
    op.drop_table("skill_evidence")
    for name in ("tracker_version", "half_life_days", "tracker_beta", "tracker_alpha"):
        op.drop_column("learner_skill_state", name)
    op.drop_column("learner_lexeme_card", "fsrs_step")
    op.drop_column("learner_lexeme_card", "fsrs_state")
