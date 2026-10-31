"""Placement diagnostic (slice S7; F-PLACE, X-PERS-03, TS-PLACE-*)."""
import uuid

import pytest

from setu.domain import placement as P

ALL = ("L0", "L1", "L2", "L3")


def p(band, item, task, outcome="correct"):
    return P.Probe(band, item, task, outcome)


def passed(band):
    return [p(band, f"{band}-a", "recall"), p(band, f"{band}-b", "read")]


def failed(band):
    return [p(band, f"{band}-a", "recall", "wrong"), p(band, f"{band}-b", "read", "wrong")]


def test_a_band_passes_only_on_two_items_and_both_task_types():
    assert P.band_result(passed("L2")) == "pass"
    assert P.band_result([p("L2", "a", "recall"), p("L2", "b", "recall")]) is None  # one task type
    assert P.band_result([p("L2", "a", "recall"), p("L2", "a", "read")]) is None  # one item
    assert P.band_result([p("L2", "a", "recall"), p("L2", "b", "read", "unsure")]) is None  # unsure does not count
    assert P.band_result(failed("L2")) == "fail"


def test_a_band_that_cannot_be_passed_within_the_cap_fails():
    probes = [p("L2", f"i{k}", "recall") for k in range(P.MAX_PROBES_PER_BAND)]
    assert P.band_result(probes) == "fail"


def test_the_walk_starts_at_l2_and_moves_up_after_a_pass():
    assert P.walk([], ALL).band == "L2"
    s = P.walk(passed("L2"), ALL)
    assert s.band == "L3" and s.placed_bands == ("L0", "L1", "L2")


def test_failing_l2_moves_down_and_a_pass_below_ends_the_walk():
    assert P.walk(failed("L2"), ALL).band == "L1"
    s = P.walk(failed("L2") + passed("L1"), ALL)
    assert s.done and s.placed_bands == ("L0", "L1")


def test_passing_the_top_band_or_failing_everything_ends_the_walk():
    top = P.walk(passed("L2") + passed("L3"), ALL)
    assert top.done and top.placed_bands == ALL
    none = P.walk(failed("L2") + failed("L1") + failed("L0"), ALL)
    assert none.done and none.placed_bands == ()


def test_failing_l3_after_passing_l2_places_up_to_l2():
    s = P.walk(passed("L2") + failed("L3"), ALL)
    assert s.done and s.placed_bands == ("L0", "L1", "L2")


def test_bands_without_approved_content_are_skipped():
    assert P.walk([], ("L0", "L1")).band == "L1"
    assert P.walk([], ()).done


def test_the_next_probe_alternates_task_types_and_never_repeats_an_item():
    units = ["u1", "u2", "u3", "u4"]
    first = P.next_probe("L2", [], units, seed=3)
    assert first[1] == "recall"
    second = P.next_probe("L2", [p("L2", first[0], "recall")], units, seed=3)
    assert second[1] == "read" and second[0] != first[0]
    assert P.next_probe("L2", [p("L2", u, "recall") for u in units], units, seed=3) is None


def test_placement_decisions_are_minted_only_by_the_placement_module():
    with pytest.raises(TypeError):
        P.PlacementDecision()
    d = P.decide(learner_id=uuid.uuid4(), bands=("L0",), skill_ids=("L0.script.ka.RCL",),
                 verdict_ids=(uuid.uuid4(), uuid.uuid4()))
    assert P.is_minted(d) and d.version == P.VERSION
    assert P.decide(learner_id=uuid.uuid4(), bands=(), skill_ids=(), verdict_ids=()) is None
