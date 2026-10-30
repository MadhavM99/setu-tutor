"""R-INPUT in the database (migration 0005): every attempt records how it was answered and what helped, and only
independent, cue-free fixes can teach the classmate (TS-DB-INPUT-*, TS-CLS-INPUT-*, TS-SCHED-MEM-05)."""
import json
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from setu.domain.checker import _issue_verdict as issue_verdict  # tests mint arbitrary verdicts

from .helpers import approvals, make_learner

KEY = b"test-resolution-key-0123456789abcdef"


@pytest.fixture
def world(engine):
    with engine.begin() as c:
        learner = make_learner(c, handle=f"h-{uuid.uuid4().hex[:10]}")
        rule_id = f"HI-TE-{uuid.uuid4().int % 400 + 100}"
        while c.execute(text("SELECT 1 FROM rule WHERE id = :r"), {"r": rule_id}).first():
            rule_id = f"HI-TE-{uuid.uuid4().int % 400 + 100}"
        c.execute(text("INSERT INTO rule (id, direction, contrast_area) VALUES (:r, 'HI->TE', 'q')"), {"r": rule_id})
        rv = c.execute(text("INSERT INTO rule_version (rule_id, version, title_hi, l1_explanation_hi, band, validity, "
                            "learner_evidence, lifecycle, teacher_approved, speaker_approvals) VALUES (:r, 1, 'सवाल', "
                            "'व्याख्या', 'L4', 'verified', 'predicted', 'active', true, CAST(:a AS jsonb)) RETURNING id"),
                       {"r": rule_id, "a": approvals("s1", "s2")}).scalar_one()
        s = c.execute(text("INSERT INTO session (learner_id, mode, config_snapshot, seed) VALUES (:l, 'learn', '{}', 1) "
                           "RETURNING id"), {"l": learner}).scalar_one()
        e = c.execute(text("INSERT INTO exchange (session_id, kind, rule_version_id, planted, source) VALUES "
                           "(:s, 'correction', :rv, true, 'bank') RETURNING id"), {"s": s, "rv": rv}).scalar_one()
    return {"learner": learner, "rule": rule_id, "exchange": e}


def attempt(engine, world, *, mode="typed", cue=0, aids=(), after_reveal=False, n=None):
    with engine.begin() as c:
        n = n or (c.execute(text("SELECT coalesce(max(n), 0) + 1 FROM attempt WHERE exchange_id = :e"),
                            {"e": world["exchange"]}).scalar_one())
        return c.execute(text("INSERT INTO attempt (exchange_id, n, raw_text, response_mode, cue_level, assistance, "
                              "after_reveal, idempotency_key) VALUES (:e, :n, 'x', :m, :cue, CAST(:a AS jsonb), :ar, :k) "
                              "RETURNING id"),
                         {"e": world["exchange"], "n": n, "m": mode, "cue": cue, "a": json.dumps(list(aids)),
                          "ar": after_reveal, "k": uuid.uuid4().hex}).scalar_one()


def refused(engine, world, **kw):
    with pytest.raises(DBAPIError):
        attempt(engine, world, **kw)


# ---------------------------------------------------------------- TS-DB-INPUT


def test_response_mode_and_aids_are_closed_sets(engine, world):
    refused(engine, world, mode="telepathy")
    refused(engine, world, aids=("vibes",), cue=1)


def test_cue_level_matches_the_recall_cues_shown(engine, world):
    refused(engine, world, aids=("hint",), cue=0)              # a hint was shown: not cue-free
    refused(engine, world, aids=(), cue=2)                     # a cue level with no cue recorded
    attempt(engine, world, aids=("hint",), cue=1)
    attempt(engine, world, aids=("reading_aid", "prompt_audio"), cue=0)  # presentation aids are not recall cues


def test_multiple_choice_and_tiles_record_their_assistance(engine, world):
    refused(engine, world, mode="multiple_choice", cue=1, aids=("hint",))   # must list choices
    refused(engine, world, mode="multiple_choice", cue=0)
    attempt(engine, world, mode="multiple_choice", cue=1, aids=("choices",))
    refused(engine, world, mode="tiles", cue=1, aids=("hint",))             # must list tiles
    attempt(engine, world, mode="tiles", cue=1, aids=("tiles",))
    attempt(engine, world, mode="onscreen_keyboard", cue=0)                 # the full keyboard is not a cue


# ---------------------------------------------------------------- TS-CLS-INPUT


def writer(engine):
    from setu.store.outcome_writer import OutcomeWriter

    return OutcomeWriter(engine, resolution_key=KEY)


