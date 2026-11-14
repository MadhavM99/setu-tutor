"""Frozen evaluation sets for the final submission (TASKS.md task 4): the 29 planting cases, the attack prompts and
the Stage-A held-out split must not change once results start, and every attack is refused by today's harness."""
import hashlib
import json
import uuid
from pathlib import Path

import pytest

from setu.agents import tools
from setu.domain import checker, leakfilter
from setu.research import generation_baselines, stage_a

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = json.loads((ROOT / "tests/eval_sets/manifest.json").read_text(encoding="utf-8"))
ATTACKS_FILE = ROOT / MANIFEST["attacks_file"]
ATTACKS = [json.loads(line) for line in ATTACKS_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
ITEMS = [(r, it) for r, it in stage_a._items() if r["direction"] == "HI->TE" and it.get("wrong_form")]


def _key(item_id):
    found = [(r, i) for r, i in ITEMS if i["item_id"] == item_id]
    if not found:
        raise KeyError(item_id)
    return stage_a.item_key(*found[0], ITEMS)


def test_planting_cases_are_frozen_and_match_the_content():
    blob = json.dumps(MANIFEST["planting_cases"], ensure_ascii=False, sort_keys=True)
    assert hashlib.sha256(blob.encode()).hexdigest() == MANIFEST["planting_sha256"]
    live = [{"item_id": it["item_id"], "rule_id": r["rule_id"], "wrong_form": it["wrong_form"],
             "correct_form": it["correct_form"]} for r, it, _ in generation_baselines.cases()]
    assert live == MANIFEST["planting_cases"] and len(live) == 29


def test_attacks_and_heldout_split_are_frozen():
    assert hashlib.sha256(ATTACKS_FILE.read_bytes()).hexdigest() == MANIFEST["attacks_sha256"]
    held = json.loads((ROOT / MANIFEST["stage_a_heldout_manifest"]).read_text(encoding="utf-8"))
    assert held["heldout_sha256"] == MANIFEST["stage_a_heldout_sha256"] and len(held["heldout_ids"]) == 185
    assert len(ATTACKS) >= 20 and len({a["id"] for a in ATTACKS}) == len(ATTACKS)


@pytest.mark.parametrize("a", [a for a in ATTACKS if a["surface"] == "model_tool_call"], ids=lambda a: a["id"])
def test_model_tool_call_attack_is_refused(a):
    def context_for(item_id):
        return leakfilter.Context(item=_key(item_id), turn="planted", seen_words=set(), allowed_target_forms=set())

    out = tools.handle_reply(a["input"], context_for=context_for, planned_item=a["planned_item"])
    assert isinstance(out, str) and out.startswith(a["expect_error_prefix"]), out


@pytest.mark.parametrize("a", [a for a in ATTACKS if a["surface"] == "learner_message"], ids=lambda a: a["id"])
def test_learner_message_attack_is_never_graded_correct(a):
    r = checker.check_fix(attempt_id=uuid.uuid4(), raw=a["input"], item=_key(a["item_id"]), response_mode="typed")
    assert r.verdict.outcome != "correct"
