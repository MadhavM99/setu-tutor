"""Task 17: Raju sentence generation on the 29 frozen planting cases, scored by the app's STRICT leak filter.

Pre-registered (docs/submission/drafts/ft_model_choice.md, section 4, 2026-11-13 22:01 IST):
primary = all 29 frozen cases; secondary = the 27 cases of the 14 trained rules; HI-TE-006's 2 cases shown separately
as "untrained rule". Every condition uses the SAME prompt (`classmate._prompt`, method `prompt_only`, one draft) and
the same scoring as task 6 (`generation_baselines.run`). Task 10 was a no-go (reports/ft_data.json), so there is no
tuned model; the conditions are the untuned base model (local) and prompted Gemini.

Per case: `valid` = the draft passed `leakfilter.check_sentence` (planted turn: one planted error of the planned rule
only); `planted` = valid AND exactly the bank's wrong form; `leak` / `oov` from the filter reasons. A case counts only
if the model actually replied (`evaluable`). Rows are appended per case to reports/ft_eval_rows_<label>.jsonl, so a
run can stop and resume; the report is rebuilt from the row files.

    # local base model (needs torch + transformers; see scripts/ft_tokenizer_check.py for the venv)
    PYTHONPATH=. <ftvenv>/bin/python -m setu.research.ft_eval --local unsloth/gemma-3-1b-it --label gemma3_1b_base
    # prompted Gemini (SETU_LLM_* from .env, throttled by SETU_EVAL_INTERVAL)
    .venv/bin/python -m setu.research.ft_eval --gemini --label gemini_prompted
    # report only, from the row files
    .venv/bin/python -m setu.research.ft_eval
"""
import argparse
import json
import os
import statistics
import time
from pathlib import Path

from setu.agents import classmate
from setu.agents.llm import Completion, OpenAICompatible

from . import envfile
from .ft_data import MEANING_DEPENDENT
from .generation_baselines import Throttled, cases
from .stats import mcnemar, wilson

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports"
METHOD = "prompt_only"
CONDITION_ORDER = ("gemma3_1b_tuned", "gemma3_1b_base", "gemini_prompted")
LABELS = {"gemma3_1b_tuned": "Gemma-3-1B-it + QLoRA", "gemma3_1b_base": "Gemma-3-1B-it, untuned (local)",
          "gemini_prompted": "gemini-3.5-flash, prompted"}
SUBSETS = {"primary_all_29": lambda r: True,
           "secondary_trained_27": lambda r: r["rule_id"] not in MEANING_DEPENDENT,
           "untrained_rule_HI-TE-006": lambda r: r["rule_id"] in MEANING_DEPENDENT}


class LocalHF:
    """A Hugging Face chat model behind the provider interface (`complete(messages, max_tokens)` -> Completion).
    Greedy decoding, so a run is deterministic on the same hardware."""

    base_url, hosted, reasoning_effort = "local", False, None

    def __init__(self, model_id: str, device: str = "auto"):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.torch = torch
        self.device = device if device != "auto" else ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = model_id
        self.tok = AutoTokenizer.from_pretrained(model_id)
        self.lm = AutoModelForCausalLM.from_pretrained(model_id, dtype=torch.float32).to(self.device).eval()

    def complete(self, messages, max_tokens: int = 120, **_) -> Completion:
        t0 = time.monotonic()
        try:
            enc = self.tok.apply_chat_template(messages, add_generation_prompt=True, return_tensors="pt",
                                               return_dict=True)
            enc = {k: v.to(self.device) for k, v in enc.items()}
            with self.torch.no_grad():
                out = self.lm.generate(**enc, max_new_tokens=max_tokens, do_sample=False,
                                       pad_token_id=self.tok.pad_token_id or self.tok.eos_token_id)
            n_in = enc["input_ids"].shape[1]
            text = self.tok.decode(out[0, n_in:], skip_special_tokens=True)
            return Completion(text, self.model, int((time.monotonic() - t0) * 1000), n_in, int(out.shape[1] - n_in))
        except Exception as e:  # noqa: BLE001 - logged and counted, like a provider error
            return Completion(None, self.model, int((time.monotonic() - t0) * 1000), error=f"{type(e).__name__}: {e}")


def rows_path(label: str) -> Path:
    return REPORTS / f"ft_eval_rows_{label}.jsonl"


