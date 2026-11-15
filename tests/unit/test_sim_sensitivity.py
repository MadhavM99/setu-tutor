"""The sensitivity knobs must not change sim-0.2's published runs, and each knob must do what its name says."""
import dataclasses

from setu.research import sim_sensitivity as ss
from setu.research import simulator_v2 as v2
from setu.research.simulator import profiles


def one(p, condition="A", seed=1):
    return v2.simulate(profiles(1, p.rules, seed)[0], condition, p, seed)


def test_default_sensitivity_params_reproduce_the_published_simulation():
    for condition in "ABC":
        assert one(ss.Params(), condition) == one(v2.Params(), condition)


def test_knobs_only_touch_the_condition_they_model():
    base = ss.Params()
    for change in ({"detect_override": 0.9}, {"planted_cue": 0}, {"unnoticed_is_lapse": False}):
        p = dataclasses.replace(base, **change)
        assert one(p, "A") != one(base, "A")
        for c in "BC":  # no planted turns there: memory is untouched (detect itself is a learner property)
            assert one(p, c)["tests"][7]["recall"] == one(base, c)["tests"][7]["recall"]
    copy = dataclasses.replace(base, feedback_restudy=True)
    assert one(copy, "A")["tests"][7]["recall"] != one(base, "A")["tests"][7]["recall"]  # A has failed fixes


def test_detect_override_changes_how_often_the_learner_fails_a_planted_turn():
    low = one(dataclasses.replace(ss.Params(), detect_override=0.0))
    high = one(dataclasses.replace(ss.Params(), detect_override=1.0))
    assert low["wrong_corrections"] == low["corrections"] > 0
    assert high["wrong_corrections"] < low["wrong_corrections"]


def test_cell_reports_an_order_and_paired_differences(monkeypatch):
    monkeypatch.setattr(v2, "run", lambda p, **kw: {c: [one(p, c, s) for s in (1, 2)] for c in "ABC"})
    c = ss.cell(ss.Params())
    assert sorted(c["order"]) == ["A", "B", "C"] and set(c["recall_day7"]) == set("ABC")
    assert abs(c["A_minus_B"] - (c["recall_day7"]["A"] - c["recall_day7"]["B"])) < 1e-3
