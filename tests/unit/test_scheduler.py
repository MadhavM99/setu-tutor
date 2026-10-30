"""Scheduler (P-ARCH-12, E-04/05, X-MEM-01, X-PERS-02/06, X-MEM-AID-13, P8b-01; TS-SCHED-*, TS-LAD-01..08)."""
import datetime as dt
import math
import uuid

import pytest

from setu.domain import scheduler as S

T0 = dt.datetime(2026, 11, 1, 9, tzinfo=dt.UTC)


# ---------------------------------------------------------------- FSRS (words, letters, chunks)


@pytest.mark.parametrize("outcome,cue,kind,rating", [
    ("correct", 0, "recall", 3), ("correct", 1, "recall", 2), ("correct", 1, "recognition", 2),
    ("partial", 0, "recall", 2), ("wrong", 0, "recall", 1), ("wrong", 2, "recall", 1), ("unsure", 0, "recall", None),
])
def test_rating_from_the_verdict_and_the_cue_cap(outcome, cue, kind, rating):
    assert S.fsrs_rating(outcome=outcome, cue_level=cue, kind=kind) == rating


def test_fsrs_reviews_are_deterministic_and_respond_to_ratings():
    a = S.fsrs_review(S.new_card(), rating=3, at=T0)
    b = S.fsrs_review(S.new_card(), rating=3, at=T0)
    assert a == b and a.reps == 1 and a.version == S.FSRS_VERSION
    good = S.fsrs_review(S.fsrs_review(a, rating=3, at=T0 + dt.timedelta(days=1)), rating=3, at=T0 + dt.timedelta(days=3))
    again = S.fsrs_review(S.fsrs_review(a, rating=3, at=T0 + dt.timedelta(days=1)), rating=1, at=T0 + dt.timedelta(days=3))
    assert good.due > again.due and again.lapses >= good.lapses


def test_fsrs_retrievability_decays():
    c = S.fsrs_review(S.new_card(), rating=3, at=T0)
    assert S.fsrs_recall(c, at=T0 + dt.timedelta(days=1)) > S.fsrs_recall(c, at=T0 + dt.timedelta(days=30))


# ---------------------------------------------------------------- mastery tracker (rules and skills)


def test_beta_quantiles_are_exact_enough():
    assert S.beta_quantile(6, 1, 0.05) == pytest.approx(0.05 ** (1 / 6), abs=1e-6)
    assert S.beta_quantile(2, 2, 0.5) == pytest.approx(0.5, abs=1e-6)


def test_cue_free_successes_raise_the_lower_bound():
    t = S.TrackerState.new(at=T0)
    for i in range(5):
        t = S.track(t, outcome="correct", cue_level=0, after_reveal=False, at=T0 + dt.timedelta(hours=i))
    assert t.mean > 0.8 and t.lo >= 0.6 and t.lo < t.mean < t.hi


def test_assisted_or_revealed_answers_are_not_mastery_evidence():
    t0 = S.TrackerState.new(at=T0)
    assisted = S.track(t0, outcome="correct", cue_level=1, after_reveal=False, at=T0)
    revealed = S.track(t0, outcome="correct", cue_level=0, after_reveal=True, at=T0)
    assert (assisted.alpha, assisted.beta) == (revealed.alpha, revealed.beta) == (t0.alpha, t0.beta)


def test_errors_lower_the_estimate_and_the_half_life():
    t = S.track(S.TrackerState.new(at=T0), outcome="correct", cue_level=0, after_reveal=False, at=T0)
    w = S.track(t, outcome="wrong", cue_level=0, after_reveal=False, at=T0)
    assert w.mean < t.mean and w.half_life_days < t.half_life_days


def test_predicted_recall_halves_after_one_half_life_and_drives_forgetting():
    t = S.track(S.TrackerState.new(at=T0), outcome="correct", cue_level=0, after_reveal=False, at=T0)
    h = t.half_life_days
    assert S.predicted_recall(t, at=T0 + dt.timedelta(days=h)) == pytest.approx(0.5, abs=1e-9)
    learner = uuid.uuid4()
    assert S.forget_if_due(learner_id=learner, rule_id="HI-TE-001", tracker=t,
                           at=T0 + dt.timedelta(days=h * 0.9)) is None
    d = S.forget_if_due(learner_id=learner, rule_id="HI-TE-001", tracker=t, at=T0 + dt.timedelta(days=h * 1.1))
    assert d is not None and d.predicted_recall < 0.5 and d.tracker_version == S.TRACKER_VERSION