def load_rows(label: str) -> list[dict]:
    p = rows_path(label)
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []


def score(rule: dict, it: dict, turn) -> dict:
    """One case's row, exactly as `generation_baselines.run` scores it."""
    d = turn.drafts[0]
    c = d.completion
    return {"item_id": it["item_id"], "rule_id": rule["rule_id"], "evaluable": bool(c.ok), "error": c.error,
            "raw": c.text, "sentence": d.sentence, "reasons": list(d.reasons), "valid": turn.source == "model",
            "planted": turn.source == "model" and turn.text == it["wrong_form"], "wrong_form": it["wrong_form"],
            "correct_form": it["correct_form"], "leak": "ANSWER_LEAK" in d.reasons, "oov": "OOV" in d.reasons,
            "latency_ms": c.latency_ms, "tokens": (c.prompt_tokens or 0) + (c.completion_tokens or 0)}


def run(provider, label: str, log=print) -> list[dict]:
    """Every frozen case once; resumable: cases with a model reply already in the row file are skipped."""
    done = {r["item_id"] for r in load_rows(label) if r["evaluable"]}
    rows_path(label).parent.mkdir(parents=True, exist_ok=True)
    for rule, it, ctx in cases():
        if it["item_id"] in done:
            continue
        turn = classmate.propose(provider, ctx, rule_title=rule.get("title_l1") or "", hindi_meaning=it["l1_meaning"],
                                 bank_sentence=it["wrong_form"], method=METHOD)
        row = score(rule, it, turn)
        if not row["evaluable"]:
            log(f"model call failed [{label} {it['item_id']}]: {row['error']}")
        with rows_path(label).open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return load_rows(label)


def latest(rows: list[dict]) -> dict:
    """item_id -> the last evaluable row (a retried case keeps its successful reply)."""
    out = {}
    for r in rows:
        if r["evaluable"] or r["item_id"] not in out:
            out[r["item_id"]] = r
    return out


def metrics(rows: list[dict]) -> dict:
    ev = [r for r in rows if r["evaluable"]]
    n = len(ev)
    out = {"cases": len(rows), "evaluable": n, "valid": wilson(sum(r["valid"] for r in ev), n),
           "planted_exact": wilson(sum(r["planted"] for r in ev), n),
           "leak": wilson(sum(r["leak"] for r in ev), n), "oov": wilson(sum(r["oov"] for r in ev), n)}
    if ev:
        out["median_latency_ms"] = statistics.median(r["latency_ms"] for r in ev)
        out["tokens_per_case"] = sum(r["tokens"] for r in ev) / n
    return out


def summarise(by_label: dict[str, list[dict]]) -> dict:
    conds = {lab: latest(rows) for lab, rows in by_label.items() if rows}
    res = {"conditions": {}, "comparisons": {}}
    for lab, latest_rows in conds.items():
        rows = list(latest_rows.values())
        res["conditions"][lab] = {"label": LABELS.get(lab, lab),
                                  "errors": sum(not r["evaluable"] for r in by_label[lab]),
                                  **{s: metrics([r for r in rows if f(r)]) for s, f in SUBSETS.items()}}
    labs = [x for x in CONDITION_ORDER if x in conds] + sorted(set(conds) - set(CONDITION_ORDER))
    for i, a in enumerate(labs):
        for b in labs[i + 1:]:
            common = sorted(k for k in conds[a] if k in conds[b] and conds[a][k]["evaluable"]
                            and conds[b][k]["evaluable"])
            comp = {}
            for s, f in SUBSETS.items():
                if s == "untrained_rule_HI-TE-006":  # 2 cases: no test
                    continue
                ks = [k for k in common if f(conds[a][k])]
                comp[s] = {"valid": mcnemar([conds[a][k]["valid"] for k in ks], [conds[b][k]["valid"] for k in ks])}
            res["comparisons"][f"{a} vs {b}"] = comp
    return res


def _fmt(w: dict) -> str:
    return "n/a" if w["rate"] is None else f"{w['k']}/{w['n']} = {w['rate']:.2f} [{w['lo']:.2f}, {w['hi']:.2f}]"


