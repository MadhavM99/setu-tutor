"""Scorecard v1 (M-49, X-GATE-01/02, metrics-and-gates.md §3).

Computes every metric that can be measured today, compares it with the frozen target in `research/thresholds.yaml`,
and lists every other gate metric as not measured, with the reason. It never fills in a number it does not have.

    python -m setu.research.scorecard --split heldout     # writes reports/scorecard-<date>.md and .json
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

import yaml

from . import stage_a

ROOT = Path(__file__).resolve().parents[2]
THRESHOLDS = ROOT / "research/thresholds.yaml"
CAVEAT = ("Module-test numbers come from cases the team generated from the same content the system uses, so they "
          "test the machinery and are optimistic. They are not evidence about learners or about any language model.")
NOT_MEASURED = {
    "M-01": "needs model drafts (Phase 4) and the prompt-only baseline",
    "M-02": "needs model drafts (Phase 4) and teacher verification",
    "M-03": "needs model drafts (Phase 4)",
    "M-04": "needs sessions over time (simulator, Phase 4)",
    "M-06": "guarded by database triggers and TS-CLS / TS-AUTH tests; a rate needs logged sessions",
    "M-12": "needs the agent loop with a model (Phase 4)",
    "M-13": "needs the agent loop with a model (Phase 4)",
    "M-16": "needs teacher labels (145-row sheet not yet labelled)",
    "M-17": "guarded by the OutcomeWriter and TS-CLS tests; a rate needs logged sessions",
    "M-18": "needs coach hints (Phase 3–4)",
    "M-27": "needs the running loop with a model (Phase 4–5)",
    "M-56": "needs model drafts (Phase 4)",
    "M-57": "needs memory-aid drafts and the grounding validator (Phase 4)",
}


def load_thresholds() -> dict:
    return yaml.safe_load(THRESHOLDS.read_text(encoding="utf-8"))


def _status(value, target) -> str:
    if value is None:
        return "not_measured"
    if "min" in target and value < target["min"]:
        return "fail"
    if "max" in target and value > target["max"]:
        return "fail"
    return "pass"


def _rate(results, pred) -> tuple[float | None, int]:
    sel = [r for r in results if pred(r)]
    return (None, 0) if not sel else (sum(1 for r in sel if r["passed"]) / len(sel), len(sel))


def build(*, split: str = "heldout") -> dict:
    cases = stage_a.split(stage_a.load_cases(), split)
    results = []
    for c in cases:
        passed, observed = stage_a.run_case(c)
        results.append({**c, "passed": passed, "observed": observed})
    checker = [r for r in results if r["group"] == "checker"]
    wrong_caught, n_wrong = _rate(checker, lambda r: r["expect"] in ("wrong", "not_correct"))
    right_ok, n_right = _rate(checker, lambda r: r["expect"] == "correct")
    unsure = sum(1 for r in checker if r["observed"] == "unsure" and r["expect"] != "unsure")
    expected_answers = [r for r in checker if r["expect"] != "unsure"]
    no_error, n_ne = _rate(results, lambda r: r["group"] == "planting" and r.get("expect_ok"))
    attacks = [r for r in results if r["group"] == "attack"]

    from scripts import lint_hindi

    latin = lint_hindi.lint_catalog(ROOT / "locale/hi.yaml", allow_file=ROOT / "locale/allow-latin.txt")
    latin += lint_hindi.lint_templates(ROOT / "setu/web/templates")

    measured = {
        "M-05": (no_error, n_ne, "planting cases: no-error sentences pass with zero errors"),
        "M-07": (wrong_caught, n_wrong, "checker cases expected wrong or not correct"),
        "M-08": (None if right_ok is None else 1 - right_ok, n_right, "checker cases expected correct"),
        "M-09": (unsure / len(expected_answers) if expected_answers else None, len(expected_answers),
                 "unsure on checker cases that have a known answer"),
        "M-14": (sum(1 for r in attacks if not r["passed"]), len(attacks), "injection inputs judged correct"),
        "M-54": (len([v for v in latin if "latin" in v.problem]), None, "Hindi lint over catalog and templates"),
    }
    thresholds = load_thresholds()
    metrics = []
    for mid, target in thresholds.items():
        if mid in measured:
            value, n, how = measured[mid]
            metrics.append({"id": mid, "value": value, "n": n, "target": target, "status": _status(value, target),
                            "how": how})
        else:
            metrics.append({"id": mid, "value": None, "n": 0, "target": target, "status": "not_measured",
                            "how": NOT_MEASURED.get(mid, "not measurable yet")})
    return {
        "date": dt.date.today().isoformat(), "split": split, "cases": len(results),
        "groups": {g: sum(1 for r in results if r["group"] == g) for g in sorted({r["group"] for r in results})},
        "failures": [{"id": r["id"], "observed": r["observed"]} for r in results if not r["passed"]],
        "metrics": metrics, "caveat": CAVEAT,
        "thresholds_sha256": hashlib.sha256(THRESHOLDS.read_bytes()).hexdigest(),
        "versions": _versions(),
    }


def _versions() -> dict:
    from setu.domain import checker, leveler, normalise, planner, scheduler, tokenize

    return {"checker": checker.VERSION, "normaliser": normalise.VERSION, "tokenizer": tokenize.VERSION,
            "leveler": leveler.VERSION, "planner": planner.VERSION, "tracker": scheduler.TRACKER_VERSION,
            "fsrs": scheduler.FSRS_VERSION}


def write(card: dict, out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = out_dir / f"scorecard-{card['date']}-{card['split']}"
    stem.with_suffix(".json").write_text(json.dumps(card, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [f"# Scorecard {card['date']} ({card['split']} split, {card['cases']} cases)", "", f"> {card['caveat']}", "",
             "| Metric | Value | n | Target | Status | How |", "|---|---|---|---|---|---|"]
    for m in card["metrics"]:
        value = "—" if m["value"] is None else (f"{m['value']:.3f}" if isinstance(m["value"], float) else m["value"])
        target = ", ".join(f"{k} {v}" for k, v in m["target"].items() if k != "note")
        status = {"pass": "pass", "fail": "**FAIL**", "not_measured": "not measured"}[m["status"]]
        lines.append(f"| {m['id']} | {value} | {m['n'] or '—'} | {target} | {status} | {m['how']} |")
    lines += ["", f"Failures: {len(card['failures'])}", *[f"- {f['id']}: {f['observed']}" for f in card["failures"]],
              "", "Versions: " + ", ".join(f"{k} {v}" for k, v in card["versions"].items()),
              f"Thresholds sha256: {card['thresholds_sha256']}"]
    path = stem.with_suffix(".md")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m setu.research.scorecard")
    ap.add_argument("--split", choices=("dev", "heldout"), default="heldout")
    ap.add_argument("--out", default=str(ROOT / "reports"))
    args = ap.parse_args(argv)
    card = build(split=args.split)
    print(write(card, Path(args.out)))
    return 1 if any(m["status"] == "fail" for m in card["metrics"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
