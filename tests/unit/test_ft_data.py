"""Research validator and training-pair sources for the Raju QLoRA model (TASKS.md task 10, step 2). Offline."""
import json

import pytest

from setu.agents.llm import Completion
from setu.research import ft_data as fd

SPECS = {s.rule_id: s for s in fd.rule_specs()}


def test_validator_accepts_every_frozen_pair():
    r = fd.recall_on_frozen()
    assert r["n"] == 29 and r["accepted"] == 29, r["rejected"]


def test_validator_rejects_synthetic_negatives_except_the_meaning_dependent_rule():
    fa = fd.false_accepts()
    assert fa["by_kind"]["no_edit"]["accepted"] == fa["by_kind"]["double_edit"]["accepted"] == 0
    assert fa["by_kind"]["wrong_rule"]["accepted"] == 0
    assert all(e["rule_id"] in fd.MEANING_DEPENDENT for e in fa["examples"])


@pytest.mark.parametrize("rule,correct,wrong,reason", [
    ("HI-TE-004", "నేను గదిలో ఉన్నాను", "నేను గదిలో ఉన్నాను", "NO_EDIT"),
    ("HI-TE-004", "నేను గదిలో ఉన్నాను", "నేను గది ఉన్నాను", "NOT_RULE_ERROR"),
    ("HI-TE-004", "నేను గదిలో ఉన్నాను", "అతను గది లో ఉన్నాను", "EDIT_SHAPE"),          # a second edit
    ("HI-TE-004", "నేను గదిలో ఉన్నాను", "నేను గది లో ఉన్నాను (room)", "WRONG_GLOSS"),
    ("HI-TE-004", "నేను గదిలో ఉన్నాను", "నేను గది లో తెలియనిపదం", "WRONG_OOV"),
    ("HI-TE-004", "నేను గది లో ఉన్నాను", "నేను గది లో లో ఉన్నాను", "CORRECT_HAS_ERROR"),
])
def test_validator_reasons(rule, correct, wrong, reason):
    assert reason in fd.validate_pair(SPECS[rule], correct, wrong)


def test_a_new_pair_of_the_same_shape_is_accepted():
    # "I have a lot of time": bank words only, not a frozen pair, same 1->1 shape as HI-TE-003
    assert fd.validate_pair(SPECS["HI-TE-003"], "నాకు చాలా సమయం ఉంది", "నేను చాలా సమయం ఉంది") == []
    assert fd.near_duplicate("నాకు చాలా సమయం ఉంది", "నేను చాలా సమయం ఉంది") is None


def test_region_trims_common_prefix_and_suffix():
    assert fd.region("ఇది నీ కోసం", "ఇది కోసం నీ") == (["నీ", "కోసం"], ["కోసం", "నీ"], 1)
    assert fd.region("ఇది పుస్తకం", "ఇది పుస్తకం ఉంది") == ([], ["ఉంది"], 2)


def test_frozen_and_near_frozen_pairs_never_enter_training():
    rid, _iid, c, w = fd.frozen_pairs()[2]
    acc, rej = fd.build([{"rule_id": rid, "source": "gemini", "correct": c, "wrong": w},
                         {"rule_id": "HI-TE-002", "source": "slot", "correct": "ఇది పెన్ను", "wrong": "ఇది పెన్ను ఉంది"}])
    assert acc == [] and "FROZEN_CASE" in rej[0]["reasons"]
    assert any(r.startswith("NEAR_FROZEN") for r in rej[1]["reasons"])
    assert fd.near_duplicate("చాలా బాగుంది", "చాలా బాగుంది ఉంది") is None


def test_meaning_dependent_rule_is_excluded():
    _, rej = fd.build([{"rule_id": "HI-TE-006", "source": "gemini", "correct": "మేము వస్తాను", "wrong": "మనం వస్తాను"}])
    assert "MEANING_DEPENDENT_RULE" in rej[0]["reasons"]


