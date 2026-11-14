"""LLM-judge validation against human labels (TASKS.md task 13; M-16, H6; Project Expectation §7).

Joins the labelled teacher sheet with its key (`research/labels/`), then scores two raters against the human:
- the deterministic checker (its verdict is in the key, computed when the sheet was built);
- a prompt-only LLM judge, given exactly the labeller's instructions (`docs/research/annotator_guide_batch_a.md`,
  sections 1 and 3) and nothing else.

Reports Cohen's κ on the four labels (correct / partial / wrong / unsure) with a bootstrap 95% CI, κ on the binary
correct vs not-correct split, accuracy and confusion tables, on the same rows for both raters. H6 holds when the
checker's κ ≥ 0.6 and it is higher than the judge's.

    set -a; source .env; set +a; python -m setu.research.judge_eval [labelled_sheet.csv]

Rows with an empty label are skipped. Without SETU_LLM_URL only checker vs human is reported.
"""
import csv
import json
import os
import random
import sys
from collections import Counter
from pathlib import Path

from setu.agents.llm import OpenAICompatible, parse_json

from .agreement import MIN_N, cohen_kappa
from .generation_baselines import Throttled

ROOT = Path(__file__).resolve().parents[2]
LABELS = ROOT / "research/labels"
OUT = ROOT / "reports/judge_eval.json"
LABEL_SET = ("correct", "partial", "wrong", "unsure")
H6_KAPPA = 0.6
BOOT, SEED = 1000, 20261113
GUIDE = ROOT / "docs/research/annotator_guide_batch_a.md"  # what the batch A labeller was given
REPLY = '\nReply with one JSON object only: {"label": "<correct | partial | wrong | unsure>"}'


def judge_system() -> str:
    """The labeller's guide, sections 1 (context) and 3 (labels): the judge gets the human's instructions, minus the
    column list and the CSV-handling rules, plus the reply format."""
    text = GUIDE.read_text(encoding="utf-8")
    context = text[text.index("\n## 1."):text.index("\n## 2.")]
    labels = text[text.index("\n## 3."):text.index("\n## 4.")]
    return (context + labels).replace("---", "").strip() + REPLY


def _read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load(sheet: Path = LABELS / "teacher_label_sheet.csv", key: Path = LABELS / "teacher_label_key.csv") -> list[dict]:
    """Labelled rows joined with the key. A label outside LABEL_SET is an error, not silently dropped."""
    keys = {r["row_id"]: r for r in _read(key)}
    rows = []
    for r in _read(sheet):
        label = (r.get("label") or "").strip().lower()
        if not label:
            continue
        if label not in LABEL_SET:
            raise ValueError(f'row {r["row_id"]}: label "{r["label"]}" is not one of {LABEL_SET}')
        rows.append(r | keys[r["row_id"]] | {"human": label})
    return rows


def judge(provider, row: dict) -> tuple[str | None, object]:
    """The judge's label (or "invalid" for an unusable reply), and the completion. None means no model reply."""
    msgs = [{"role": "system", "content": judge_system()},
            {"role": "user", "content": f"Hindi meaning: {row['hindi_meaning']}\nClassmate's sentence: "
                                        f"{row['classmate_sentence']}\nLearner's correction: {row['learner_correction']}"}]
    c = provider.complete(msgs, max_tokens=40, temperature=0.0)
    if not c.ok:
        return None, c
    obj = parse_json(c.text, ("label",))
    label = obj["label"].strip().lower() if obj and isinstance(obj["label"], str) else None
    return (label if label in LABEL_SET else "invalid"), c


def _binary(labels):
    return ["correct" if x == "correct" else "not_correct" for x in labels]


def bootstrap_ci(a, b, n: int = BOOT, seed: int = SEED):
    rng, idx, ks = random.Random(seed), range(len(a)), []
    for _ in range(n):
        s = [rng.choice(idx) for _ in idx]
        k = cohen_kappa([a[i] for i in s], [b[i] for i in s])
        if k is not None:
            ks.append(k)
    if len(ks) < n // 2:
        return None
    ks.sort()
    return [round(ks[int(0.025 * len(ks))], 3), round(ks[int(0.975 * len(ks)) - 1], 3)]


def score(human: list, rater: list) -> dict:
    n = len(human)
    if n < MIN_N:
        return {"n": n, "kappa": None, "reason": "too_few"}
    k = cohen_kappa(human, rater)
    return {"n": n, "kappa": k, "kappa_ci95": bootstrap_ci(human, rater),
            "kappa_binary": cohen_kappa(_binary(human), _binary(rater)),
            "accuracy": sum(h == r for h, r in zip(human, rater, strict=True)) / n,
            "confusion": {f"{h}->{r}": c for (h, r), c in sorted(Counter(zip(human, rater, strict=True)).items())}}


def run(rows: list[dict], provider=None) -> dict:
    out = {"labelled_rows": len(rows), "human_labels": dict(Counter(r["human"] for r in rows)),
           "by_batch": dict(Counter(r["batch"] for r in rows))}
    out["checker_all_rows"] = score([r["human"] for r in rows], [r["checker_outcome"] for r in rows])
    if provider is None:
        return out | {"judge": "not_run: no model endpoint (SETU_LLM_URL unset)"}
    judged = []
    for r in rows:
        label, c = judge(provider, r)
        if label is not None:
            judged.append(r | {"judge": label, "tokens": (c.prompt_tokens or 0) + (c.completion_tokens or 0)})
    human = [r["human"] for r in judged]
    checker = score(human, [r["checker_outcome"] for r in judged])  # same rows as the judge
    llm = score(human, [r["judge"] for r in judged])
    out |= {"judged_rows": len(judged), "not_evaluable": len(rows) - len(judged),
            "judge_invalid_rate": sum(r["judge"] == "invalid" for r in judged) / len(judged) if judged else None,
            "judge_tokens": sum(r["tokens"] for r in judged), "checker": checker, "llm_judge": llm}
    kc, kj = checker.get("kappa"), llm.get("kappa")
    out["h6"] = None if kc is None or kj is None else {
        "checker_kappa_at_least_0_6": kc >= H6_KAPPA, "checker_better_than_judge": kc > kj,
        "holds": kc >= H6_KAPPA and kc > kj}
    out["disagreements"] = [{"row_id": r["row_id"], "attempt_kind": r["attempt_kind"], "human": r["human"],
                             "checker": r["checker_outcome"], "judge": r["judge"], "note": r.get("note", "")}
                            for r in judged if len({r["human"], r["checker_outcome"], r["judge"]}) > 1]
    return out


def main(argv=None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    rows = load(Path(args[0])) if args else load()
    provider = OpenAICompatible.from_environment()
    report = {"status": "no_labels"} if not rows else {"status": "run"}
    if rows:
        if provider is not None:
            provider = Throttled(provider, float(os.environ.get("SETU_EVAL_INTERVAL", "6")))
            report |= {"model": provider.model, "reasoning_effort": provider.reasoning_effort}
        report |= run(rows, provider)
        if provider is not None:
            report["provider_calls"] = {"ok": provider.ok, "errors": dict(provider.errors)}
    OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "disagreements"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
