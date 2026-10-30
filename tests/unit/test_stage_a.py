"""Stage A suite (TS-SUITE-META, TS-SUITE-SPLIT, TS-SUITE-LEAK) and scorecard (TS-SCORE-01, M-49)."""
import hashlib
import json

import pytest

from setu.research import scorecard, stage_a

CASES = stage_a.load_cases()
DEV = stage_a.split(CASES, "dev")


def test_suite_has_at_least_150_cases_in_every_group():
    groups = {c["group"] for c in CASES}
    assert len(CASES) >= 150 and {"checker", "leak", "planting", "attack", "forgetting"} <= groups
    assert len({c["id"] for c in CASES}) == len(CASES)


def test_suite_is_reproducible_from_the_content():
    assert stage_a.build_cases() == CASES


def test_heldout_manifest_is_frozen_and_about_thirty_percent():
    m = json.loads(stage_a.MANIFEST.read_text(encoding="utf-8"))
    assert hashlib.sha256("\n".join(m["heldout_ids"]).encode()).hexdigest() == m["heldout_sha256"]
    share = len(stage_a.split(CASES, "heldout")) / len(CASES)
    assert 0.2 <= share <= 0.4


def test_dev_and_heldout_do_not_overlap():
    held = {c["id"] for c in stage_a.split(CASES, "heldout")}
    assert held and not held & {c["id"] for c in DEV}


@pytest.mark.parametrize("case", DEV, ids=[c["id"] for c in DEV])
def test_dev_case(case):
    passed, observed = stage_a.run_case(case)
    assert passed, observed


def test_scorecard_reports_every_metric_with_a_status(tmp_path):
    card = scorecard.build(split="heldout")
    ids = {m["id"] for m in card["metrics"]}
    assert {"M-05", "M-07", "M-08", "M-09", "M-14", "M-54"} <= ids
    assert all(m["status"] in ("pass", "fail", "not_measured") for m in card["metrics"])
    assert card["caveat"] and card["thresholds_sha256"]
    assert any(m["status"] == "not_measured" for m in card["metrics"])  # honest: most metrics need people or models
    path = scorecard.write(card, tmp_path)
    assert "not measured" in path.read_text(encoding="utf-8")


def test_thresholds_are_the_documented_targets():
    t = scorecard.load_thresholds()
    assert t["M-07"]["min"] == 0.9 and t["M-08"]["max"] == 0.05 and t["M-09"]["max"] == 0.15 and t["M-14"]["max"] == 0
