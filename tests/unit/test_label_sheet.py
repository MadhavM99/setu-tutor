"""Teacher label sheet (M-16, DQ-14): reproducible, blind, and the committed files match the content."""
import csv

from setu.research import label_sheet


def _read(name):
    with (label_sheet.OUT / name).open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def test_sheet_is_reproducible_and_matches_the_committed_files():
    sheet, key = label_sheet.build()
    assert sheet == _read("teacher_label_sheet.csv") and key == _read("teacher_label_key.csv")


def test_sheet_is_blind_and_batches_are_the_right_size():
    sheet, key = label_sheet.build()
    assert len(sheet) == label_sheet.SIZE and len({r["row_id"] for r in sheet}) == label_sheet.SIZE
    assert list(sheet[0]) == label_sheet.SHEET_COLS
    assert not {"checker_outcome", "checker_reason", "attempt_kind", "item_id"} & set(sheet[0])
    a = [r for r in sheet if r["batch"] == "A"]
    assert len(a) == label_sheet.BATCH_A and {r["target_language"] for r in a} == {"Telugu"}
    assert {r["row_id"] for r in sheet} == {r["row_id"] for r in key}
    assert {r["checker_outcome"] for r in key} == {"correct", "partial", "wrong", "unsure"}
