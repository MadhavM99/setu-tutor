"""Scheduler updates through the OutcomeWriter (migration 0007; TS-SCHED-*, TS-LAD-*, P8b-01 forgetting)."""
import datetime as dt
import json
import uuid

import pytest
from sqlalchemy import text

from setu.domain.checker import _issue_verdict as issue_verdict  # tests mint arbitrary verdicts

from .helpers import approvals, make_learner

KEY = b"test-resolution-key-0123456789abcdef"
T0 = dt.datetime(2026, 11, 2, 9, tzinfo=dt.UTC)


@pytest.fixture
def world(engine):
    with engine.begin() as c:
        learner = make_learner(c, handle=f"h-{uuid.uuid4().hex[:10]}")
        skill = f"L4.rule.{uuid.uuid4().hex[:6]}.PR"
        c.execute(text("INSERT INTO skill (id, band, family, target, modality, direction) VALUES "
                       "(:s, 'L4', 'rule', 'x', 'PR', 'HI->TE')"), {"s": skill})
        rule_id = f"HI-TE-{uuid.uuid4().int % 300 + 600}"
        while c.execute(text("SELECT 1 FROM rule WHERE id = :r"), {"r": rule_id}).first():
            rule_id = f"HI-TE-{uuid.uuid4().int % 300 + 600}"
        c.execute(text("INSERT INTO rule (id, direction, contrast_area) VALUES (:r, 'HI->TE', 'q')"), {"r": rule_id})
        rv = c.execute(text("INSERT INTO rule_version (rule_id, version, title_hi, l1_explanation_hi, band, validity, "
                            "learner_evidence, lifecycle, teacher_approved, speaker_approvals, target_skill_id) VALUES "
                            "(:r, 1, 'सवाल', 'व्याख्या', 'L4', 'verified', 'predicted', 'active', true, "
                            "CAST(:a AS jsonb), :s) RETURNING id"),
                       {"r": rule_id, "a": approvals("s1", "s2"), "s": skill}).scalar_one()
        s = c.execute(text("INSERT INTO session (learner_id, mode, config_snapshot, seed) VALUES (:l, 'learn', '{}', 1) "
                           "RETURNING id"), {"l": learner}).scalar_one()
    return {"learner": learner, "skill": skill, "rule": rule_id, "rv": rv, "session": s}


def attempt(engine, world, *, kind="own", planted=None, mode="typed", cue=0, aids=()):
    with engine.begin() as c:
        e = c.execute(text("INSERT INTO exchange (session_id, kind, rule_version_id, planted, source) VALUES "
                           "(:s, :k, :rv, :p, 'bank') RETURNING id"),
                      {"s": world["session"], "k": kind, "rv": world["rv"], "p": planted}).scalar_one()
        return c.execute(text("INSERT INTO attempt (exchange_id, n, raw_text, response_mode, cue_level, assistance, "
                              "idempotency_key) VALUES (:e, 1, 'x', :m, :c, CAST(:a AS jsonb), :k) RETURNING id"),
                         {"e": e, "m": mode, "c": cue, "a": json.dumps(list(aids)), "k": uuid.uuid4().hex}).scalar_one()


@pytest.fixture
def writer(engine):
    from setu.store.outcome_writer import OutcomeWriter

    return OutcomeWriter(engine, resolution_key=KEY)


def one(engine, sql, **p):
    with engine.connect() as c:
        return c.execute(text(sql), p).first()


def card_target(ref="te:అవును"):
    from setu.store.outcome_writer import CardTarget

    return CardTarget(card_kind="lexeme", card_ref=ref, modality="RCL")


def skill_target(world, item="a", task="production", production=True):
    from setu.store.outcome_writer import SkillTarget

    return SkillTarget(skill_id=world["skill"], band="L4", item_ref=item, task_type=task, production=production)


def test_a_cue_free_answer_updates_the_fsrs_card_and_the_skill(engine, writer, world):
    a = attempt(engine, world)
    v = issue_verdict(attempt_id=a, outcome="correct", kind="recall", reason_code="t")
    writer.record_verdict(v, card=card_target(), skill=skill_target(world), at=T0)
    card = one(engine, "SELECT id, reps, stability, due, fsrs_state, fsrs_version FROM learner_lexeme_card "
                       "WHERE learner_id = :l", l=world["learner"])
    log = one(engine, "SELECT rating, cue_level FROM fsrs_review_log WHERE card_id = :c", c=card.id)
    st = one(engine, "SELECT tracker_alpha, tracker_beta, status, cuefree_successes, updated_by_event, "
                     "tracker_version FROM learner_skill_state WHERE learner_id = :l AND skill_id = :s",
             l=world["learner"], s=world["skill"])
    assert card.reps == 1 and card.stability and card.fsrs_version == "fsrs-6.3.2"
    assert (log.rating, log.cue_level) == (3, 0)
    assert st.tracker_alpha == 2 and st.status == "learning" and st.cuefree_successes == 1 and st.updated_by_event
    assert st.tracker_version == "tracker-1"


