"""Unit tests for human-system agreement evaluation (Task 13, setu/research/evaluate_agreement.py)."""

import csv
import json
from pathlib import Path
import pytest

from setu.research import scorecard
from setu.research.agreement import cohen_kappa
from setu.research.evaluate_agreement import (
    ALLOWED_CATEGORIES,
    CATEGORIES,
    DEFAULT_HUMAN_PATH,
    DEFAULT_KEY_PATH,
    evaluate_batch_a_agreement,
    get_batch_a_agreement_if_available,
    main,
)


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


@pytest.fixture
def synthetic_data(tmp_path):
    # 20 items: 10 correct, 6 partial, 4 wrong
    h_rows = []
    k_rows = []
    # 8 correct/correct, 2 correct/partial
    # 4 partial/partial, 2 partial/unsure
    # 4 wrong/wrong
    labels = (
        [("correct", "correct")] * 8
        + [("correct", "partial")] * 2
        + [("partial", "partial")] * 4
        + [("partial", "unsure")] * 2
        + [("wrong", "wrong")] * 4
    )
    for idx, (h, c) in enumerate(labels, start=1):
        rid = f"row_{idx:03d}"
        h_rows.append({"row_id": rid, "label": h, "note": "ok"})
        k_rows.append({"row_id": rid, "checker_outcome": c, "checker_reason": "rule"})

    h_path = tmp_path / "human_synthetic.csv"
    k_path = tmp_path / "key_synthetic.csv"
    _write_csv(h_path, h_rows, ["row_id", "label", "note"])
    _write_csv(k_path, k_rows, ["row_id", "checker_outcome", "checker_reason"])
    return h_path, k_path, labels


def test_synthetic_kappa_and_observed_agreement(synthetic_data):
    h_path, k_path, labels = synthetic_data
    res = evaluate_batch_a_agreement(human_path=h_path, key_path=k_path)

    expected_po = sum(h == c for h, c in labels) / len(labels)  # (8 + 4 + 4) / 20 = 16 / 20 = 0.8
    assert res.n == 20
    assert res.observed_agreement == pytest.approx(expected_po)

    h_list = [h for h, _ in labels]
    c_list = [c for _, c in labels]
    expected_k = cohen_kappa(h_list, c_list)
    assert res.kappa == pytest.approx(expected_k)
    assert res.m16_status == "pass"  # 0.8 / high kappa >= 0.60


def test_order_independent_matching(tmp_path, synthetic_data):
    h_path, k_path, _ = synthetic_data
    # Read human rows and reverse them
    with h_path.open(encoding="utf-8-sig") as f:
        h_rows = list(csv.DictReader(f))
    h_reversed = list(reversed(h_rows))
    h_rev_path = tmp_path / "human_reversed.csv"
    _write_csv(h_rev_path, h_reversed, ["row_id", "label", "note"])

    res_normal = evaluate_batch_a_agreement(human_path=h_path, key_path=k_path)
    res_rev = evaluate_batch_a_agreement(human_path=h_rev_path, key_path=k_path)

    assert res_normal.n == res_rev.n
    assert res_normal.observed_agreement == pytest.approx(res_rev.observed_agreement)
    assert res_normal.expected_agreement == pytest.approx(res_rev.expected_agreement)
    assert res_normal.kappa == pytest.approx(res_rev.kappa)
    assert res_normal.confusion_matrix == res_rev.confusion_matrix


def test_duplicate_row_id_detected(tmp_path):
    h_rows = [
        {"row_id": "r1", "label": "correct", "note": ""},
        {"row_id": "r1", "label": "partial", "note": ""},
        {"row_id": "r2", "label": "wrong", "note": ""},
    ]
    k_rows = [
        {"row_id": "r1", "checker_outcome": "correct", "checker_reason": ""},
        {"row_id": "r2", "checker_outcome": "wrong", "checker_reason": ""},
    ]
    h_path = tmp_path / "h_dup.csv"
    k_path = tmp_path / "k_dup.csv"
    _write_csv(h_path, h_rows, ["row_id", "label", "note"])
    _write_csv(k_path, k_rows, ["row_id", "checker_outcome", "checker_reason"])

    res = evaluate_batch_a_agreement(human_path=h_path, key_path=k_path)
    assert "r1" in res.duplicate_ids
    assert any("Duplicate row IDs found" in err for err in res.errors)


def test_missing_and_unexpected_ids_detected(tmp_path):
    h_rows = [
        {"row_id": "r1", "label": "correct", "note": ""},
        {"row_id": "r_missing_in_key", "label": "partial", "note": ""},
    ]
    k_rows = [
        {"row_id": "r1", "checker_outcome": "correct", "checker_reason": ""},
    ]
    h_path = tmp_path / "h_miss.csv"
    k_path = tmp_path / "k_miss.csv"
    _write_csv(h_path, h_rows, ["row_id", "label", "note"])
    _write_csv(k_path, k_rows, ["row_id", "checker_outcome", "checker_reason"])

    res = evaluate_batch_a_agreement(human_path=h_path, key_path=k_path)
    assert "r_missing_in_key" in res.missing_ids
    assert any("not found in checker key" in err for err in res.errors)


