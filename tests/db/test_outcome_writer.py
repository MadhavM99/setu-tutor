"""OutcomeWriter against real Postgres (P-SESS-11, P8b-01, X-CLS-NOTRUST, architecture §2–5).

The writer commits through its own connections, so fixtures commit too. Every test makes fresh learners and
rules, so tests stay independent even though committed rows (and ledger events) accumulate.
"""
import uuid

import pytest
from sqlalchemy import text

from .helpers import approvals

KEY = b"test-resolution-key-0123456789abcdef"


@pytest.fixture
def writer(engine):
    from setu.store.outcome_writer import OutcomeWriter

    return OutcomeWriter(engine, resolution_key=KEY)


def _rule(c, direction="HI->TE"):
    rule_id = f"HI-TE-{uuid.uuid4().int % 500 + 500}"
    while c.execute(text("SELECT 1 FROM rule WHERE id = :r"), {"r": rule_id}).first():
        rule_id = f"HI-TE-{uuid.uuid4().int % 500 + 500}"
    c.execute(text("INSERT INTO rule (id, direction, contrast_area) VALUES (:r, :d, 'polar_question')"),
              {"r": rule_id, "d": direction})
    rv = c.execute(text("INSERT INTO rule_version (rule_id, version, title_hi, l1_explanation_hi, band, validity, "
                        "learner_evidence, lifecycle, teacher_approved, speaker_approvals) VALUES (:r, 1, 'सवाल', "
                        "'व्याख्या', 'L4', 'verified', 'predicted', 'active', true, CAST(:a AS jsonb)) RETURNING id"),
                   {"r": rule_id, "a": approvals("s1", "s2")}).scalar_one()
    return rule_id, rv


def _person(c, role="learner"):
    from .helpers import make_learner

    return make_learner(c, handle=f"h-{uuid.uuid4().hex[:10]}", role=role)


def _attempt(c, learner, rv, kind="correction", planted=True):
    s = c.execute(text("INSERT INTO session (learner_id, mode, config_snapshot, seed) VALUES (:l, 'learn', '{}', 1) "
                       "RETURNING id"), {"l": learner}).scalar_one()
    e = c.execute(text("INSERT INTO exchange (session_id, kind, rule_version_id, planted, source) VALUES "
                       "(:s, :k, :rv, :p, 'bank') RETURNING id"), {"s": s, "k": kind, "rv": rv, "p": planted}
                  ).scalar_one()
    return c.execute(text("INSERT INTO attempt (exchange_id, n, raw_text, idempotency_key) VALUES (:e, 1, 'x', :k) "
                          "RETURNING id"), {"e": e, "k": uuid.uuid4().hex}).scalar_one()


@pytest.fixture
def world(engine):
    with engine.begin() as c:
        learner = _person(c)
        teacher = _person(c, role="teacher")
        rule_id, rv = _rule(c)
    return {"learner": learner, "teacher": teacher, "rule": rule_id, "rv": rv}


def new_attempt(engine, world, **kw):
    with engine.begin() as c:
        return _attempt(c, world["learner"], world["rv"], **kw)


def verdict(attempt_id, outcome="correct", kind="fix"):
    from setu.domain.checker import _issue_verdict as issue_verdict  # tests mint arbitrary verdicts

    return issue_verdict(attempt_id=attempt_id, outcome=outcome, kind=kind, reason_code="test")


def classmate(engine, world):
    with engine.connect() as c:
        return c.execute(text("SELECT state, state_version FROM classmate_rule_state WHERE learner_id = :l "
                              "AND rule_id = :r"), {"l": world["learner"], "r": world["rule"]}).first()


def ledger_ok(engine):
    with engine.connect() as c:
        return c.execute(text("SELECT setu_verify_ledger()")).scalar_one() is None


# ---------------------------------------------------------------- the classmate learns only from a checked fix


def test_correct_fix_of_a_planted_error_teaches_the_classmate(engine, writer, world):
    rec = writer.record_verdict(verdict(new_attempt(engine, world)))
    assert rec.classmate_change == "taught"
    assert tuple(classmate(engine, world)) == ("taught", 1)
    with engine.connect() as c:
        ev = c.execute(text("SELECT actor, event_type, payload FROM event_ledger WHERE id = :i"),
                       {"i": rec.classmate_event_id}).one()
    assert ev.actor == "checker" and ev.event_type == "classmate_taught"
    assert ev.payload["verdict_id"] == str(rec.verdict_id)
    assert ledger_ok(engine)


