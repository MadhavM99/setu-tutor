"""Teacher label sheet for checker–teacher agreement (M-16, DQ-14).

Builds 145 learner corrections from the content bank: the correct form and its variants, the planted error left
unchanged, half-fixes, a kept Hindi habit word, one-character slips, fragments, other-script typing and another
item's sentence. Rows are shuffled under random ids and the sheet never shows the checker's verdict or the reference
answer, so the labeller is blind to both. The checker's verdicts go to a separate key file that is not shared with
the labeller; `agreement.py` joins the two on `row_id`.

Batch A (50 rows, Hindi->Telugu only) is for the native Telugu speaker; batch B is the rest.

    python -m setu.research.label_sheet     # rewrite research/labels/teacher_label_{sheet,key}.csv
"""
import csv
import random
import unicodedata
import uuid
from collections import defaultdict
from pathlib import Path

from setu.domain import checker, normalise
from setu.research.stage_a import _items, item_key

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "research/labels"
SEED = 20261112
SIZE, BATCH_A = 145, 50
SHEET_COLS = ["row_id", "batch", "target_language", "hindi_meaning", "classmate_sentence", "learner_correction",
              "label", "note"]
KEY_COLS = ["row_id", "item_id", "rule_id", "direction", "attempt_kind", "checker_outcome", "checker_reason"]


def _drop_vowel_sign(form: str) -> str | None:
    """A one-character slip: the last vowel sign in the sentence left out."""
    for i in range(len(form) - 1, -1, -1):
        if unicodedata.category(form[i]) in ("Mn", "Mc") and unicodedata.name(form[i], "").find("VIRAMA") < 0:
            return form[:i] + form[i + 1:]
    return None


def attempts(rule, it, items) -> list[tuple[str, str]]:
    correct, wrong = it["correct_form"], it["wrong_form"]
    accepted = [correct, *(v["form"] for v in it["accepted_variants"])]
    out = [("correct_form", correct)]
    out += [(f"variant_{k}", f) for k, f in enumerate(accepted[1:])]
    out.append(("planted_unchanged", wrong))
    accepted_tokens = {t for f in accepted for t in f.split()}
    habit = [t for t in wrong.split() if t not in accepted_tokens]
    if habit:
        rest = " ".join(t for t in wrong.split() if t not in habit)
        if rest:
            out.append(("habit_removed_only", rest))
        kept = f"{' '.join(habit)} {correct}" if wrong.split()[0] in habit else f"{correct} {' '.join(habit)}"
        out.append(("fixed_but_habit_kept", kept))
    if slip := _drop_vowel_sign(correct):
        out.append(("spelling_slip", slip))
    if len(correct.split()) > 1:
        out.append(("fragment", correct.split()[-1]))
    target_telugu = rule["direction"] == "HI->TE"
    out.append(("other_script_typing", normalise.to_devanagari(correct) if target_telugu else normalise.to_telugu(correct)))
    sibling = next((o for r, o in items if r["rule_id"] == rule["rule_id"] and o["item_id"] != it["item_id"]), None)
    if sibling:
        out.append(("other_item_sentence", sibling["correct_form"]))
    seen, uniq = set(), []
    for kind, text in out:
        if text and text not in seen:
            seen.add(text)
            uniq.append((kind, text))
    return uniq


def build() -> tuple[list[dict], list[dict]]:
    items = [(r, it) for r, it in _items() if it.get("wrong_form")]
    rng = random.Random(SEED)
    pool = []
    for rule, it in items:
        key = item_key(rule, it, items)
        for kind, text in attempts(rule, it, items):
            v = checker.check_fix(attempt_id=uuid.uuid4(), raw=text, item=key, response_mode="typed").verdict
            pool.append({"rule": rule, "item": it, "kind": kind, "text": text,
                         "outcome": v.outcome, "reason": v.reason_code})

    def stratified(rows, n):
        """Round-robin over (attempt kind, checker outcome) so rare cells are not crowded out."""
        cells = defaultdict(list)
        for r in rows:
            cells[(r["kind"], r["outcome"])].append(r)
        for c in cells.values():
            rng.shuffle(c)
        order, picked = sorted(cells), []
        while len(picked) < n and any(cells.values()):
            for c in order:
                if cells[c] and len(picked) < n:
                    picked.append(cells[c].pop())
        return picked

    batch_a = stratified([r for r in pool if r["rule"]["direction"] == "HI->TE"], BATCH_A)
    taken = {id(r) for r in batch_a}
    batch_b = stratified([r for r in pool if id(r) not in taken], SIZE - BATCH_A)
    sheet, key = [], []
    for batch, rows in (("A", batch_a), ("B", batch_b)):
        rng.shuffle(rows)
        for r in rows:
            rid = f"{rng.getrandbits(32):08x}"
            hi_te = r["rule"]["direction"] == "HI->TE"
            sheet.append({"row_id": rid, "batch": batch, "target_language": "Telugu" if hi_te else "Hindi",
                          "hindi_meaning": r["item"]["l1_meaning"], "classmate_sentence": r["item"]["wrong_form"],
                          "learner_correction": r["text"], "label": "", "note": ""})
            key.append({"row_id": rid, "item_id": r["item"]["item_id"], "rule_id": r["rule"]["rule_id"],
                        "direction": r["rule"]["direction"], "attempt_kind": r["kind"],
                        "checker_outcome": r["outcome"], "checker_reason": r["reason"]})
    return sheet, key


def _write(path: Path, cols, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    sheet, key = build()
    OUT.mkdir(parents=True, exist_ok=True)
    _write(OUT / "teacher_label_sheet.csv", SHEET_COLS, sheet)
    _write(OUT / "teacher_label_key.csv", KEY_COLS, key)
    print(f"{len(sheet)} rows ({sum(r['batch'] == 'A' for r in sheet)} in batch A) -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
