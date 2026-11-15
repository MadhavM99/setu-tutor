"""Validation of Batch A human annotation sheets (Task 12).

Validates that a returned human annotation CSV matches the master sheet,
preserves row IDs and source content, uses only approved label categories,
leaves no labels or notes blank, and covers exactly the 50 Batch A items.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MASTER_PATH = ROOT / "research/labels/teacher_label_sheet.csv"
DEFAULT_BATCH_A_PATH = ROOT / "research/labels/teacher_label_sheet_batch_a.csv"

EXPECTED_COLUMNS = [
    "row_id",
    "batch",
    "target_language",
    "hindi_meaning",
    "classmate_sentence",
    "learner_correction",
    "label",
    "note",
]
SOURCE_COLUMNS = [
    "batch",
    "target_language",
    "hindi_meaning",
    "classmate_sentence",
    "learner_correction",
]
ALLOWED_LABELS = frozenset({"correct", "partial", "wrong", "unsure"})
BATCH_A_TARGET_LANGUAGE = "Telugu"
BATCH_A_BATCH = "A"


@dataclasses.dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    row_count: int
    label_counts: dict[str, int]
    errors: list[str]
    duplicate_ids: list[str] = dataclasses.field(default_factory=list)
    missing_ids: list[str] = dataclasses.field(default_factory=list)
    unexpected_ids: list[str] = dataclasses.field(default_factory=list)
    invalid_labels: list[tuple[str, str]] = dataclasses.field(default_factory=list)
    empty_labels: list[str] = dataclasses.field(default_factory=list)
    empty_notes: list[str] = dataclasses.field(default_factory=list)
    source_mismatches: list[str] = dataclasses.field(default_factory=list)

    def summary(self) -> str:
        lines = []
        lines.append(f"Validation {'PASSED' if self.is_valid else 'FAILED'}")
        lines.append(f"Total Rows: {self.row_count}")
        lines.append("Label Distribution:")
        for label in ["correct", "partial", "wrong", "unsure"]:
            count = self.label_counts.get(label, 0)
            pct = (count / self.row_count * 100) if self.row_count > 0 else 0.0
            lines.append(f"  {label:<8}: {count:>3} ({pct:5.1f}%)")
        if not self.is_valid:
            lines.append(f"Errors ({len(self.errors)}):")
            for err in self.errors:
                lines.append(f"  - {err}")
        return "\n".join(lines)


def _read_csv(path: Path | str) -> tuple[list[str] | None, list[dict[str, str]]]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")
    with p.open(mode="r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames) if reader.fieldnames else None
        rows = list(reader)
    return fieldnames, rows


def validate_batch_a(
    annotated_path: Path | str,
    master_path: Path | str | None = None,
) -> ValidationResult:
    master_p = Path(master_path) if master_path is not None else DEFAULT_MASTER_PATH
    annotated_p = Path(annotated_path)

    errors: list[str] = []
    duplicate_ids: list[str] = []
    missing_ids: list[str] = []
    unexpected_ids: list[str] = []
    invalid_labels: list[tuple[str, str]] = []
    empty_labels: list[str] = []
    empty_notes: list[str] = []
    source_mismatches: list[str] = []
    valid_label_counter: Counter[str] = Counter()

    # 1. Read master sheet to determine expected Batch A items
    try:
        _, master_rows = _read_csv(master_p)
    except (OSError, ValueError, KeyError, csv.Error) as e:
        errors.append(f"Failed to read master CSV '{master_p}': {e}")
        return ValidationResult(
            is_valid=False,
            row_count=0,
            label_counts={},
            errors=errors,
        )

    master_batch_a = [
        r
        for r in master_rows
        if r.get("batch") == BATCH_A_BATCH
        and r.get("target_language") == BATCH_A_TARGET_LANGUAGE
    ]
    expected_ids = [r["row_id"] for r in master_batch_a]
    expected_id_set = set(expected_ids)
    expected_count = len(expected_ids)
    master_map = {r["row_id"]: r for r in master_batch_a}

    # 2. Read annotated CSV
    try:
        cols, rows = _read_csv(annotated_p)
    except (OSError, ValueError, KeyError, csv.Error) as e:
        errors.append(f"Failed to read annotated CSV '{annotated_p}': {e}")
        return ValidationResult(
            is_valid=False,
            row_count=0,
            label_counts={},
            errors=errors,
        )

    # 3. Column check: missing columns, extra columns, order
    if cols is None:
        errors.append("Annotated CSV has no header row.")
        return ValidationResult(
            is_valid=False,
            row_count=0,
            label_counts={},
            errors=errors,
        )

    missing_cols = [c for c in EXPECTED_COLUMNS if c not in cols]
    extra_cols = [c for c in cols if c not in EXPECTED_COLUMNS]
    if missing_cols:
        errors.append(f"Missing required columns: {missing_cols}")
    if extra_cols:
        errors.append(f"Unexpected extra columns: {extra_cols}")
    if not missing_cols and not extra_cols and cols != EXPECTED_COLUMNS:
        errors.append(f"Column order mismatch. Expected {EXPECTED_COLUMNS}, got {cols}")

    # 4. Row count check
    actual_count = len(rows)
    if actual_count != expected_count:
        errors.append(
            f"Row count mismatch: expected {expected_count} rows, found {actual_count}."
        )

    # 5. Row ID checks (duplicates, missing, unexpected)
    seen_ids: set[str] = set()
    row_ids: list[str] = []
    for idx, r in enumerate(rows, start=1):
        rid = (r.get("row_id") or "").strip()
        if not rid:
            errors.append(f"Row {idx} has missing or empty 'row_id'.")
            continue
        if rid in seen_ids and rid not in duplicate_ids:
            duplicate_ids.append(rid)
        seen_ids.add(rid)
        row_ids.append(rid)

    if duplicate_ids:
        errors.append(f"Duplicate row IDs found ({len(duplicate_ids)}): {duplicate_ids}")

    row_id_set = set(row_ids)
    missing_ids = sorted(expected_id_set - row_id_set)
    unexpected_ids = sorted(row_id_set - expected_id_set)

    if missing_ids:
        errors.append(f"Missing expected Batch A row IDs ({len(missing_ids)}): {missing_ids}")
    if unexpected_ids:
        errors.append(f"Unexpected row IDs not in Batch A ({len(unexpected_ids)}): {unexpected_ids}")

    # 6. Row-level checks: batch, target_language, label, note, source match
    for idx, r in enumerate(rows, start=1):
        rid = (r.get("row_id") or "").strip()
        batch_val = (r.get("batch") or "").strip()
        lang_val = (r.get("target_language") or "").strip()
        label_val = (r.get("label") or "").strip().lower()
        note_val = (r.get("note") or "").strip()

        # Batch and language checks
        if batch_val != BATCH_A_BATCH:
            errors.append(f"Row {rid or idx}: batch must be '{BATCH_A_BATCH}', found '{batch_val}'.")
        if lang_val != BATCH_A_TARGET_LANGUAGE:
            errors.append(
                f"Row {rid or idx}: target_language must be '{BATCH_A_TARGET_LANGUAGE}', found '{lang_val}'."
            )

        # Label checks
        if not label_val:
            empty_labels.append(rid or f"row_{idx}")
            errors.append(f"Row {rid or idx}: 'label' is empty.")
        elif label_val not in ALLOWED_LABELS:
            invalid_labels.append((rid or f"row_{idx}", label_val))
            errors.append(
                f"Row {rid or idx}: invalid label '{label_val}'. Allowed: {sorted(ALLOWED_LABELS)}."
            )
        else:
            valid_label_counter[label_val] += 1

        # Note checks
        if not note_val:
            empty_notes.append(rid or f"row_{idx}")
            errors.append(f"Row {rid or idx}: 'note' is empty.")

        # Source column checks against master
        if rid in master_map:
            master_r = master_map[rid]
            for col in SOURCE_COLUMNS:
                orig = (master_r.get(col) or "").strip()
                curr = (r.get(col) or "").strip()
                if orig != curr:
                    desc = f"Row {rid} source mismatch in '{col}': expected {orig!r}, found {curr!r}"
                    source_mismatches.append(desc)
                    errors.append(desc)

    # Label distribution summary (only valid labels counted)
    label_counts = {
        lbl: valid_label_counter.get(lbl, 0)
        for lbl in ["correct", "partial", "wrong", "unsure"]
    }
    is_valid = len(errors) == 0

    return ValidationResult(
        is_valid=is_valid,
        row_count=actual_count,
        label_counts=label_counts,
        errors=errors,
        duplicate_ids=duplicate_ids,
        missing_ids=missing_ids,
        unexpected_ids=unexpected_ids,
        invalid_labels=invalid_labels,
        empty_labels=empty_labels,
        empty_notes=empty_notes,
        source_mismatches=source_mismatches,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Batch A human annotation CSV.")
    parser.add_argument(
        "annotated",
        nargs="?",
        default=str(DEFAULT_BATCH_A_PATH),
        help="Path to annotated Batch A CSV (default: %(default)s)",
    )
    parser.add_argument(
        "--master",
        default=str(DEFAULT_MASTER_PATH),
        help="Path to master teacher label sheet (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    result = validate_batch_a(args.annotated, master_path=args.master)
    print(result.summary())
    return 0 if result.is_valid else 1


if __name__ == "__main__":
    sys.exit(main())