@pytest.mark.parametrize("outcome,kind,exchange_kind,planted", [
    ("wrong", "fix", "correction", True),
    ("partial", "fix", "correction", True),
    ("unsure", "fix", "correction", True),
    ("correct", "explanation", "correction", True),   # answering "why?" changes nothing (P8b-02)
    ("correct", "no_error", "no_error", False),       # confirming a correct sentence teaches nothing
    ("correct", "own", "own", False),                 # the learner's own sentence is not teaching Raju
])
def test_nothing_else_changes_what_the_classmate_knows(engine, writer, world, outcome, kind, exchange_kind, planted):
    a = new_attempt(engine, world, kind=exchange_kind, planted=planted)
    rec = writer.record_verdict(verdict(a, outcome=outcome, kind=kind))
    assert rec.classmate_change is None
    assert classmate(engine, world) is None


def test_unsure_goes_to_the_teacher_queue_and_changes_nothing(engine, writer, world):
    rec = writer.record_verdict(verdict(new_attempt(engine, world), outcome="unsure"))
    assert rec.queue_item_id is not None
    with engine.connect() as c:
        status = c.execute(text("SELECT status FROM teacher_queue_item WHERE id = :q"),
                           {"q": rec.queue_item_id}).scalar_one()
        skill_rows = c.execute(text("SELECT count(*) FROM learner_skill_state WHERE learner_id = :l"),
                               {"l": world["learner"]}).scalar_one()
    assert status == "open" and skill_rows == 0
    assert classmate(engine, world) is None


def test_recording_is_idempotent_and_refuses_a_conflicting_verdict(engine, writer, world):
    from setu.store.outcome_writer import ConflictingVerdict

    a = new_attempt(engine, world)
    v = verdict(a)
    first = writer.record_verdict(v)
    again = writer.record_verdict(v)
    assert again.verdict_id == first.verdict_id and again.classmate_change is None
    assert tuple(classmate(engine, world)) == ("taught", 1)
    with pytest.raises(ConflictingVerdict):
        writer.record_verdict(verdict(a, outcome="wrong"))


def test_writer_works_with_writer_privileges_only(writer):
    assert writer.effective_role() == "setu_writer"


# ---------------------------------------------------------------- forgetting and re-teaching


def test_forgetting_then_reteaching(engine, writer, world):
    from setu.domain.scheduler import decide_forget

    writer.record_verdict(verdict(new_attempt(engine, world)))
    decision = decide_forget(learner_id=world["learner"], rule_id=world["rule"], predicted_recall=0.31,
                             tracker_version="t")
    assert writer.apply_forget(decision) == "forgotten"
    assert tuple(classmate(engine, world)) == ("forgotten", 2)
    assert writer.apply_forget(decision) is None  # nothing left to forget
    writer.record_verdict(verdict(new_attempt(engine, world)))
    assert tuple(classmate(engine, world)) == ("taught", 3)
    assert ledger_ok(engine)


def test_forget_does_nothing_for_a_rule_the_classmate_never_learned(writer, world):
    from setu.domain.scheduler import decide_forget

    d = decide_forget(learner_id=world["learner"], rule_id=world["rule"], predicted_recall=0.1, tracker_version="t")
    assert writer.apply_forget(d) is None


# ---------------------------------------------------------------- database-side defence in depth


def _as_writer(engine):
    c = engine.connect()
    c.begin()
    c.execute(text("SET LOCAL ROLE setu_writer"))
    return c


def _event(c, event_type, payload, actor="checker"):
    import json

    return c.execute(text("INSERT INTO event_ledger (actor, event_type, payload) VALUES (:a, :t, CAST(:p AS jsonb)) "
                          "RETURNING id"), {"a": actor, "t": event_type, "p": json.dumps(payload)}).scalar_one()


@pytest.mark.parametrize("bad", ["no_verdict", "wrong_verdict", "other_rule", "wrong_event_type"])
def test_direct_sql_cannot_teach_without_a_correct_fix(engine, writer, world, bad):
    from sqlalchemy.exc import DBAPIError

    a = new_attempt(engine, world)
    wrong = writer.record_verdict(verdict(a, outcome="wrong"))
    payload = {"learner_id": str(world["learner"]), "rule_id": world["rule"]}
    if bad == "wrong_verdict":
        payload["verdict_id"] = str(wrong.verdict_id)
    if bad == "other_rule":
        with engine.begin() as c:
            _, other_rv = _rule(c)
            other = _attempt(c, world["learner"], other_rv)
        ok_other = writer.record_verdict(verdict(other))
        payload["verdict_id"] = str(ok_other.verdict_id)
    c = _as_writer(engine)
    try:
        ev = _event(c, "classmate_note" if bad == "wrong_event_type" else "classmate_taught", payload)
        with pytest.raises(DBAPIError) as e:
            c.execute(text("INSERT INTO classmate_rule_state (learner_id, rule_id, state, state_version, "
                           "last_event_id) VALUES (:l, :r, 'taught', 1, :e)"),
                      {"l": world["learner"], "r": world["rule"], "e": ev})
        assert "classmate" in str(e.value.orig)
    finally:
        c.rollback()
        c.close()


