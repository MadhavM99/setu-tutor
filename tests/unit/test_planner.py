"""Planner v1 (P-ARCH-02, P-SESS-05/07, P-LSP-04/05, P8b-03, P-BANK-05, X-CLS-START, R-17, E-12; TS-PLAN-01..08)."""
import collections

import pytest

from setu.domain import planner as P


def rule(rid, *, band="L4", learner_ready=True, classmate="unknown", active=True, errors=0, opportunities=0):
    return P.RuleView(rule_id=rid, band=band, learner_ready=learner_ready, classmate_state=classmate,
                      plantable_content=active, errors=errors, opportunities=opportunities)


RULES = [rule(f"HI-TE-00{i}") for i in range(1, 6)] + [rule("HI-TE-009", classmate="taught")]


def plan(rules=RULES, seed=1, **kw):
    return P.plan_session(rules=rules, learner_band=kw.pop("learner_band", "L4"), seed=seed,
                          config=P.Config(**kw))


def kinds(p):
    return [t.kind for t in p.turns]


def test_same_seed_same_plan_and_the_seed_is_recorded():
    assert plan(seed=7) == plan(seed=7)
    assert plan(seed=7).seed == 7 and plan(seed=7).planner_version == P.VERSION


def test_session_shape_follows_the_config():
    p = plan(correction_exchanges=5, own_sentences_min=2)
    assert len([t for t in p.turns if t.kind in ("planted", "no_error")]) == 5
    assert kinds(p).count("own") == 2


def test_only_rules_the_learner_knows_and_the_classmate_does_not_are_planted():
    rules = [rule("HI-TE-001"), rule("HI-TE-002", learner_ready=False), rule("HI-TE-003", classmate="taught"),
             rule("HI-TE-004", active=False), rule("HI-TE-005", classmate="forgotten")]
    for seed in range(30):
        planted = {t.rule_id for t in plan(rules, seed=seed).turns if t.kind == "planted"}
        assert planted <= {"HI-TE-001", "HI-TE-005"}


def test_bands_are_the_learners_or_one_above():
    rules = [rule("HI-TE-001", band="L3"), rule("HI-TE-002", band="L4"), rule("HI-TE-003", band="L5"),
             rule("HI-TE-004", band="L2"), rule("HI-TE-009", band="L3", classmate="taught")]
    used = {t.rule_id for s in range(30) for t in plan(rules, seed=s, learner_band="L3").turns if t.rule_id}
    assert used <= {"HI-TE-001", "HI-TE-002", "HI-TE-009"}


def test_no_error_share_is_about_one_in_five_when_errors_can_be_planted():
    turns = [t for s in range(400) for t in plan(seed=s).turns if t.kind in ("planted", "no_error")]
    share = sum(t.kind == "no_error" for t in turns) / len(turns)
    assert 0.15 <= share <= 0.25
    assert all(t.rule_id == "HI-TE-009" for t in turns if t.kind == "no_error")  # only rules the classmate knows


def test_with_nothing_to_plant_the_session_becomes_production_not_no_error_turns():
    # R-17: the newer paper copy found 83% no-error turns once every rule was taught.
    rules = [rule("HI-TE-001", classmate="taught"), rule("HI-TE-002", classmate="taught"),
             rule("HI-TE-003", classmate="taught")]
    p = plan(rules)
    assert "planted" not in kinds(p)
    no_error = kinds(p).count("no_error")
    assert no_error <= 1 and kinds(p).count("own") >= 2 + 5 - no_error


def test_the_classmate_waits_until_enough_rules_are_known():
    few = [rule("HI-TE-001"), rule("HI-TE-002"), rule("HI-TE-003", learner_ready=False)]
    p = plan(few, classmate_start_min_rules=3)
    assert set(kinds(p)) == {"own"} and p.classmate_active is False
    assert plan(few, classmate_start_min_rules=2).classmate_active is True


def test_interleaving_limits_runs_of_one_rule():
    rules = [rule("HI-TE-001", errors=50, opportunities=50), rule("HI-TE-002"), rule("HI-TE-003")]
    for s in range(50):
        ids = [t.rule_id for t in plan(rules, seed=s, correction_exchanges=8, interleave_max_run=2).turns
               if t.kind in ("planted", "no_error")]
        assert all(len(set(ids[i:i + 3])) > 1 for i in range(len(ids) - 2))


def test_rules_the_learner_gets_wrong_are_planted_more_often():
    rules = [rule("HI-TE-001", errors=9, opportunities=10), rule("HI-TE-002", errors=0, opportunities=10),
             rule("HI-TE-003", errors=0, opportunities=10)]
    counts = collections.Counter(t.rule_id for s in range(300) for t in plan(rules, seed=s).turns
                                 if t.kind == "planted")
    assert counts["HI-TE-001"] > counts["HI-TE-002"] and counts["HI-TE-001"] > counts["HI-TE-003"]


def test_forgotten_rules_come_first():
    rules = [rule("HI-TE-001"), rule("HI-TE-002"), rule("HI-TE-005", classmate="forgotten")]
    first = [next(t.rule_id for t in plan(rules, seed=s).turns if t.kind == "planted") for s in range(30)]
    assert first.count("HI-TE-005") == 30


def test_unknown_band_or_bad_config_is_refused():
    with pytest.raises(ValueError):
        plan(learner_band="L9")
    with pytest.raises(ValueError):
        plan(no_error_share=0.9)