def classmate(engine, world):
    with engine.connect() as c:
        return c.execute(text("SELECT state FROM classmate_rule_state WHERE learner_id = :l AND rule_id = :r"),
                         {"l": world["learner"], "r": world["rule"]}).scalar()


@pytest.mark.parametrize("kw,kind", [
    ({"mode": "multiple_choice", "cue": 1, "aids": ("choices",)}, "recognition"),
    ({"mode": "multiple_choice", "cue": 1, "aids": ("choices",)}, "fix"),   # even if mislabelled as a fix
    ({"mode": "tiles", "cue": 1, "aids": ("tiles",)}, "fix"),
    ({"mode": "typed", "cue": 1, "aids": ("hint",)}, "fix"),
    ({"mode": "typed", "cue": 0, "after_reveal": True}, "fix"),
])
def test_assisted_answers_never_teach_the_classmate(engine, world, kw, kind):
    a = attempt(engine, world, **kw)
    rec = writer(engine).record_verdict(issue_verdict(attempt_id=a, outcome="correct", kind=kind, reason_code="t"))
    assert rec.classmate_change is None and classmate(engine, world) is None


@pytest.mark.parametrize("mode", ["typed", "onscreen_keyboard", "spoken"])
def test_independent_cue_free_fixes_teach_the_classmate(engine, world, mode):
    a = attempt(engine, world, mode=mode, aids=("reading_aid",))
    rec = writer(engine).record_verdict(issue_verdict(attempt_id=a, outcome="correct", kind="fix", reason_code="t"))
    assert rec.classmate_change == "taught" and classmate(engine, world) == "taught"


def test_the_trigger_refuses_teaching_backed_by_an_assisted_answer(engine, world):
    a = attempt(engine, world, mode="tiles", cue=1, aids=("tiles",))
    v = writer(engine).record_verdict(issue_verdict(attempt_id=a, outcome="correct", kind="fix", reason_code="t"))
    c = engine.connect()
    c.begin()
    try:
        c.execute(text("SET LOCAL ROLE setu_writer"))
        ev = c.execute(text("INSERT INTO event_ledger (actor, event_type, payload) VALUES ('checker', "
                            "'classmate_taught', CAST(:p AS jsonb)) RETURNING id"),
                       {"p": json.dumps({"learner_id": str(world["learner"]), "rule_id": world["rule"],
                                         "verdict_id": str(v.verdict_id)})}).scalar_one()
        with pytest.raises(DBAPIError) as e:
            c.execute(text("INSERT INTO classmate_rule_state (learner_id, rule_id, state, state_version, "
                           "last_event_id) VALUES (:l, :r, 'taught', 1, :e)"),
                      {"l": world["learner"], "r": world["rule"], "e": ev})
        assert "classmate" in str(e.value.orig)
    finally:
        c.rollback()
        c.close()


def test_recognition_is_a_verdict_kind(engine, world):
    a = attempt(engine, world, mode="multiple_choice", cue=1, aids=("choices",))
    writer(engine).record_verdict(issue_verdict(attempt_id=a, outcome="correct", kind="recognition", reason_code="t"))
    with engine.connect() as c:
        assert c.execute(text("SELECT kind FROM verdict WHERE attempt_id = :a"), {"a": a}).scalar_one() == "recognition"


# ---------------------------------------------------------------- TS-SCHED-MEM-05


def test_fsrs_log_inherits_the_attempts_cue_level(engine, world):
    a = attempt(engine, world, mode="tiles", cue=1, aids=("tiles",))
    rec = writer(engine).record_verdict(issue_verdict(attempt_id=a, outcome="correct", kind="recall", reason_code="t"))
    with engine.begin() as c:
        card = c.execute(text("INSERT INTO learner_lexeme_card (learner_id, card_kind, card_ref, modality) VALUES "
                              "(:l, 'letter', :r, 'RCL') RETURNING id"),
                         {"l": world["learner"], "r": uuid.uuid4().hex[:6]}).scalar_one()
    with pytest.raises(DBAPIError) as e, engine.begin() as c:
        c.execute(text("INSERT INTO fsrs_review_log (card_id, verdict_id, rating, cue_level) VALUES (:c, :v, 3, 0)"),
                  {"c": card, "v": rec.verdict_id})
    assert "cue" in str(e.value.orig)
    with engine.begin() as c:
        c.execute(text("INSERT INTO fsrs_review_log (card_id, verdict_id, rating, cue_level) VALUES (:c, :v, 2, 1)"),
                  {"c": card, "v": rec.verdict_id})
