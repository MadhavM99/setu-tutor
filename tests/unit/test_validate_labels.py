"""Unit tests for Batch A human label sheet validator (setu/research/validate_labels.py)."""

import copy
import csv
from pathlib import Path
import pytest

from setu.research.validate_labels import (
    DEFAULT_BATCH_A_PATH,
    DEFAULT_MASTER_PATH,
    EXPECTED_COLUMNS,
    ValidationResult,
    main,
    validate_batch_a,
)


def _write_csv(path: Path, rows: list[dict], fieldnames=None):
    if fieldnames is None:
        fieldnames = EXPECTED_COLUMNS
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


@pytest.fixture
def master_csv(tmp_path):
    rows = [
        {
            "row_id": "id_01",
            "batch": "A",
            "target_language": "Telugu",
            "hindi_meaning": "मैं खा रहा हूँ।",
            "classmate_sentence": "నేను తింటాను",
            "learner_correction": "తింటున్నాను",
            "label": "",
            "note": "",
        },
        {
            "row_id": "id_02",
            "batch": "A",
            "target_language": "Telugu",
            "hindi_meaning": "वह आता है।",
            "classmate_sentence": "అతను వస్తుంది",
            "learner_correction": "వస్తాడు",
            "label": "",
            "note": "",
        },
        {
            "row_id": "id_03",
            "batch": "A",
            "target_language": "Telugu",
            "hindi_meaning": "किताब कहाँ है?",
            "classmate_sentence": "పుస్తకం ఎక్కడ",
            "learner_correction": "పుస్తకం ఎక్కడ ఉంది",
            "label": "",
            "note": "",
        },
        {
            "row_id": "id_04",
            "batch": "B",
            "target_language": "Hindi",
            "hindi_meaning": "B meaning",
            "classmate_sentence": "B sentence",
            "learner_correction": "B fix",
            "label": "",
            "note": "",
        },
    ]
    p = tmp_path / "mock_master.csv"
    _write_csv(p, rows)
    return p


@pytest.fixture
def valid_rows():
    return [
        {
            "row_id": "id_01",
            "batch": "A",
            "target_language": "Telugu",
            "hindi_meaning": "मैं खा रहा हूँ।",
            "classmate_sentence": "నేను తింటాను",
            "learner_correction": "తింటున్నాను",
            "label": "correct",
            "note": "meaning is correct",
        },
        {
            "row_id": "id_02",
            "batch": "A",
            "target_language": "Telugu",
            "hindi_meaning": "वह आता है।",
            "classmate_sentence": "అతను వస్తుంది",
            "learner_correction": "వస్తాడు",
            "label": "partial",
            "note": "subject pronoun omitted",
        },
        {
            "row_id": "id_03",
            "batch": "A",
            "target_language": "Telugu",
            "hindi_meaning": "किताब कहाँ है?",
            "classmate_sentence": "పుస్తకం ఎక్కడ",
            "learner_correction": "పుస్తకం ఎక్కడ ఉంది",
            "label": "wrong",
            "note": "grammar error",
        },
    ]


def test_validate_production_batch_a_sheet_passes():
    """Verify that the completed production Batch A CSV passes all checks."""
    result = validate_batch_a(DEFAULT_BATCH_A_PATH, master_path=DEFAULT_MASTER_PATH)
    assert result.is_valid is True, f"Validation failed with errors: {result.errors}"
    assert result.row_count == 50
    assert len(result.errors) == 0
    assert len(result.duplicate_ids) == 0
    assert len(result.missing_ids) == 0
    assert len(result.unexpected_ids) == 0
    assert len(result.invalid_labels) == 0
    assert len(result.empty_labels) == 0
    assert len(result.empty_notes) == 0
    assert len(result.source_mismatches) == 0
    assert result.label_counts == {"correct": 16, "partial": 26, "wrong": 8, "unsure": 0}
    assert "Validation PASSED" in result.summary()


