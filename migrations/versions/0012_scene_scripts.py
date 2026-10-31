"""L5 scene scripts for the native friend: approved lines and reply variants only, scene telemetry

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from setu.store import grants

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB(astext_type=sa.Text())
UUID = postgresql.UUID(as_uuid=True)
TEXTS = postgresql.ARRAY(sa.Text())
REVIEW = "('draft', 'in_review', 'approved', 'rejected')"
EVENTS = ("started", "line_shown", "hint", "fallback", "completed")

# A script is visible only when it, its scene and every one of its lines are approved; a line only when its script
# is visible; a reply variant only when it is approved (two speakers) and its line is visible.
VIEWS = [
    """
CREATE VIEW learner_scene_script AS
SELECT sc.* FROM scene_script sc JOIN learner_scene s ON s.id = sc.scene_id
 WHERE sc.review_status = 'approved'
   AND EXISTS (SELECT 1 FROM scene_line l WHERE l.scene_id = sc.scene_id)
   AND NOT EXISTS (SELECT 1 FROM scene_line l WHERE l.scene_id = sc.scene_id AND l.review_status <> 'approved')""",
    """
CREATE VIEW learner_scene_line AS
SELECT l.* FROM scene_line l JOIN learner_scene_script sc ON sc.scene_id = l.scene_id
 WHERE l.review_status = 'approved'""",
    """
CREATE VIEW learner_scene_reply_variant AS
SELECT v.* FROM scene_reply_variant v JOIN learner_scene_line l ON l.id = v.line_id WHERE v.status = 'approved'""",
]
OLD_LINE_VIEW = """
CREATE VIEW learner_scene_line AS
SELECT l.* FROM scene_line l JOIN learner_scene s ON s.id = l.scene_id WHERE l.review_status = 'approved'"""


def _no_latin(table, *cols):
    return [sa.CheckConstraint(f"setu_no_latin({c})", name=op.f(f"ck_{table}_{c}_no_latin")) for c in cols]


def upgrade() -> None:
    op.create_table(
        "scene_script",
        sa.Column("scene_id", sa.Text(), nullable=False),
        sa.Column("band", sa.Text(), server_default="L5", nullable=False),
        sa.Column("objective_hi", sa.Text(), nullable=False),
        sa.Column("instructions_hi", sa.Text(), nullable=False),
        sa.Column("prerequisites", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("vocab_required", TEXTS, server_default=sa.text("'{}'::text[]"), nullable=False),
        sa.Column("vocab_permitted", TEXTS, server_default=sa.text("'{}'::text[]"), nullable=False),
        sa.Column("review_status", sa.Text(), server_default="draft", nullable=False),
        sa.Column("approvals", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("provenance", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=True),
        sa.CheckConstraint("band = 'L5'", name=op.f("ck_scene_script_band_l5")),
        sa.CheckConstraint(f"review_status IN {REVIEW}", name=op.f("ck_scene_script_review_status_values")),
        sa.CheckConstraint("review_status <> 'approved' OR jsonb_array_length(approvals) >= 2",
                           name=op.f("ck_scene_script_approved_needs_two")),
        *_no_latin("scene_script", "objective_hi", "instructions_hi"),
        sa.ForeignKeyConstraint(["scene_id"], ["scene.id"], name=op.f("fk_scene_script_scene_id_scene")),
        sa.PrimaryKeyConstraint("scene_id", name=op.f("pk_scene_script")),
    )
    for name, typ in (("question_hi", sa.Text()), ("options_hi", JSONB), ("answer_index", sa.Integer()),
                      ("reply_goal_hi", sa.Text()), ("hint_hi", sa.Text()), ("content_hash", sa.Text())):
        op.add_column("scene_line", sa.Column(name, typ, nullable=True))
    op.add_column("scene_line", sa.Column("replies", TEXTS, server_default=sa.text("'{}'::text[]"), nullable=False))
    op.add_column("scene_line", sa.Column("approvals", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.add_column("scene_line", sa.Column("provenance", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.create_check_constraint(op.f("ck_scene_line_approved_needs_two"), "scene_line",
                               "review_status <> 'approved' OR jsonb_array_length(approvals) >= 2")
    for c in ("question_hi", "reply_goal_hi", "hint_hi"):
        op.create_check_constraint(op.f(f"ck_scene_line_{c}_no_latin"), "scene_line", f"setu_no_latin({c})")
    op.create_check_constraint(op.f("ck_scene_line_options_hi_no_latin"), "scene_line",
                               "setu_no_latin(options_hi::text)")
    op.create_table(
        "scene_reply_variant",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("line_id", UUID, nullable=False),
        sa.Column("form", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="proposed", nullable=False),
        sa.Column("approvals", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("provenance", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('proposed', 'approved', 'rejected')",
                           name=op.f("ck_scene_reply_variant_status_values")),
        sa.CheckConstraint("status <> 'approved' OR jsonb_array_length(approvals) >= 2",
                           name=op.f("ck_scene_reply_variant_approved_needs_two")),
        *_no_latin("scene_reply_variant", "form"),
        sa.ForeignKeyConstraint(["line_id"], ["scene_line.id"], name=op.f("fk_scene_reply_variant_line_id_scene_line")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scene_reply_variant")),
    )
    op.create_table(
        "scene_event",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("session_id", UUID, nullable=False),
        sa.Column("scene_id", sa.Text(), nullable=False),
        sa.Column("exchange_id", UUID, nullable=True),
        sa.Column("event", sa.Text(), nullable=False),
        sa.Column("oov_words", TEXTS, server_default=sa.text("'{}'::text[]"), nullable=False),
        sa.Column("hindi_share", sa.Float(), nullable=True),
        sa.Column("data", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(f"event IN {EVENTS}", name=op.f("ck_scene_event_event_values")),
        sa.CheckConstraint("hindi_share IS NULL OR (hindi_share >= 0 AND hindi_share <= 1)",
                           name=op.f("ck_scene_event_hindi_share_range")),
        sa.ForeignKeyConstraint(["session_id"], ["session.id"], name=op.f("fk_scene_event_session_id_session")),
        sa.ForeignKeyConstraint(["scene_id"], ["scene.id"], name=op.f("fk_scene_event_scene_id_scene")),
        sa.ForeignKeyConstraint(["exchange_id"], ["exchange.id"], name=op.f("fk_scene_event_exchange_id_exchange")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scene_event")),
    )
    op.execute("DROP VIEW IF EXISTS learner_scene_line")
    for v in VIEWS:
        op.execute(v)
    for stmt in grants.grant_statements(grants.PLAN_V8, grants.VIEW_GRANTS_V5):
        op.execute(stmt)


def downgrade() -> None:
    for v in ("learner_scene_reply_variant", "learner_scene_line", "learner_scene_script"):
        op.execute(f"DROP VIEW IF EXISTS {v}")
    op.drop_table("scene_event")
    op.drop_table("scene_reply_variant")
    for c in ("approved_needs_two", "question_hi_no_latin", "reply_goal_hi_no_latin", "hint_hi_no_latin",
              "options_hi_no_latin"):
        op.drop_constraint(op.f(f"ck_scene_line_{c}"), "scene_line", type_="check")
    for c in ("question_hi", "options_hi", "answer_index", "reply_goal_hi", "hint_hi", "content_hash", "replies",
              "approvals", "provenance"):
        op.drop_column("scene_line", c)
    op.drop_table("scene_script")
    op.execute(OLD_LINE_VIEW)
    for stmt in grants.grant_statements(grants.PLAN_V7, grants.VIEW_GRANTS_V4):
        op.execute(stmt)
