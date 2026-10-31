"""Teacher review of content: one approval per reviewer (database check), an immutable review history

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from setu.store import grants

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
APPROVALS = {"letter": "approvals", "akshara": "approvals", "lexeme": "approvals", "chunk": "approvals",
             "scene_script": "approvals", "scene_line": "approvals", "scene_reply_variant": "approvals",
             "accepted_variant": "approvals", "rule_version": "speaker_approvals"}
DISTINCT = """
CREATE FUNCTION setu_distinct_reviewers(a jsonb) RETURNS boolean LANGUAGE sql IMMUTABLE AS $fn$
  -- every approval names its reviewer, and no reviewer is counted twice
  SELECT coalesce(bool_and(x ? 'reviewer'), true) AND count(*) = count(DISTINCT x->>'reviewer')
    FROM jsonb_array_elements(a) AS x
$fn$"""
# The content role may append to the ledger only its own review events, never anything that could back learning state.
LEDGER_GUARD = """
CREATE FUNCTION setu_content_ledger_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF current_user = 'setu_content' AND (NEW.event_type <> 'content_reviewed' OR NEW.actor NOT LIKE 'teacher:%') THEN
    RAISE EXCEPTION 'setu_content may append only content_reviewed events by a teacher';
  END IF;
  RETURN NEW;
END $$"""
KINDS = ("letter", "akshara", "lexeme", "chunk", "scene", "scene_script", "scene_line", "scene_reply_variant")


def upgrade() -> None:
    op.execute(DISTINCT)
    for table, col in APPROVALS.items():
        op.create_check_constraint(op.f(f"ck_{table}_distinct_reviewers"), table, f"setu_distinct_reviewers({col})")
    op.create_table(
        "content_review",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("target_kind", sa.Text(), nullable=False),
        sa.Column("target_id", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("reviewer_id", UUID, nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("native_speaker", sa.Boolean(), nullable=False),
        sa.Column("comment_hi", sa.Text(), nullable=True),
        sa.Column("status_after", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(f"target_kind IN {KINDS}", name=op.f("ck_content_review_target_kind_values")),
        sa.CheckConstraint("decision IN ('approve', 'reject')", name=op.f("ck_content_review_decision_values")),
        sa.CheckConstraint("setu_no_latin(comment_hi)", name=op.f("ck_content_review_comment_hi_no_latin")),
        sa.ForeignKeyConstraint(["reviewer_id"], ["learner.id"], name=op.f("fk_content_review_reviewer_id_learner")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_content_review")),
    )
    op.execute("CREATE TRIGGER content_review_immutable BEFORE UPDATE OR DELETE ON content_review "
               "FOR EACH ROW EXECUTE FUNCTION setu_forbid_mutation()")
    op.execute("CREATE TRIGGER content_review_no_truncate BEFORE TRUNCATE ON content_review "
               "FOR EACH STATEMENT EXECUTE FUNCTION setu_forbid_mutation()")
    op.execute(LEDGER_GUARD)
    op.execute("CREATE TRIGGER event_ledger_content_guard BEFORE INSERT ON event_ledger "
               "FOR EACH ROW EXECUTE FUNCTION setu_content_ledger_guard()")
    for stmt in grants.grant_statements(grants.PLAN_V9, grants.VIEW_GRANTS_V5, grants.SEQUENCE_GRANTS_V2):
        op.execute(stmt)


def downgrade() -> None:
    op.execute("REVOKE USAGE ON SEQUENCE event_ledger_id_seq FROM setu_content")
    op.execute("DROP TRIGGER IF EXISTS event_ledger_content_guard ON event_ledger")
    op.execute("DROP FUNCTION IF EXISTS setu_content_ledger_guard()")
    op.drop_table("content_review")
    for table in APPROVALS:
        op.drop_constraint(op.f(f"ck_{table}_distinct_reviewers"), table, type_="check")
    op.execute("DROP FUNCTION IF EXISTS setu_distinct_reviewers(jsonb)")
    for stmt in grants.grant_statements(grants.PLAN_V8, grants.VIEW_GRANTS_V5):
        op.execute(stmt)
