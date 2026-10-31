"""Simulator v0.1 (exploratory): reproducible, matched across conditions, no condition-specific effect hidden."""
import dataclasses

from setu.research import simulator as S


def test_runs_are_reproducible():
    a = S.summarise(S.run(n=4, seeds=(1,)))
    b = S.summarise(S.run(n=4, seeds=(1,)))
    assert a == b


def test_conditions_get_the_same_number_of_exchanges_and_profiles():
    r = S.run(n=5, seeds=(2,))
    assert len(r["A"]) == len(r["B"]) == len(r["C"]) == 5
    turns = 3 * (S.Params().correction_exchanges + S.Params().own_sentences_min)
    for c in S.CONDITIONS:
        for x in r[c]:
            exchanges = x["own"] + x["corrections"] + x["no_error_turns"] + (turns - x["own"] if c == "B" else 0)
            assert exchanges == turns if c != "C" else x["own"] == turns


def test_with_every_learning_effect_equal_the_conditions_cannot_differ_on_recall():
    p = dataclasses.replace(S.Params(), cued_gain=0.0, restudy_gain=0.0, retrieval_gain=0.0, hint_gain=0.0,
                            explain_gain=0.0, detect_gain=0.0, contrast=0.0, spacing=0.0)
    t = S.summarise(S.run(n=6, seeds=(3,), params=p))["conditions"]
    assert t["A"]["recall_day7"]["mean"] == t["B"]["recall_day7"]["mean"] == t["C"]["recall_day7"]["mean"]
