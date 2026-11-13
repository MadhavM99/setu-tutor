"""Seeded train/val split for the Raju QLoRA model (TASKS.md task 10, step 3). Offline.

The last two tests check the REAL data/ft/train.jsonl and val.jsonl when they exist: any exact or near-duplicate
overlap with the 29 frozen planting cases fails the suite.
"""
import json

import pytest

from setu.research import ft_data as fd
from setu.research import ft_split as fs

FROZEN = fs.frozen_sentences()


def _pairs():
    """Synthetic accepted pairs: 3 rules x 6 distinct sentences, plus a near-duplicate of the first of each rule."""
    sents = ["మా అమ్మ ఇంట్లో వంట చేస్తుంది", "రేపు బడికి సెలవు", "ఈ పుస్తకం చాలా పెద్దది",
             "నాకు కాఫీ ఇష్టం లేదు", "వాళ్ళు సినిమాకి వెళ్ళారు", "ఆ కుక్క పరిగెత్తుతోంది"]
    out = []
    for r in ("HI-TE-001", "HI-TE-003", "HI-TE-004"):
        for s in sents:
            out.append({"rule_id": r, "source": "gemini", "correct": f"{r} {s}", "wrong": f"{r} {s} కదా"})
        out.append({**out[-6], "correct": out[-6]["correct"] + " ఇప్పుడు", "wrong": out[-6]["wrong"] + " ఇప్పుడు"})
    return out


def test_split_is_deterministic_and_seed_dependent():
    a, b = fs.split(_pairs(), seed=13), fs.split(_pairs(), seed=13)
    assert a["train"] == b["train"] and a["val"] == b["val"]
    others = [fs.split(_pairs(), seed=s)["val"] for s in range(1, 8)]
    assert any(v != a["val"] for v in others)


def test_every_rule_with_two_groups_gets_a_val_example():
    res = fs.split(_pairs(), val_fraction=0.1)
    assert {p["rule_id"] for p in res["val"]} == {"HI-TE-001", "HI-TE-003", "HI-TE-004"}
    assert len(res["train"]) + len(res["val"]) == len(_pairs())


def test_near_duplicates_never_straddle_train_and_val():
    pairs = _pairs()
    gid = fs.groups(pairs)
    assert gid[0] == gid[6]  # the appended near-duplicate joins its original's group
    for seed in range(20):
        res = fs.split(pairs, seed=seed, val_fraction=0.5)
        assert fs.leaks(res["train"], res["val"]) == []


def test_frozen_sentences_are_dropped_on_either_side():
    _, _, fc, fw = fd.frozen_pairs()[0]
    bad = [{"rule_id": "HI-TE-001", "source": "gemini", "correct": "నాకు చాలా సమయం ఉంది", "wrong": fc},  # cross-side
           {"rule_id": "HI-TE-001", "source": "gemini", "correct": fw + " ఇప్పుడు", "wrong": "నేను చాలా సమయం"}]
    res = fs.split(_pairs() + bad)
    assert [p["frozen_overlap"] for p in res["dropped"]] == ["exact", "near"]
    assert not any(fs.frozen_overlap(p, FROZEN) for p in res["train"] + res["val"])


def _real(name):
    p = fd.DATA / f"{name}.jsonl"
    if not p.exists():
        pytest.skip(f"{p} not built yet")
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


@pytest.mark.parametrize("name", ["train", "val"])
def test_written_split_has_no_frozen_overlap(name):
    rows = _real(name)
    hits = [(p["correct"], p["wrong"], fs.frozen_overlap(p, FROZEN)) for p in rows]
    assert [h for h in hits if h[2]] == []


def test_written_split_is_disjoint_and_has_no_val_train_near_duplicates():
    train, val = _real("train"), _real("val")
    assert not {(p["correct"], p["wrong"]) for p in train} & {(p["correct"], p["wrong"]) for p in val}
    assert fs.leaks(train, val) == []
