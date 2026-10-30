"""TS-DB-02 and TS-AUTH-04: database roles enforce "only the OutcomeWriter writes learning state".

Roles (E-01): setu_read (agents' tools), setu_app (web layer operational records),
setu_writer (OutcomeWriter only), setu_content (importer and teacher review), setu_migrate (owner).
"""
import pytest
from sqlalchemy import text

from .helpers import as_role, fails, make_learner, make_rule, make_rule_version, ok

LEARNING_STATE = ["learner_skill_state", "learner_lexeme_card", "classmate_rule_state", "concept_cue_state",
                  "technique_effect", "fsrs_review_log", "verdict", "event_ledger"]


@pytest.fixture
def world(conn):
    learner = make_learner(conn)
    make_rule(conn)
    rv = make_rule_version(conn)
    ev = conn.execute(text("INSERT INTO event_ledger (actor, event_type, payload) VALUES ('checker', "
                           "'classmate_initialised', jsonb_build_object('learner_id', CAST(:l AS text), "
                           "'rule_id', 'HI-TE-001')) RETURNING id"), {"l": learner}).scalar_one()
    conn.execute(text("INSERT INTO classmate_rule_state (learner_id, rule_id, state, state_version, last_event_id) "
                      "VALUES (:l, 'HI-TE-001', 'unknown', 1, :e)"), {"l": learner, "e": ev})
    return {"learner": learner, "rv": rv, "ev": ev}


def _privilege(conn, role, table, priv):
    return conn.execute(text("SELECT has_table_privilege(:r, :t, :p)"),
                        {"r": role, "t": f"public.{table}", "p": priv}).scalar_one()


@pytest.mark.parametrize("role", ["setu_read", "setu_app", "setu_content"])
@pytest.mark.parametrize("table", LEARNING_STATE)
def test_only_writer_can_write_learning_state(conn, role, table):
    for priv in ("INSERT", "UPDATE", "DELETE", "TRUNCATE"):
        assert not _privilege(conn, role, table, priv), (role, table, priv)


@pytest.mark.parametrize("table", ["learner_skill_state", "learner_lexeme_card", "classmate_rule_state",
                                   "concept_cue_state", "technique_effect"])
def test_writer_can_insert_and_update_learning_state(conn, table):
    assert _privilege(conn, "setu_writer", table, "INSERT")
    assert _privilege(conn, "setu_writer", table, "UPDATE")
    assert not _privilege(conn, "setu_writer", table, "DELETE")


def test_read_role_cannot_write_anything(conn, world):
    with as_role(conn, "setu_read"):
        fails(conn, "UPDATE classmate_rule_state SET state = 'taught'", match="permission denied")
        fails(conn, "INSERT INTO event_ledger (actor, event_type, payload) VALUES ('checker', 'x', '{}')",
              match="permission denied")
        fails(conn, "UPDATE rule_version SET teacher_approved = true", match="permission denied")
        fails(conn, "DELETE FROM learner", match="permission denied")
        ok(conn, "SELECT state FROM classmate_rule_state")
        # Since migration 0003 the read role sees content only through the learner views (approved content).
        ok(conn, "SELECT title_hi FROM learner_rule_version")
        fails(conn, "SELECT title_hi FROM rule_version", match="permission denied")


def test_read_role_cannot_see_secrets_or_raw_learner_text(conn, world):
    with as_role(conn, "setu_read"):
        fails(conn, "SELECT passphrase_hash FROM learner", match="permission denied")
        ok(conn, "SELECT id, l1, l2, direction FROM learner")
        for table in ("attempt", "consent", "background", "model_call", "event_ledger", "teacher_resolution"):
            fails(conn, f"SELECT * FROM {table}", match="permission denied")


def test_app_role_records_attempts_but_cannot_grade_or_teach(conn, world):
    with as_role(conn, "setu_app"):
        s = ok(conn, "INSERT INTO session (learner_id, mode, config_snapshot, seed) VALUES (:l, 'learn', '{}', 1) "
               "RETURNING id", {"l": world["learner"]}).scalar_one()
        e = ok(conn, "INSERT INTO exchange (session_id, kind, source) VALUES (:s, 'own', 'template') RETURNING id",
               {"s": s}).scalar_one()
        a = ok(conn, "INSERT INTO attempt (exchange_id, n, raw_text, idempotency_key) VALUES (:e, 1, 'x', 'k') "
               "RETURNING id", {"e": e}).scalar_one()
        fails(conn, "INSERT INTO verdict (attempt_id, outcome, kind, checker_version) VALUES "
              "(:a, 'correct', 'own', 'v1')", {"a": a}, match="permission denied")
        fails(conn, "UPDATE classmate_rule_state SET state = 'taught'", match="permission denied")
        fails(conn, "UPDATE attempt SET raw_text = 'y'", match="permission denied")


def test_content_role_cannot_touch_learners_or_state(conn, world):
    with as_role(conn, "setu_content"):
        ok(conn, "INSERT INTO rule (id, direction, contrast_area) VALUES ('HI-TE-002', 'HI->TE', 'copula')")
        fails(conn, "UPDATE classmate_rule_state SET state = 'taught'", match="permission denied")
        fails(conn, "SELECT * FROM attempt", match="permission denied")
        fails(conn, "SELECT passphrase_hash FROM learner", match="permission denied")


def test_writer_appends_to_ledger_and_updates_state_but_cannot_edit_content(conn, world):
    with as_role(conn, "setu_writer"):
        ev = ok(conn, "INSERT INTO event_ledger (actor, event_type, payload) VALUES ('checker', 'teach', '{}') "
                "RETURNING id").scalar_one()
        # The writer has the UPDATE privilege, but the guard trigger (slice 1.3) still refuses a "taught"
        # change that no checked correct fix backs.
        fails(conn, "UPDATE classmate_rule_state SET state = 'taught', state_version = 2, last_event_id = :e",
              {"e": ev}, match="classmate state")
        fails(conn, "UPDATE event_ledger SET payload = '{}'", match="permission denied")
        fails(conn, "INSERT INTO rule (id, direction, contrast_area) VALUES ('HI-TE-003', 'HI->TE', 'x')",
              match="permission denied")
        fails(conn, "SELECT passphrase_hash FROM learner", match="permission denied")


def test_public_has_no_table_privileges(conn):
    rows = conn.execute(text("SELECT table_name, privilege_type FROM information_schema.role_table_grants "
                             "WHERE grantee = 'PUBLIC' AND table_schema = 'public'")).all()
    assert rows == []


def test_every_table_is_covered_by_the_grant_plan(conn):
    # A new table without an explicit grant decision must fail this test (no silent default privileges).
    from setu.store.grants import GRANT_PLAN
    from setu.store.models import Base

    planned = set()
    for tables in GRANT_PLAN.values():
        for spec in tables:
            planned.add(spec[0])
    assert set(Base.metadata.tables) <= planned | {"alembic_version"}
