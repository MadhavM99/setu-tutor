"""accounts (invites, sessions, login attempts), consent guard on sessions, consent withdrawal

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from setu.store import grants, sql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

TS = postgresql.TIMESTAMP(timezone=True)


def upgrade() -> None:
    op.create_table(
        "invite",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("code_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("cohort", sa.Text(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", TS, nullable=False),
        sa.Column("used_at", TS, nullable=True),
        sa.Column("used_by", sa.UUID(), nullable=True),
        sa.CheckConstraint("role IN ('learner', 'teacher', 'researcher', 'admin')", name=op.f("ck_invite_role_values")),
        sa.CheckConstraint("(used_at IS NULL) = (used_by IS NULL)", name=op.f("ck_invite_used_together")),
        sa.ForeignKeyConstraint(["created_by"], ["learner.id"], name=op.f("fk_invite_created_by_learner")),
        sa.ForeignKeyConstraint(["used_by"], ["learner.id"], name=op.f("fk_invite_used_by_learner")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invite")),
        sa.UniqueConstraint("code_hash", name=op.f("uq_invite_code_hash")),
    )
    op.create_table(
        "auth_session",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("learner_id", sa.UUID(), nullable=False),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", TS, nullable=False),
        sa.Column("revoked_at", TS, nullable=True),
        sa.CheckConstraint("expires_at > created_at", name=op.f("ck_auth_session_expires_after_created")),
        sa.ForeignKeyConstraint(["learner_id"], ["learner.id"], name=op.f("fk_auth_session_learner_id_learner")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_session")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_auth_session_token_hash")),
    )
    op.create_table(
        "login_attempt",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("handle", sa.Text(), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("ts", TS, server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_login_attempt")),
    )
    op.add_column("attempt", sa.Column("redacted_at", TS, nullable=True))
    op.create_check_constraint(op.f("ck_attempt_redacted_is_empty"), "attempt",
                               "redacted_at IS NULL OR (raw_text = '' AND normalised_text IS NULL)")
    op.create_check_constraint(op.f("ck_consent_scope_not_empty"), "consent", "cardinality(scope) >= 1")
    for stmt in sql.CONSENT_GUARDS:
        op.execute(stmt)
    for stmt in grants.grant_statements(grants.PLAN_V3, grants.VIEW_GRANTS):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in grants.grant_statements(grants.PLAN_V2, grants.VIEW_GRANTS):
        op.execute(stmt)
    for stmt in sql.CONSENT_GUARDS_DOWN:
        op.execute(stmt)
    op.drop_constraint(op.f("ck_consent_scope_not_empty"), "consent", type_="check")
    op.drop_constraint(op.f("ck_attempt_redacted_is_empty"), "attempt", type_="check")
    op.drop_column("attempt", "redacted_at")
    op.drop_table("login_attempt")
    op.drop_table("auth_session")
    op.drop_table("invite")
