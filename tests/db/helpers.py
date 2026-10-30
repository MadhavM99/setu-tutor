"""Helpers for real-Postgres tests (rows are inserted inside the test transaction)."""
import json
import uuid
from contextlib import contextmanager

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError


@contextmanager
def as_role(conn, role):
    conn.execute(text(f"SET ROLE {role}"))
    try:
        yield conn
    finally:
        conn.execute(text("RESET ROLE"))


def fails(conn, sql, params=None, match=None):
    """Run `sql` in a savepoint and assert that Postgres rejects it; return the error text."""
    sp = conn.begin_nested()
    try:
        conn.execute(text(sql), params or {})
    except DBAPIError as e:
        sp.rollback()
        msg = str(e.orig)
        if match:
            assert match in msg, msg
        return msg
    sp.rollback()
    raise AssertionError(f"expected failure, but it succeeded: {sql}")


def ok(conn, sql, params=None):
    sp = conn.begin_nested()
    result = conn.execute(text(sql), params or {})
    sp.commit()
    return result


# ---------- fixture rows (inserted as the owner, inside the test transaction) ----------


def make_learner(conn, handle=None, role="learner", consent=True):
    """A learner row; with `consent`, also an active pilot consent so sessions may start (migration 0004)."""
    learner_id = conn.execute(
        text(
            "INSERT INTO learner (handle, passphrase_hash, l1, l2, direction, role) "
            "VALUES (:h, 'argon2-placeholder', 'hi', 'te', 'HI->TE', :r) RETURNING id"
        ),
        {"h": handle or f"h-{uuid.uuid4().hex[:8]}", "r": role},
    ).scalar_one()
    if consent:
        conn.execute(text("INSERT INTO consent (learner_id, form_version, scope) VALUES (:l, 'pilot-v1', "
                          "ARRAY['pilot'])"), {"l": learner_id})
    return learner_id


def make_rule(conn, rule_id="HI-TE-001", direction="HI->TE"):
    conn.execute(
        text("INSERT INTO rule (id, direction, contrast_area) VALUES (:i, :d, 'polar_question')"),
        {"i": rule_id, "d": direction},
    )
    return rule_id


def make_rule_version(conn, rule_id="HI-TE-001", version=1, **cols):
    base = {
        "validity": "uncertain",
        "learner_evidence": "model_predicted",
        "lifecycle": "draft",
        "teacher_approved": False,
        "speaker_approvals": "[]",
    }
    base.update(cols)
    return conn.execute(
        text(
            "INSERT INTO rule_version (rule_id, version, title_hi, l1_explanation_hi, band, validity, "
            "learner_evidence, lifecycle, teacher_approved, speaker_approvals) VALUES (:rule_id, :version, "
            "'सवाल', 'व्याख्या', 'L4', :validity, :learner_evidence, :lifecycle, :teacher_approved, "
            "CAST(:speaker_approvals AS jsonb)) RETURNING id"
        ),
        {"rule_id": rule_id, "version": version, **base},
    ).scalar_one()


def approvals(*reviewers, lang="te"):
    return json.dumps([{"lang": lang, "reviewer": r, "date": "2026-10-31"} for r in reviewers])
