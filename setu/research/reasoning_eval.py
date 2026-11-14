"""Reasoning evaluation (TASKS.md task 15; Project Expectation §2 capability 3: "analyse the intermediate steps").

Runs `diagnose.diagnose` with each method on learner corrections whose ground truth is known by construction:
- `stage_a`:  the Stage-A checker cases that are wrong (planted_unchanged, fragment), Hindi→Telugu only (the diagnosis
              prompt is written for learners of Telugu). Both splits: the prompts were never tuned on any Stage-A case;
- `extended`: Hindi→Telugu attempts from the label-sheet generator that Stage-A lacks (habit kept beside the fix,
              a spelling slip, another item's sentence, and the correct sentence itself, to catch false alarms).
The two sets are reported separately.

Truth per case: the wrong word(s) ("none" when a word is missing or nothing is wrong), the rule id (None for a correct
sentence), and the error type. Metrics per method: accuracy of each step, final-answer accuracy (every scored field
right), valid-answer rate, agreement of the error type with the checker (`CHECKER_TO_TYPE`), and for `stepwise` how
often the self-check revised an answer and whether the revision fixed or broke it. Baseline `direct`, ablation
`no_self_check`.

    set -a; source .env; set +a; python -m setu.research.reasoning_eval
"""
import json
import os
import statistics
import uuid
from pathlib import Path

from setu.agents import diagnose
from setu.agents.llm import OpenAICompatible
from setu.domain import checker

from .generation_baselines import Throttled
from .label_sheet import attempts
from .stage_a import _items, item_key, load_cases

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports/reasoning_eval.json"
FIELDS = ("wrong_word", "rule_id", "error_type")
EXTENDED_KINDS = {"fixed_but_habit_kept": "habit_kept", "spelling_slip": "spelling_slip",
                  "other_item_sentence": "other_sentence", "correct_form": "correct"}


def _accepted_tokens(it) -> set:
    return {t for f in (it["correct_form"], *(v["form"] for v in it["accepted_variants"])) for t in f.split()}


def _case(rule, it, items, kind, text, error_type) -> dict:
    accepted = _accepted_tokens(it)
    habit = {t for t in it["wrong_form"].split() if t not in accepted}
    if error_type == "habit_kept":
        words = {t for t in text.split() if t in habit}
    elif error_type == "spelling_slip":
        words = {t for t in text.split() if t not in accepted}
    else:  # a missing word, another sentence or nothing wrong: no single wrong word to point to
        words = {"none"}
    v = checker.check_fix(attempt_id=uuid.uuid4(), raw=text, item=item_key(rule, it, items),
                          response_mode="typed").verdict
    return {"id": f"{it['item_id']}:{kind}", "kind": kind, "direction": rule["direction"],
            "hindi_meaning": it["l1_meaning"], "classmate_sentence": it["wrong_form"], "learner_text": text,
            "truth": {"wrong_word": sorted(words) or None, "rule_id": None if error_type == "correct" else rule["rule_id"],
                      "error_type": error_type},
            "checker_type": diagnose.CHECKER_TO_TYPE.get(v.reason_code)}


def stage_a_cases() -> list[dict]:
    items = _items()
    by_id = {it["item_id"]: (r, it) for r, it in items}
    out = []
    for c in load_cases():
        kind = c["id"].rsplit(":", 1)[1]
        if c["group"] != "checker" or kind not in ("planted_unchanged", "fragment"):
            continue
        rule, it = by_id[c["item_id"]]
        if rule["direction"] == "HI->TE":
            out.append(_case(rule, it, items, kind, c["input"],
                             "habit_kept" if kind == "planted_unchanged" else "word_missing_or_extra"))
    return out


def extended_cases() -> list[dict]:
    items = [(r, it) for r, it in _items() if it.get("wrong_form")]
    return [_case(rule, it, items, kind, text, EXTENDED_KINDS[kind])
            for rule, it in items if rule["direction"] == "HI->TE"
            for kind, text in attempts(rule, it, items) if kind in EXTENDED_KINDS]


def rules_for(direction: str) -> list[tuple[str, str]]:
    seen = {}
    for r, _ in _items():
        if r["direction"] == direction:
            seen[r["rule_id"]] = r.get("title_en") or r.get("title_l1") or ""
    return sorted(seen.items())


def correct(field: str, got, truth) -> bool | None:
    """None when the field is not scored for this case."""
    want = truth[field]
    if want is None:
        return None
    return got in want if field == "wrong_word" else got == want