def test_summary_counts_and_go_no_go():
    acc = [{"rule_id": "HI-TE-004", "source": "gemini"}] * 3
    s = fd.summary(acc, [], {"calls": 1})
    c = s["go_no_go"]["checks"]
    assert s["by_rule"]["HI-TE-004"] == 3 and s["coverage"]["hi_te_trainable"] == "1 of 14" and not s["go_no_go"]["go"]
    assert c["validator_recall"]["met"] and not c["rules_covered"]["met"] and not c["total_pairs"]["met"]
    assert s["frozen_cases_by_direction"] == {"HI->TE": 29, "TE->HI": 0}
    assert "HI-TE-006" in c["pairs_per_frozen_rule"]["failing"]


def test_go_needs_every_check():
    rules = [r for r in fd.rule_specs() if r.direction == "HI->TE" and r.rule_id not in fd.MEANING_DEPENDENT]
    acc = [{"rule_id": r.rule_id, "source": "gemini"} for r in rules for _ in range(15)]
    s = fd.summary(acc, [], {})
    c = s["go_no_go"]["checks"]
    assert c["rules_covered"]["met"] and c["total_pairs"]["met"] and c["pairs_per_frozen_rule"][
        "met_excluding_meaning_dependent"]
    assert s["go_no_go"]["go"]  # the agreed reading leaves out HI-TE-006 (excluded by design)
    assert not s["go_no_go"]["go_strict"]  # HI-TE-006 has frozen cases but can never get pairs
    acc = [p for p in acc if p["rule_id"] != "HI-TE-004"]
    assert not fd.summary(acc, [], {})["go_no_go"]["go"]  # any other frozen rule short of 10 still fails


class _Fake:
    model = "fake"

    def __init__(self, replies):
        self.replies, self.calls = list(replies), 0

    def complete(self, messages, **_):
        self.calls += 1
        r = self.replies.pop(0)
        return Completion(None, "fake", 1, error=r[1:]) if r.startswith("!") else Completion(r, "fake", 1, 10, 20)


def test_generation_is_resumable_and_logs_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(fd, "DATA", tmp_path)
    good = json.dumps({"pairs": [{"hindi": "मेरे पास बहुत समय है", "correct": "నాకు చాలా సమయం ఉంది",
                                  "wrong": "నేను చాలా సమయం ఉంది"}]}, ensure_ascii=False)
    spec = SPECS["HI-TE-003"]
    logged = []
    p1 = _Fake(["!HTTPStatusError: 429", good])
    fd.generate(p1, [spec], calls_per_rule=2, interval=0, log=logged.append)
    assert p1.calls == 2 and len(logged) == 1
    p2 = _Fake([good])  # resume: only the failed call 0 is retried
    fd.generate(p2, [spec], calls_per_rule=2, interval=0, log=logged.append)
    assert p2.calls == 1
    pairs, stats = fd.gemini_pairs()
    assert stats == {"calls": 3, "ok_calls": 2, "errors": {"HTTPStatusError: 429": 1}, "tokens": 60}
    acc, _ = fd.build(pairs)
    assert len(acc) == 1 and acc[0]["source"] == "gemini"  # the duplicate is dropped


def test_funnel_counts_each_rejected_pair_once_at_its_first_failing_check():
    rej = [{"source": "gemini", "reasons": ["CORRECT_OOV", "NEAR_FROZEN:x"]},
           {"source": "gemini", "reasons": ["EDIT_SHAPE"]},
           {"source": "gemini", "reasons": ["NEAR_FROZEN:y"]},
           {"source": "gemini", "reasons": ["DUPLICATE"]},
           {"source": "slot", "reasons": ["CORRECT_OOV"]}]
    f = fd.funnel([{"source": "gemini"}], rej, {"calls": 3, "ok_calls": 1, "errors": {"429": 2}})
    assert f["candidates"] == 5 and f["accepted"] == 1
    assert [s["removed"] for s in f["stages"]] == [1, 1, 1, 1]
    assert f["stages"][-1]["remaining"] == f["accepted"]
