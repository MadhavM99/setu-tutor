"""TS-DB-03: the event ledger is append-only and hash-chained (E-02); content versions are immutable
(data-model.md §4, X-BANK-06); verdicts keep their original outcome (teacher-console.md F7).
"""
import itertools

from sqlalchemy import text

from .helpers import fails, make_learner, make_rule, make_rule_version, ok


def _append(conn, n=3):
    ids = []
    for i in range(n):
        ids.append(conn.execute(text("INSERT INTO event_ledger (actor, event_type, payload) VALUES "
                                     "('checker', 'teach', CAST(:p AS jsonb)) RETURNING id"),
                                {"p": f'{{"i": {i}}}'}).scalar_one())
    return ids


def test_hash_chain_links_each_event_to_the_previous(conn):
    ids = _append(conn)
    rows = conn.execute(text("SELECT id, prev_hash, hash FROM event_ledger WHERE id = ANY(:ids) ORDER BY id"),
                        {"ids": ids}).all()
    for prev, cur in itertools.pairwise(rows):
        assert cur.prev_hash == prev.hash
    assert all(len(r.hash) == 64 for r in rows)
    assert conn.execute(text("SELECT setu_verify_ledger()")).scalar_one() is None


def test_client_supplied_hashes_and_timestamps_are_ignored(conn):
    _append(conn, 1)
    row = conn.execute(text("INSERT INTO event_ledger (actor, event_type, payload, prev_hash, hash, ts) VALUES "
                            "('checker', 'x', '{}', 'forged', 'forged', '2000-01-01') "
                            "RETURNING prev_hash, hash, ts")).one()
    assert row.hash != "forged" and row.prev_hash != "forged"
    assert row.ts.year >= 2026
    assert conn.execute(text("SELECT setu_verify_ledger()")).scalar_one() is None


def test_ledger_rejects_update_delete_and_truncate_even_for_the_owner(conn):
    _append(conn, 2)
    fails(conn, "UPDATE event_ledger SET payload = '{}'", match="append-only")
    fails(conn, "DELETE FROM event_ledger", match="append-only")
    fails(conn, "TRUNCATE event_ledger CASCADE", match="append-only")


def test_actor_must_be_checker_scheduler_or_a_teacher(conn):
    fails(conn, "INSERT INTO event_ledger (actor, event_type, payload) VALUES ('model', 'teach', '{}')")
    fails(conn, "INSERT INTO event_ledger (actor, event_type, payload) VALUES ('raju', 'teach', '{}')")
    ok(conn, "INSERT INTO event_ledger (actor, event_type, payload) VALUES ('teacher:t-1', 'resolve', '{}')")
    ok(conn, "INSERT INTO event_ledger (actor, event_type, payload) VALUES ('scheduler', 'forget', '{}')")


def test_tampering_is_detected_by_verification(conn):
    ids = _append(conn, 3)
    # Simulate an attacker with superuser rights who bypasses the triggers.
    conn.execute(text("SET LOCAL session_replication_role = replica"))
    conn.execute(text("UPDATE event_ledger SET payload = '{\"i\": 99}' WHERE id = :i"), {"i": ids[1]})
    conn.execute(text("SET LOCAL session_replication_role = origin"))
    assert conn.execute(text("SELECT setu_verify_ledger()")).scalar_one() == ids[1]


def test_rule_version_is_immutable(conn):
    make_rule(conn)
    make_rule_version(conn)
    fails(conn, "UPDATE rule_version SET title_hi = 'नया'", match="immutable")
    fails(conn, "UPDATE rule_version SET teacher_approved = true", match="immutable")
    fails(conn, "DELETE FROM rule_version", match="immutable")


def test_item_version_hint_and_verdict_are_immutable(conn):
    make_rule(conn)
    rv = make_rule_version(conn)
    conn.execute(text("INSERT INTO item (id, rule_id) VALUES ('HI-TE-001-a', 'HI-TE-001')"))
    conn.execute(text("INSERT INTO item_version (item_id, version, rule_version_id, correct_form, pool, "
                      "review_status) VALUES ('HI-TE-001-a', 1, :rv, 'నువ్వు వస్తావా', 'practice', 'draft')"),
                 {"rv": rv})
    conn.execute(text("INSERT INTO hint (rule_version_id, type, text_hi, status, validated_no_answer) VALUES "
                      "(:rv, 'l1_rule', 'संकेत', 'draft', false)"), {"rv": rv})
    fails(conn, "UPDATE item_version SET correct_form = 'x'", match="immutable")
    fails(conn, "UPDATE hint SET text_hi = 'x'", match="immutable")

    learner = make_learner(conn)
    s = conn.execute(text("INSERT INTO session (learner_id, mode, config_snapshot, seed) VALUES "
                          "(:l, 'learn', '{}', 1) RETURNING id"), {"l": learner}).scalar_one()
    e = conn.execute(text("INSERT INTO exchange (session_id, kind, source) VALUES (:s, 'own', 'template') "
                          "RETURNING id"), {"s": s}).scalar_one()
    a = conn.execute(text("INSERT INTO attempt (exchange_id, n, raw_text, idempotency_key) VALUES "
                          "(:e, 1, 'x', 'k') RETURNING id"), {"e": e}).scalar_one()
    conn.execute(text("INSERT INTO verdict (attempt_id, outcome, kind, checker_version) VALUES "
                      "(:a, 'wrong', 'own', 'v1')"), {"a": a})
    fails(conn, "UPDATE verdict SET outcome = 'correct'", match="immutable")


def test_memory_aid_content_is_immutable_and_status_follows_its_state_machine(conn):
    conn.execute(text("INSERT INTO concept (id, kind, content_ref, fact_sheet) VALUES ('c-ళ', 'letter', 'ళ', '{}')"))
    aid = conn.execute(text("INSERT INTO memory_aid (concept_id, technique, version, text_hi, review_status) "
                            "VALUES ('c-ళ', 'shape', 1, 'कहानी', 'draft') RETURNING id")).scalar_one()
    fails(conn, "UPDATE memory_aid SET text_hi = 'दूसरी' WHERE id = :a", {"a": aid}, match="immutable")
    fails(conn, "UPDATE memory_aid SET review_status = 'approved' WHERE id = :a", {"a": aid}, match="transition")
    ok(conn, "UPDATE memory_aid SET review_status = 'in_review' WHERE id = :a", {"a": aid})
    ok(conn, "UPDATE memory_aid SET review_status = 'approved', reviewers = '[\"t1\"]' WHERE id = :a", {"a": aid})
    fails(conn, "UPDATE memory_aid SET review_status = 'draft' WHERE id = :a", {"a": aid}, match="transition")
    fails(conn, "UPDATE memory_aid SET review_status = 'retired' WHERE id = :a", {"a": aid}, match="retired_has_reason")
    ok(conn, "UPDATE memory_aid SET review_status = 'retired', retired_reason = 'भ्रम पैदा करता है' WHERE id = :a",
       {"a": aid})
    fails(conn, "DELETE FROM memory_aid WHERE id = :a", {"a": aid}, match="immutable")