def test_valid_fixture_passes(tmp_path, master_csv, valid_rows):
    ann_path = tmp_path / "valid.csv"
    _write_csv(ann_path, valid_rows)
    result = validate_batch_a(ann_path, master_path=master_csv)
    assert result.is_valid is True
    assert result.row_count == 3
    assert result.label_counts == {"correct": 1, "partial": 1, "wrong": 1, "unsure": 0}
    assert "Validation PASSED" in result.summary()


def test_missing_required_column(tmp_path, master_csv, valid_rows):
    ann_path = tmp_path / "missing_col.csv"
    cols = [c for c in EXPECTED_COLUMNS if c != "note"]
    _write_csv(ann_path, valid_rows, fieldnames=cols)
    result = validate_batch_a(ann_path, master_path=master_csv)
    assert result.is_valid is False
    assert any("Missing required columns: ['note']" in err for err in result.errors)


def test_unexpected_extra_column(tmp_path, master_csv, valid_rows):
    ann_path = tmp_path / "extra_col.csv"
    cols = EXPECTED_COLUMNS + ["extra_info"]
    rows = [dict(r, extra_info="test") for r in valid_rows]
    _write_csv(ann_path, rows, fieldnames=cols)
    result = validate_batch_a(ann_path, master_path=master_csv)
    assert result.is_valid is False
    assert any("Unexpected extra columns: ['extra_info']" in err for err in result.errors)


def test_column_order_mismatch(tmp_path, master_csv, valid_rows):
    ann_path = tmp_path / "order_mismatch.csv"
    cols = list(reversed(EXPECTED_COLUMNS))
    _write_csv(ann_path, valid_rows, fieldnames=cols)
    result = validate_batch_a(ann_path, master_path=master_csv)
    assert result.is_valid is False
    assert any("Column order mismatch" in err for err in result.errors)


def test_missing_row_id_and_count_mismatch(tmp_path, master_csv, valid_rows):
    ann_path = tmp_path / "missing_row.csv"
    # Drop row 3 (only 2 rows instead of 3)
    _write_csv(ann_path, valid_rows[:2])
    result = validate_batch_a(ann_path, master_path=master_csv)
    assert result.is_valid is False
    assert result.missing_ids == ["id_03"]
    assert any("Row count mismatch" in err for err in result.errors)
    assert any("Missing expected Batch A row IDs" in err for err in result.errors)


def test_duplicate_row_id(tmp_path, master_csv, valid_rows):
    ann_path = tmp_path / "dup_row.csv"
    rows = [valid_rows[0], valid_rows[1], copy.deepcopy(valid_rows[0])]
    _write_csv(ann_path, rows)
    result = validate_batch_a(ann_path, master_path=master_csv)
    assert result.is_valid is False
    assert result.duplicate_ids == ["id_01"]
    assert result.missing_ids == ["id_03"]
    assert any("Duplicate row IDs found" in err for err in result.errors)


def test_unexpected_row_id(tmp_path, master_csv, valid_rows):
    ann_path = tmp_path / "unexpected_row.csv"
    rows = [valid_rows[0], valid_rows[1], copy.deepcopy(valid_rows[2])]
    rows[2]["row_id"] = "id_unknown"
    _write_csv(ann_path, rows)
    result = validate_batch_a(ann_path, master_path=master_csv)
    assert result.is_valid is False
    assert result.unexpected_ids == ["id_unknown"]
    assert result.missing_ids == ["id_03"]
    assert any("Unexpected row IDs not in Batch A" in err for err in result.errors)


def test_invalid_label_rejected(tmp_path, master_csv, valid_rows):
    ann_path = tmp_path / "invalid_label.csv"
    rows = copy.deepcopy(valid_rows)
    rows[1]["label"] = "maybe"
    _write_csv(ann_path, rows)
    result = validate_batch_a(ann_path, master_path=master_csv)
    assert result.is_valid is False
    assert ("id_02", "maybe") in result.invalid_labels
    assert any("invalid label 'maybe'" in err for err in result.errors)
    # Ensure invalid label was not counted in valid label counts
    assert result.label_counts["partial"] == 0
    assert result.label_counts["correct"] == 1
    assert result.label_counts["wrong"] == 1