def test_direct_sql_cannot_forget_without_the_scheduler_or_skip_versions(engine, writer, world):
    from sqlalchemy.exc import DBAPIError

    writer.record_verdict(verdict(new_attempt(engine, world)))
    payload = {"learner_id": str(world["learner"]), "rule_id": world["rule"], "predicted_recall": 0.2}
    for actor, version in (("checker", 2), ("scheduler", 5)):
        c = _as_writer(engine)
        try:
            ev = _event(c, "classmate_forgot", payload, actor=actor)
            with pytest.raises(DBAPIError):
                c.execute(text("UPDATE classmate_rule_state SET state = 'forgotten', state_version = :v, "
                               "last_event_id = :e WHERE learner_id = :l AND rule_id = :r"),
                          {"v": version, "e": ev, "l": world["learner"], "r": world["rule"]})
        finally:
            c.rollback()
            c.close()


def test_an_old_verdict_cannot_be_replayed_after_forgetting(engine, writer, world):
    from sqlalchemy.exc import DBAPIError

    from setu.domain.scheduler import decide_forget

    first = writer.record_verdict(verdict(new_attempt(engine, world)))
    writer.apply_forget(decide_forget(learner_id=world["learner"], rule_id=world["rule"], predicted_recall=0.2,
                                      tracker_version="t"))
    c = _as_writer(engine)
    try:
        ev = _event(c, "classmate_taught", {"learner_id": str(world["learner"]), "rule_id": world["rule"],
                                            "verdict_id": str(first.verdict_id)})
        with pytest.raises(DBAPIError) as e:
            c.execute(text("UPDATE classmate_rule_state SET state = 'taught', state_version = 3, last_event_id = :e "
                           "WHERE learner_id = :l AND rule_id = :r"),
                      {"e": ev, "l": world["learner"], "r": world["rule"]})
        assert "stale" in str(e.value.orig)
    finally:
        c.rollback()
        c.close()


# ---------------------------------------------------------------- teacher resolutions


def _unsure_in_queue(engine, writer, world):
    return writer.record_verdict(verdict(new_attempt(engine, world), outcome="unsure"))


def _signed(queue_item_id, teacher_id, outcome="correct", key=KEY):
    from setu.store.resolution import TeacherResolution

    return TeacherResolution.sign(key=key, queue_item_id=queue_item_id, teacher_id=teacher_id, outcome=outcome,
                                  note_hi="सही है")


def test_teacher_resolution_settles_the_queue_and_can_teach_the_classmate(engine, writer, world):
    rec = _unsure_in_queue(engine, writer, world)
    out = writer.apply_resolution(_signed(rec.queue_item_id, world["teacher"]))
    assert out.classmate_change == "taught"
    assert tuple(classmate(engine, world)) == ("taught", 1)
    with engine.connect() as c:
        status = c.execute(text("SELECT status FROM teacher_queue_item WHERE id = :q"),
                           {"q": rec.queue_item_id}).scalar_one()
        actor = c.execute(text("SELECT actor FROM event_ledger WHERE id = :e"),
                          {"e": out.resolution_event_id}).scalar_one()
    assert status == "resolved" and actor == f"teacher:{world['teacher']}"
    assert ledger_ok(engine)


def test_wrong_resolution_closes_the_item_without_teaching(engine, writer, world):
    rec = _unsure_in_queue(engine, writer, world)
    out = writer.apply_resolution(_signed(rec.queue_item_id, world["teacher"], outcome="wrong"))
    assert out.classmate_change is None
    assert classmate(engine, world) is None


def test_resolution_is_refused_when_unsigned_not_a_teacher_or_already_settled(engine, writer, world):
    from setu.store.outcome_writer import ResolutionRefused
    from setu.store.resolution import BadSignature

    rec = _unsure_in_queue(engine, writer, world)
    with pytest.raises(BadSignature):
        writer.apply_resolution(_signed(rec.queue_item_id, world["teacher"], key=b"x" * 32))
    with pytest.raises(ResolutionRefused):
        writer.apply_resolution(_signed(rec.queue_item_id, world["learner"]))  # a learner is not a teacher
    writer.apply_resolution(_signed(rec.queue_item_id, world["teacher"]))
    with pytest.raises(ResolutionRefused):
        writer.apply_resolution(_signed(rec.queue_item_id, world["teacher"], outcome="wrong"))
    assert tuple(classmate(engine, world)) == ("taught", 1)
