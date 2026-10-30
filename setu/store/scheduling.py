"""Forgetting scan (P8b-01): find rules the classmate knows whose learner is now predicted to forget them, and let
the OutcomeWriter apply the scheduler's decisions. Reads run as `setu_read`; the only writes go through the writer.
Run at session start (and optionally nightly)."""
import datetime as dt

from sqlalchemy import text
from sqlalchemy.engine import Engine

from setu.domain import scheduler

from .outcome_writer import OutcomeWriter


def forget_due(engine: Engine, writer: OutcomeWriter, learner_id, *, at: dt.datetime | None = None) -> list[str]:
    at = at or dt.datetime.now(dt.UTC)
    with engine.execution_options(isolation_level="READ COMMITTED").begin() as c:
        c.execute(text("SET LOCAL ROLE setu_read"))
        rows = c.execute(text(
            "SELECT cs.rule_id, s.tracker_alpha, s.tracker_beta, s.half_life_days, s.last_practised, s.tracker_version "
            "FROM classmate_rule_state cs JOIN learner_rule_version rv ON rv.rule_id = cs.rule_id "
            "JOIN learner_skill_state s ON s.learner_id = cs.learner_id AND s.skill_id = rv.target_skill_id "
            "WHERE cs.learner_id = :l AND cs.state = 'taught' AND s.last_practised IS NOT NULL ORDER BY cs.rule_id"),
            {"l": learner_id}).all()
    forgotten = []
    for r in rows:
        tracker = scheduler.TrackerState(r.tracker_alpha, r.tracker_beta, r.half_life_days, r.last_practised)
        decision = scheduler.forget_if_due(learner_id=learner_id, rule_id=r.rule_id, tracker=tracker, at=at)
        if decision is not None and writer.apply_forget(decision) == "forgotten":
            forgotten.append(r.rule_id)
    return forgotten