def test_confusion_matrix_correctness(tmp_path):
    h_rows = [
        {"row_id": "r1", "label": "correct", "note": ""},
        {"row_id": "r2", "label": "partial", "note": ""},
        {"row_id": "r3", "label": "wrong", "note": ""},
        {"row_id": "r4", "label": "unsure", "note": ""},
    ]
    k_rows = [
        {"row_id": "r1", "checker_outcome": "correct", "checker_reason": ""},  # (correct, correct)
        {"row_id": "r2", "checker_outcome": "wrong", "checker_reason": ""},    # (partial, wrong)
        {"row_id": "r3", "checker_outcome": "correct", "checker_reason": ""},  # (wrong, correct)
        {"row_id": "r4", "checker_outcome": "unsure", "checker_reason": ""},   # (unsure, unsure)
    ]
    h_path = tmp_path / "h_cm.csv"
    k_path = tmp_path / "k_cm.csv"
    _write_csv(h_path, h_rows, ["row_id", "label", "note"])
    _write_csv(k_path, k_rows, ["row_id", "checker_outcome", "checker_reason"])

    res = evaluate_batch_a_agreement(human_path=h_path, key_path=k_path)
    cm = res.confusion_matrix
    assert cm["correct"]["correct"] == 1
    assert cm["partial"]["wrong"] == 1
    assert cm["wrong"]["correct"] == 1
    assert cm["unsure"]["unsure"] == 1
    assert cm["correct"]["wrong"] == 0


def test_insufficient_sample_size_withheld(tmp_path):
    # Only 5 samples (< MIN_N = 10)
    h_rows = [{"row_id": f"r{i}", "label": "correct", "note": ""} for i in range(5)]
    k_rows = [{"row_id": f"r{i}", "checker_outcome": "correct", "checker_reason": ""} for i in range(5)]
    h_path = tmp_path / "h_small.csv"
    k_path = tmp_path / "k_small.csv"
    _write_csv(h_path, h_rows, ["row_id", "label", "note"])
    _write_csv(k_path, k_rows, ["row_id", "checker_outcome", "checker_reason"])

    res = evaluate_batch_a_agreement(human_path=h_path, key_path=k_path)
    assert res.n == 5
    assert res.m16_status == "not_measured"


def test_integration_production_batch_a_dataset():
    """Verify agreement evaluation on the real 50-row Batch A human annotations."""
    res = evaluate_batch_a_agreement(DEFAULT_HUMAN_PATH, DEFAULT_KEY_PATH)
    assert res.n == 50
    assert len(res.duplicate_ids) == 0
    assert len(res.missing_ids) == 0
    assert len(res.unexpected_ids) == 0
    assert len(res.errors) == 0

    assert res.observed_agreement == pytest.approx(0.3600, abs=1e-3)
    assert res.expected_agreement == pytest.approx(0.2472, abs=1e-3)
    assert res.kappa == pytest.approx(0.1498, abs=1e-3)

    # M-16 target is 0.60, so 0.1498 fails the gate
    assert res.m16_target_min == 0.60
    assert res.m16_status == "fail"

    # Specificity check: 0 false passes on human-judged wrong
    assert res.confusion_matrix["wrong"]["wrong"] == 7
    assert res.confusion_matrix["wrong"]["correct"] == 0
    assert res.confusion_matrix["wrong"]["partial"] == 0

    # Human distribution: 16 correct, 26 partial, 8 wrong, 0 unsure
    assert sum(res.confusion_matrix["correct"].values()) == 16
    assert sum(res.confusion_matrix["partial"].values()) == 26
    assert sum(res.confusion_matrix["wrong"].values()) == 8
    assert sum(res.confusion_matrix["unsure"].values()) == 0


def test_scorecard_reflects_batch_a_m16():
    """Verify that scorecard integrates Batch A agreement under M-16."""
    card = scorecard.build(split="heldout")
    m16 = next((m for m in card["metrics"] if m["id"] == "M-16"), None)
    assert m16 is not None
    assert m16["n"] == 50
    assert m16["value"] == pytest.approx(0.1498, abs=1e-3)
    assert m16["status"] == "fail"
    assert "Batch A" in m16["how"]


def test_cli_main_generates_reports(tmp_path, capsys):
    out_json = tmp_path / "test_report.json"
    out_md = tmp_path / "test_report.md"

    exit_code = main([
        "--human", str(DEFAULT_HUMAN_PATH),
        "--key", str(DEFAULT_KEY_PATH),
        "--out-json", str(out_json),
        "--out-md", str(out_md),
    ])
    assert exit_code == 0
    assert out_json.exists()
    assert out_md.exists()

    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data["n"] == 50
    assert data["cohen_kappa"] == pytest.approx(0.1498, abs=1e-3)
    assert "confusion_matrix" in data

    md_content = out_md.read_text(encoding="utf-8")
    assert "0.1498" in md_content
    assert "Confusion Matrix" in md_content

    captured = capsys.readouterr().out
    assert "HUMAN-SYSTEM AGREEMENT EVALUATION" in captured