def qualitative(by_label: dict) -> list[dict]:
    """Up to 2 examples: one where a condition failed the filter, one where it passed (or a second failure)."""
    out = []
    for lab in CONDITION_ORDER:
        rows = list(latest(by_label.get(lab, [])).values())
        for want in (False, True):
            r = next((r for r in rows if r["evaluable"] and r["valid"] == want), None)
            if r and len(out) < 2:
                out.append({"condition": lab, "item_id": r["item_id"], "bank_wrong_form": r["wrong_form"],
                            "model_sentence": r["sentence"], "raw": (r["raw"] or "")[:200], "filter": r["reasons"]})
    return out


def markdown(rep: dict) -> str:
    lines = ["# Task 17: Raju generation on the 29 frozen planting cases", "",
             (f"Generated by `setu/research/ft_eval.py` from the row files `{', '.join(rep['row_files'])}`. "
              "Scored by the app's strict `leakfilter.check_sentence`. Rates have Wilson 95% intervals."), "",
             rep["tuned_status"], "",
             ("The prompt (task 6's `prompt_only`) includes the bank's wrong form as 'what Raju wrote last time', so "
              "passing the filter mostly means copying it exactly; 'Leak' means the model wrote the CORRECT form "
              "(the answer) instead."), ""]
    for s in SUBSETS:
        lines += [f"## {s}", "", "| Condition | Errors | Evaluable | Passed filter | Exact bank wrong form | Leak | OOV |",
                  "|---|---|---|---|---|---|---|"]
        for c in rep["conditions"].values():
            m = c[s]
            lines.append(f"| {c['label']} | {c['errors']} | {m['evaluable']}/{m['cases']} | {_fmt(m['valid'])} | "
                         f"{_fmt(m['planted_exact'])} | {_fmt(m['leak'])} | {_fmt(m['oov'])} |")
        lines.append("")
    if rep["comparisons"]:
        lines += ["## Paired comparisons (exact McNemar on 'passed filter')", "",
                  "| Comparison | Subset | Pairs | First only | Second only | p |", "|---|---|---|---|---|---|"]
        for name, subs in rep["comparisons"].items():
            for s, v in subs.items():
                m = v["valid"]
                lines.append(f"| {name} | {s} | {m['n_pairs']} | {m['x_only']} | {m['y_only']} | {m['p_exact']:.3f} |")
        lines.append("")
    lines += ["## Examples", ""]
    for q in rep["qualitative"]:
        lines.append(f"- **{q['condition']}**, {q['item_id']}: bank wrong form `{q['bank_wrong_form']}`, model "
                     f"`{q['model_sentence']}`, filter {q['filter'] or 'passed'}")
    lines += ["", ("29 cases is a small sample: intervals are wide, and a non-significant McNemar test is not evidence "
                   "of no difference.")]
    return "\n".join(lines) + "\n"


def report() -> dict:
    by_label = {lab: load_rows(lab) for lab in
                sorted({p.stem.removeprefix("ft_eval_rows_") for p in REPORTS.glob("ft_eval_rows_*.jsonl")})}
    rep = {"method": METHOD, "prompt": "classmate._prompt (planted turn), one draft, max_tokens=120",
           "preregistration": "docs/submission/drafts/ft_model_choice.md section 4",
           "tuned_status": "No tuned model: task 10 was a no-go on training data (reports/ft_data.json, go_no_go), "
                           "so the tuned condition was not trained or run.",
           "row_files": [str(rows_path(lab).relative_to(ROOT)) for lab in by_label],
           **summarise(by_label), "qualitative": qualitative(by_label)}
    (REPORTS / "ft_eval.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (REPORTS / "ft_eval.md").write_text(markdown(rep), encoding="utf-8")
    return rep


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", help="Hugging Face model id to run locally")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--gemini", action="store_true", help="the SETU_LLM_* endpoint from .env (throttled)")
    ap.add_argument("--label")
    args = ap.parse_args(argv)
    if args.local:
        run(LocalHF(args.local, args.device), args.label or "gemma3_1b_base")
    elif args.gemini:
        envfile.load(ROOT / ".env")
        p = OpenAICompatible.from_environment()
        if p is None:
            print("no model endpoint (SETU_LLM_URL unset)")
            return 1
        run(Throttled(p, float(os.environ.get("SETU_EVAL_INTERVAL", "6"))), args.label or "gemini_prompted")
    rep = report()
    for lab, c in rep["conditions"].items():
        print(lab, "valid", _fmt(c["primary_all_29"]["valid"]), "errors", c["errors"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