def test_old_evidence_decays_towards_the_prior():
    t = S.TrackerState.new(at=T0)
    for i in range(6):
        t = S.track(t, outcome="correct", cue_level=0, after_reveal=False, at=T0 + dt.timedelta(hours=i))
    later = S.track(t, outcome="partial", cue_level=0, after_reveal=False, at=T0 + dt.timedelta(days=120))
    assert later.alpha < t.alpha


# ---------------------------------------------------------------- unlock rule (learning-ladder.md §3)


def ev(item, task, day, outcome="correct", cue=0, after_reveal=False, production=False):
    return S.Evidence(item_ref=item, task_type=task, day=dt.date(2026, 11, day), outcome=outcome, cue_level=cue,
                      after_reveal=after_reveal, production=production)


def strong_tracker():
    t = S.TrackerState.new(at=T0)
    for i in range(6):
        t = S.track(t, outcome="correct", cue_level=0, after_reveal=False, at=T0 + dt.timedelta(hours=i))
    return t


def test_three_answers_to_one_item_on_one_day_do_not_unlock():
    evs = [ev("a", "recall", 1)] * 3
    assert S.mastery_status(evs, strong_tracker(), band="L2").status != "mastered"


def test_varied_cue_free_evidence_with_production_unlocks():
    evs = [ev("a", "recall", 1), ev("b", "recall", 1), ev("b", "production", 2, production=True)]
    m = S.mastery_status(evs, strong_tracker(), band="L2")
    assert m.status == "mastered" and m.distinct_items == 2 and m.distinct_days == 2 and m.production_successes == 1


@pytest.mark.parametrize("bad", [
    [ev("a", "recall", 1), ev("b", "recall", 1), ev("b", "production", 2, production=True, cue=1)],          # aided
    [ev("a", "recall", 1), ev("b", "recall", 1), ev("b", "production", 2, production=True, after_reveal=True)],
    [ev("a", "recall", 1), ev("b", "recall", 1), ev("c", "recall", 2)],                                        # no production
    [ev("a", "recall", 1), ev("b", "recall", 1), ev("b", "production", 2, production=True, outcome="unsure")],
])
def test_aided_revealed_or_unproduced_evidence_does_not_unlock_l2_skills(bad):
    assert S.mastery_status(bad, strong_tracker(), band="L2").status != "mastered"


def test_l0_l1_skills_need_cue_free_recall_but_not_production():
    evs = [ev("a", "recall", 1), ev("b", "recognition", 1), ev("b", "recall", 2)]
    assert S.mastery_status(evs, strong_tracker(), band="L1").status == "mastered"


def test_a_weak_tracker_keeps_the_skill_learning():
    evs = [ev("a", "recall", 1), ev("b", "recall", 1), ev("b", "production", 2, production=True)]
    weak = S.TrackerState.new(at=T0)
    assert S.mastery_status(evs, weak, band="L2").status == "learning"


def test_due_when_predicted_recall_falls_below_half():
    t = strong_tracker()
    evs = [ev("a", "recall", 1), ev("b", "recall", 1), ev("b", "production", 2, production=True)]
    later = T0 + dt.timedelta(days=t.half_life_days * 2)
    assert S.mastery_status(evs, t, band="L2", at=later).status == "due"


# ---------------------------------------------------------------- baselines for M-23 / M-24


def test_bkt_update_matches_the_standard_equations():
    b = S.Bkt(p_init=0.2, p_learn=0.15, p_slip=0.1, p_guess=0.2)
    p = b.update(0.2, correct=True)
    posterior = 0.2 * 0.9 / (0.2 * 0.9 + 0.8 * 0.2)
    assert p == pytest.approx(posterior + (1 - posterior) * 0.15)
    assert b.predict(0.5) == pytest.approx(0.5 * 0.9 + 0.5 * 0.2)


def test_sm2_intervals_and_easiness():
    s = S.Sm2()
    s = s.review(quality=5)
    assert s.interval == 1
    s = s.review(quality=5)
    assert s.interval == 6
    s = s.review(quality=5)
    assert s.interval == round(6 * s.easiness_before)
    assert S.Sm2().review(quality=2).interval == 1


def test_log_loss_and_auc():
    assert S.log_loss([1, 0], [0.9, 0.1]) == pytest.approx(-math.log(0.9))
    assert S.auc([1, 1, 0, 0], [0.9, 0.8, 0.3, 0.1]) == 1.0
    assert S.auc([1, 0], [0.4, 0.4]) == 0.5