def test_an_assisted_answer_is_capped_at_hard_and_is_not_mastery_evidence(engine, writer, world):
    a = attempt(engine, world, mode="tiles", cue=1, aids=("tiles",))
    v = issue_verdict(attempt_id=a, outcome="correct", kind="recall", reason_code="t")
    writer.record_verdict(v, card=card_target("te:ఎంత"), skill=skill_target(world), at=T0)
    log = one(engine, "SELECT l.rating, l.cue_level FROM fsrs_review_log l JOIN learner_lexeme_card c ON c.id = l.card_id "
                      "WHERE c.learner_id = :l", l=world["learner"])
    st = one(engine, "SELECT tracker_alpha, cuefree_successes FROM learner_skill_state WHERE learner_id = :l",
             l=world["learner"])
    assert (log.rating, log.cue_level) == (2, 1)
    assert st.tracker_alpha == 1 and st.cuefree_successes == 0


def test_unsure_changes_no_schedule_and_no_skill(engine, writer, world):
    a = attempt(engine, world)
    writer.record_verdict(issue_verdict(attempt_id=a, outcome="unsure", kind="recall", reason_code="t"),
                          card=card_target(), skill=skill_target(world), at=T0)
    assert one(engine, "SELECT count(*) AS n FROM learner_lexeme_card WHERE learner_id = :l", l=world["learner"]).n == 0
    assert one(engine, "SELECT count(*) AS n FROM learner_skill_state WHERE learner_id = :l", l=world["learner"]).n == 0
    assert one(engine, "SELECT count(*) AS n FROM skill_evidence WHERE learner_id = :l", l=world["learner"]).n == 0


def test_varied_cue_free_evidence_over_two_days_masters_the_skill(engine, writer, world):
    plan = [("a", "recall", False, 0), ("b", "recall", False, 1), ("a", "production", True, 2),
            ("b", "production", True, 3), ("c", "production", True, 26)]
    for item, task, prod, hours in plan:
        a = attempt(engine, world)
        writer.record_verdict(issue_verdict(attempt_id=a, outcome="correct", kind="own", reason_code="t"),
                              skill=skill_target(world, item=item, task=task, production=prod),
                              at=T0 + dt.timedelta(hours=hours))
    st = one(engine, "SELECT status, distinct_items, distinct_days, production_successes, mastery_lo, due_at "
                     "FROM learner_skill_state WHERE learner_id = :l", l=world["learner"])
    assert st.status == "mastered" and st.distinct_items == 3 and st.distinct_days == 2
    assert st.production_successes == 3 and st.mastery_lo >= 0.6 and st.due_at > T0


def test_skill_evidence_is_immutable_and_writer_only(engine, writer, world):
    from sqlalchemy.exc import DBAPIError

    a = attempt(engine, world)
    writer.record_verdict(issue_verdict(attempt_id=a, outcome="correct", kind="own", reason_code="t"),
                          skill=skill_target(world), at=T0)
    with pytest.raises(DBAPIError), engine.begin() as c:
        c.execute(text("UPDATE skill_evidence SET outcome = 'wrong'"))
    with pytest.raises(DBAPIError), engine.begin() as c:
        c.execute(text("SET LOCAL ROLE setu_app"))
        c.execute(text("INSERT INTO skill_evidence (learner_id, skill_id, verdict_id, item_ref, task_type, day, "
                       "outcome, cue_level, after_reveal, production) SELECT learner_id, skill_id, verdict_id, item_ref, "
                       "task_type, day, outcome, cue_level, after_reveal, production FROM skill_evidence LIMIT 1"))


def test_the_classmate_forgets_when_the_learner_is_predicted_to_forget(engine, writer, world):
    from setu.store.scheduling import forget_due

    a = attempt(engine, world, kind="correction", planted=True)
    writer.record_verdict(issue_verdict(attempt_id=a, outcome="correct", kind="fix", reason_code="t"),
                          skill=skill_target(world), at=T0)
    assert one(engine, "SELECT state FROM classmate_rule_state WHERE learner_id = :l", l=world["learner"]).state == "taught"
    assert forget_due(engine, writer, world["learner"], at=T0 + dt.timedelta(hours=12)) == []
    forgotten = forget_due(engine, writer, world["learner"], at=T0 + dt.timedelta(days=30))
    assert forgotten == [world["rule"]]
    assert one(engine, "SELECT state FROM classmate_rule_state WHERE learner_id = :l",
               l=world["learner"]).state == "forgotten"