def _pre_check(d: diagnose.Diagnosis) -> dict:
    """The three answers before the self-check (from steps 1-3)."""
    by = {s.name: s for s in d.steps}
    return {f: (by[n].answer or {}).get(f) if n in by and by[n].valid else None
            for f, n in zip(FIELDS, ("wrong_word", "rule", "error_type"), strict=True)}


def row(case: dict, d: diagnose.Diagnosis) -> dict:
    t = case["truth"]
    got = {f: getattr(d, f) for f in FIELDS}
    marks = {f: correct(f, got[f], t) for f in FIELDS}
    r = {"id": case["id"], "kind": case["kind"], "evaluable": any(s.completion.ok for s in d.steps),
         "steps_valid": [s.valid for s in d.steps], "marks": marks,
         "final_correct": all(m for m in marks.values() if m is not None),
         "agrees_with_checker": None if case["checker_type"] is None else got["error_type"] == case["checker_type"],
         "revised": d.revised, "calls": len(d.steps),
         "tokens": sum((s.completion.prompt_tokens or 0) + (s.completion.completion_tokens or 0) for s in d.steps),
         "latency": [s.completion.latency_ms for s in d.steps], "answer": got}
    if d.method == "stepwise":
        pre = _pre_check(d)
        before = {f: correct(f, pre[f], t) for f in FIELDS}
        r["revision_fixed"] = sum(1 for f in FIELDS if before[f] is False and marks[f] is True)
        r["revision_broke"] = sum(1 for f in FIELDS if before[f] is True and marks[f] is False)
    return r


def summarise(rows: list[dict]) -> dict:
    ev = [r for r in rows if r["evaluable"]]
    out = {"cases": len(rows), "evaluable": len(ev)}
    if not ev:
        return out | {"status": "not_evaluable: no model reply"}
    n = len(ev)

    def rate(xs):
        xs = [x for x in xs if x is not None]
        return sum(xs) / len(xs) if xs else None

    out |= {f"{f}_accuracy": rate(r["marks"][f] for r in ev) for f in FIELDS}
    out |= {"final_accuracy": sum(r["final_correct"] for r in ev) / n,
            "valid_step_rate": rate(v for r in ev for v in r["steps_valid"]),
            "checker_agreement": rate(r["agrees_with_checker"] for r in ev),
            "calls_per_case": sum(r["calls"] for r in ev) / n, "tokens_per_case": sum(r["tokens"] for r in ev) / n,
            "median_latency_ms": statistics.median(x for r in ev for x in r["latency"]),
            "by_kind": {k: sum(r["final_correct"] for r in ev if r["kind"] == k) / c
                        for k in sorted({r["kind"] for r in ev})
                        if (c := sum(r["kind"] == k for r in ev))}}
    if "revision_fixed" in ev[0]:
        out |= {"self_check_revised_rate": sum(r["revised"] for r in ev) / n,
                "revisions_fixed": sum(r["revision_fixed"] for r in ev),
                "revisions_broke": sum(r["revision_broke"] for r in ev)}
    return out


def run(provider, sets: dict[str, list[dict]] | None = None) -> dict:
    sets = sets if sets is not None else {"stage_a": stage_a_cases(), "extended": extended_cases()}
    out = {}
    for name, cases in sets.items():
        out[name] = {}
        for method in diagnose.METHODS:
            rows = [row(c, diagnose.diagnose(provider, hindi_meaning=c["hindi_meaning"],
                                             classmate_sentence=c["classmate_sentence"], learner_text=c["learner_text"],
                                             rules=rules_for(c["direction"]), method=method)) for c in cases]
            out[name][method] = {"role": {"stepwise": "method", "no_self_check": "ablation",
                                          "direct": "baseline"}[method]} | summarise(rows)
            out[name][method]["rows"] = rows
    return out


def main() -> int:
    sets = {"stage_a": stage_a_cases(), "extended": extended_cases()}
    report = {"cases": {k: len(v) for k, v in sets.items()}}
    provider = OpenAICompatible.from_environment()
    if provider is None:
        report |= {"status": "not_run", "reason": "no model endpoint (SETU_LLM_URL unset)",
                   "calls_needed_at_most": sum(len(v) for v in sets.values()) * 8}
    else:
        provider = Throttled(provider, float(os.environ.get("SETU_EVAL_INTERVAL", "6")))
        report |= {"status": "run", "model": provider.model, "reasoning_effort": provider.reasoning_effort,
                   "results": run(provider, sets), "provider_calls": {"ok": provider.ok, "errors": dict(provider.errors)}}
    OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "results"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