def test_empty_label_rejected(tmp_path, master_csv, valid_rows):
    ann_path = tmp_path / "empty_label.csv"
    rows = copy.deepcopy(valid_rows)
    rows[0]["label"] = ""
    _write_csv(ann_path, rows)
    result = validate_batch_a(ann_path, master_path=master_csv)
    assert result.is_valid is False
    assert "id_01" in result.empty_labels
    assert any("Row id_01: 'label' is empty." in err for err in result.errors)


def test_empty_note_rejected(tmp_path, master_csv, valid_rows):
    ann_path = tmp_path / "empty_note.csv"
    rows = copy.deepcopy(valid_rows)
    rows[2]["note"] = "   "
    _write_csv(ann_path, rows)
    result = validate_batch_a(ann_path, master_path=master_csv)
    assert result.is_valid is False
    assert "id_03" in result.empty_notes
    assert any("Row id_03: 'note' is empty." in err for err in result.errors)


def test_modified_source_hindi_meaning_rejected(tmp_path, master_csv, valid_rows):
    ann_path = tmp_path / "tampered_hindi.csv"
    rows = copy.deepcopy(valid_rows)
    rows[0]["hindi_meaning"] = "कुछ और अर्थ"
    _write_csv(ann_path, rows)
    result = validate_batch_a(ann_path, master_path=master_csv)
    assert result.is_valid is False
    assert any("source mismatch in 'hindi_meaning'" in err for err in result.errors)


def test_modified_source_learner_correction_rejected(tmp_path, master_csv, valid_rows):
    ann_path = tmp_path / "tampered_correction.csv"
    rows = copy.deepcopy(valid_rows)
    rows[1]["learner_correction"] = "వేరే సమాధానం"
    _write_csv(ann_path, rows)
    result = validate_batch_a(ann_path, master_path=master_csv)
    assert result.is_valid is False
    assert any("source mismatch in 'learner_correction'" in err for err in result.errors)


def test_wrong_batch_or_language_rejected(tmp_path, master_csv, valid_rows):
    ann_path = tmp_path / "wrong_metadata.csv"
    rows = copy.deepcopy(valid_rows)
    rows[0]["batch"] = "B"
    rows[1]["target_language"] = "Hindi"
    _write_csv(ann_path, rows)
    result = validate_batch_a(ann_path, master_path=master_csv)
    assert result.is_valid is False
    assert any("batch must be 'A'" in err for err in result.errors)
    assert any("target_language must be 'Telugu'" in err for err in result.errors)


def test_nonexistent_files_rejected(tmp_path):
    result = validate_batch_a(tmp_path / "does_not_exist.csv", master_path=tmp_path / "no_master.csv")
    assert result.is_valid is False
    assert any("Failed to read master CSV" in err for err in result.errors)


def test_cli_main_exit_codes(tmp_path, master_csv, valid_rows, capsys):
    valid_csv = tmp_path / "valid.csv"
    _write_csv(valid_csv, valid_rows)

    # Valid run exits with 0
    exit_code = main([str(valid_csv), "--master", str(master_csv)])
    assert exit_code == 0
    captured = capsys.readouterr().out
    assert "Validation PASSED" in captured

    # Invalid run exits with 1
    invalid_csv = tmp_path / "invalid.csv"
    _write_csv(invalid_csv, valid_rows[:1])
    exit_code_invalid = main([str(invalid_csv), "--master", str(master_csv)])
    assert exit_code_invalid == 1
    captured_invalid = capsys.readouterr().out
    assert "Validation FAILED" in captured_invalid
