"""Controlled re-run of the Raju generation comparison (final audit, 15 Nov 2026). Research only: the app is unchanged.

Why. The task 6 / task 14 runs compared `prompt_only`, `tool` (harness feedback) and `agentic_tools` (model-chosen
tool calls) and found only the last one clearly better. Reading the code showed three things that comparison could
not separate:

1. Memory. `tool` re-sends the task plus the filter's reason codes, but NOT the model's own rejected draft, so the
   model cannot see what it wrote. `agentic_tools` keeps the whole conversation.
2. Who decides. In `agentic_tools` the model decides when to call the check; in `tool` the harness always runs it.
3. The exemplar. Every prompt contains the bank's wrong sentence ("राजू ने पिछली बार ऐसा लिखा था: ..."), and the leak
   filter accepts only that sentence (43 of 49 items have no wrong pattern). "Valid" therefore mostly means "copied
   the sentence it was shown".

Conditions (same 29 frozen planting cases, same model and settings, each case run REPEATS times):

| Name | Exemplar in prompt | Sees its own drafts | Who runs the check |
|---|---|---|---|
| prompt_only            | yes | -   | nobody (one draft)        |
| tool                   | yes | no  | harness (as shipped)      |
| tool_history  (NEW)    | yes | yes | harness                   |
| agentic_tools          | yes | yes | model                     |
| prompt_only_noex (NEW) | no  | -   | nobody                    |
| agentic_noex   (NEW)   | no  | yes | model                     |

`tool_history` is the deterministic alternative to tool calling: the harness checks every draft and returns the same
JSON result the tool would return, inside one growing conversation, with at most MAX_DRAFTS (3) drafts. That is the
same number of checked drafts `agentic_tools` can afford in its 6 model calls (check + final per draft).

Hypotheses, written before the run (15 Nov 2026):
- H-A1 (memory, not choice): `tool_history` valid rate is higher than `tool`.
- H-A2 (choice adds nothing): `agentic_tools` is NOT higher than `tool_history`. We can only fail to reject this at
  n = 29; a non-significant difference is not evidence of equivalence, so the paired counts are reported.
- H-A3 (exemplar dependence): without the exemplar the strict valid rate falls sharply for both `prompt_only` and
  `agentic_tools`.
Primary analysis: repeat 1, exact McNemar on the paired cases. Secondary: all repeats pooled, with a bootstrap
interval that resamples cases (repeats of one case are not independent).

This is a post-hoc ablation: it was designed after seeing the task 6 and task 14 results, on the same frozen cases.
The cases were not changed and no prompt was tuned on them, but a confirmation needs new cases.

    set -a; source .env; set +a; python -m setu.research.generation_ablation            # run / resume
    python -m setu.research.generation_ablation --report-only                            # rebuild the report

Rows are appended to `reports/generation_ablation_rows.jsonl` as each case finishes; a rerun only fills in what is
missing. A case with no model reply is an error row, never a result.
"""
import argparse
import json
import os
import random
import re
import statistics
from pathlib import Path

from setu.agents import classmate
from setu.agents.llm import OpenAICompatible, parse_json
from setu.domain import leakfilter
from setu.domain.normalise import canonical
from setu.domain.tokenize import tokens

from . import envfile
from .generation_baselines import Throttled, cases
from .stats import mcnemar, wilson

ROOT = Path(__file__).resolve().parents[2]
ROWS = ROOT / "reports/generation_ablation_rows.jsonl"
OUT_JSON = ROOT / "reports/generation_ablation.json"
OUT_MD = ROOT / "reports/generation_ablation.md"
CONDITIONS = ("prompt_only", "tool", "tool_history", "agentic_tools", "prompt_only_noex", "agentic_noex")
REPEATS = 3
MAX_DRAFTS = classmate.MAX_DRAFTS
_EXEMPLAR = re.compile(r" राजू ने पिछली बार ऐसा लिखा था: [^\n]*")
PAIRS = (("tool_history", "tool", "H-A1 memory"), ("agentic_tools", "tool_history", "H-A2 model choice"),
         ("agentic_tools", "tool", "replication of task 14"), ("agentic_tools", "prompt_only", "replication of task 6"),
         ("prompt_only", "prompt_only_noex", "H-A3 exemplar, one draft"),
         ("agentic_tools", "agentic_noex", "H-A3 exemplar, agentic"))


class NoExemplar:
    """Removes the bank's wrong sentence from the task before it reaches the model (H-A3)."""

    def __init__(self, provider):
        self.provider = provider

    def complete(self, messages, **kw):
        msgs = [dict(m, content=_EXEMPLAR.sub("", m["content"])) if m["role"] == "user" else m for m in messages]
        return self.provider.complete(msgs, **kw)


def propose_with_history(provider, ctx: leakfilter.Context, *, rule_title: str, hindi_meaning: str,
                         bank_sentence: str) -> classmate.RajuTurn:
    """Harness-run check with memory: every draft and the check's JSON result stay in the conversation."""
    msgs = classmate._prompt(ctx, rule_title, hindi_meaning)
    drafts = []
    for _ in range(MAX_DRAFTS):
        c = provider.complete(list(msgs), max_tokens=120)
        obj = parse_json(c.text, ("sentence",)) if c.ok else None
        sentence = obj["sentence"] if obj and isinstance(obj["sentence"], str) else None
        reasons = tuple(leakfilter.check_sentence(sentence, ctx)) if sentence else ("NO_SENTENCE",)
        drafts.append(classmate.Draft(sentence, reasons, c))
        if not reasons:
            return classmate.RajuTurn(sentence, "model", tuple(drafts), "tool_history")
        if c.ok:
            msgs.append({"role": "assistant", "content": c.text})
            msgs.append({"role": "user", "content": "TOOL RESULT: " + json.dumps(
                {"ok": False, "reasons": list(reasons)}, ensure_ascii=False) + "\nफिर से सिर्फ़ JSON में लिखो।"})
    return classmate.RajuTurn(bank_sentence, "bank", tuple(drafts), "tool_history")


def run_condition(provider, condition: str, rule, it, ctx) -> classmate.RajuTurn:
    kw = {"rule_title": rule.get("title_l1") or "", "hindi_meaning": it["l1_meaning"], "bank_sentence": it["wrong_form"]}
    if condition == "tool_history":
        return propose_with_history(provider, ctx, **kw)
    if condition.endswith("_noex"):
        provider = NoExemplar(provider)
    method = {"prompt_only_noex": "prompt_only", "agentic_noex": "agentic_tools"}.get(condition, condition)
    return classmate.propose(provider, ctx, method=method, **kw)


def describe(sentence: str | None, it: dict) -> str:
    """What a draft is, by string comparison only (no judgement of grammar): the bank's wrong sentence, the correct
    sentence (a leak), a different sentence that still has a word found only in the wrong sentence, or other."""
    if not sentence:
        return "none"
    s = canonical(sentence)
    if s == canonical(it["wrong_form"]):
        return "bank_wrong_form"
    if s == canonical(it["correct_form"]):
        return "correct_form"
    planted_only = set(tokens(it["wrong_form"])) - set(tokens(it["correct_form"]))
    return "other_with_planted_word" if planted_only & set(tokens(sentence)) else "other"


def row(condition: str, repeat: int, it: dict, t: classmate.RajuTurn) -> dict:
    ok = [d for d in t.drafts if d.completion.ok]
    sentences = [d.sentence for d in t.drafts if d.sentence]
    reasons = [r for d in t.drafts for r in d.reasons]
    return {"condition": condition, "repeat": repeat, "item_id": it["item_id"], "evaluable": bool(ok),
            "valid": t.source == "model", "leak": "ANSWER_LEAK" in reasons, "oov": "OOV" in reasons,
            "calls": len(t.drafts), "provider_errors": len(t.drafts) - len(ok),
            "tokens": sum((d.completion.prompt_tokens or 0) + (d.completion.completion_tokens or 0) for d in t.drafts),
            "latency_ms": [d.completion.latency_ms for d in t.drafts],
            "first_draft": sentences[0] if sentences else None, "first_draft_kind": describe(sentences[0] if sentences
                                                                                             else None, it),
            "same_draft_repeated": len(sentences) > 1 and len(set(map(canonical, sentences))) == 1,
            "drafts": sentences, "reasons": reasons, "shown": t.text, "model": ok[0].completion.model if ok else None}


def load_rows(path: Path = ROWS) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def collect(provider, *, repeats: int = REPEATS, conditions=CONDITIONS, path: Path = ROWS, limit: int | None = None):
    """Run every missing (condition, repeat, case). Error rows are retried on the next run."""
    done = {(r["condition"], r["repeat"], r["item_id"]) for r in load_rows(path) if r["evaluable"]}
    kept = [r for r in load_rows(path) if r["evaluable"]]
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept), encoding="utf-8")
    todo = list(cases())[:limit]
    with path.open("a", encoding="utf-8") as f:
        for repeat in range(1, repeats + 1):
            for condition in conditions:
                for rule, it, ctx in todo:
                    if (condition, repeat, it["item_id"]) in done:
                        continue
                    r = row(condition, repeat, it, run_condition(provider, condition, rule, it, ctx))
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
                    f.flush()


def _boot(by_case: dict, fn, n: int = 5000, seed: int = 20261115) -> list[float]:
    """Percentile bootstrap that resamples cases (clusters), keeping each case's repeats together."""
    rng, ids = random.Random(seed), sorted(by_case)
    vals = sorted(fn([by_case[rng.choice(ids)] for _ in ids]) for _ in range(n))
    return [vals[int(0.025 * n)], vals[int(0.975 * n) - 1]]


def summarise(rows: list[dict]) -> dict:
    rows = [r for r in rows if r["evaluable"]]
    out = {"conditions": {}, "paired": []}
    for cond in CONDITIONS:
        rs = [r for r in rows if r["condition"] == cond]
        if not rs:
            continue
        r1 = [r for r in rs if r["repeat"] == 1]
        by_case: dict = {}
        for r in rs:
            by_case.setdefault(r["item_id"], []).append(r)

        def rate(groups):
            flat = [r["valid"] for g in groups for r in g]
            return sum(flat) / len(flat)

        per_repeat = {str(k): sum(r["valid"] for r in rs if r["repeat"] == k) / max(1, sum(r["repeat"] == k for r in rs))
                      for k in sorted({r["repeat"] for r in rs})}
        kinds = {k: sum(r["first_draft_kind"] == k for r in rs) for k in
                 ("bank_wrong_form", "correct_form", "other_with_planted_word", "other", "none")}
        multi = [r for r in rs if r["calls"] > 1]
        out["conditions"][cond] = {
            "rows": len(rs), "cases": len(by_case), "repeats": len(per_repeat),
            "repeat1_valid": wilson(sum(r["valid"] for r in r1), len(r1)),
            "pooled_valid_rate": rate(by_case.values()), "pooled_valid_ci95_case_bootstrap": _boot(by_case, rate),
            "valid_rate_by_repeat": per_repeat,
            "cases_valid_in_every_repeat": sum(all(r["valid"] for r in g) for g in by_case.values()),
            "cases_valid_in_no_repeat": sum(not any(r["valid"] for r in g) for g in by_case.values()),
            "leak_rate": sum(r["leak"] for r in rs) / len(rs), "oov_rate": sum(r["oov"] for r in rs) / len(rs),
            "first_draft_kinds": kinds,
            "same_draft_repeated_share_of_retried": (sum(r["same_draft_repeated"] for r in multi) / len(multi)
                                                     if multi else None),
            "calls_per_case": statistics.mean(r["calls"] for r in rs),
            "tokens_per_case": statistics.mean(r["tokens"] for r in rs),
            "median_latency_ms": statistics.median(x for r in rs for x in r["latency_ms"]),
            "total_calls": sum(r["calls"] for r in rs), "total_tokens": sum(r["tokens"] for r in rs)}
    for x, y, label in PAIRS:
        for scope in ("repeat1", "all_repeats"):
            a = {(r["item_id"], r["repeat"]): r["valid"] for r in rows if r["condition"] == x}
            b = {(r["item_id"], r["repeat"]): r["valid"] for r in rows if r["condition"] == y}
            keys = sorted(k for k in a if k in b and (scope == "all_repeats" or k[1] == 1))
            if not keys:
                continue
            m = mcnemar([a[k] for k in keys], [b[k] for k in keys])
            entry = {"x": x, "y": y, "label": label, "scope": scope, **m,
                     "difference": sum(a[k] for k in keys) / len(keys) - sum(b[k] for k in keys) / len(keys)}
            if scope == "all_repeats":  # repeats of a case are dependent: no p-value, a case-bootstrap interval instead
                entry["p_exact"] = None
                by_case = {}
                for k in keys:
                    by_case.setdefault(k[0], []).append((a[k], b[k]))
                entry["difference_ci95_case_bootstrap"] = _boot(
                    by_case, lambda gs: statistics.mean(p - q for g in gs for p, q in g))
            out["paired"].append(entry)
    out["total_calls"] = sum(c["total_calls"] for c in out["conditions"].values())
    out["total_tokens"] = sum(c["total_tokens"] for c in out["conditions"].values())
    return out


def _f(x, nd=2):
    return "–" if x is None else f"{x:.{nd}f}"


def markdown(report: dict) -> str:
    s = report["summary"]
    lines = ["# Raju generation: controlled ablation (memory, model choice, exemplar)", "",
             (f"Model `{report.get('model')}`, reasoning effort `{report.get('reasoning_effort')}`, temperature 0.4 "
              f"(the agents' default). Status: {report['status']}. Generated by "
              "`setu/research/generation_ablation.py` from `reports/generation_ablation_rows.jsonl`; do not edit by "
              "hand."), "",
             ("Post-hoc ablation on the 29 frozen planting cases (designed after the task 6 and task 14 results; the "
              "cases and prompts were not changed). 'Valid' = the model's sentence passed the app's leak filter, which "
              "for 27 of these 29 cases means it equals the bank's wrong sentence exactly."), "",
             "## Valid rate", "",
             ("| Condition | Exemplar | Own drafts visible | Check run by | Repeat 1 (Wilson 95%) | All repeats "
              "(case-bootstrap 95%) | By repeat | Valid in every / no repeat | Calls/case | Tokens/case |"),
             "|---|---|---|---|---|---|---|---|---|---|"]
    meta = {"prompt_only": ("yes", "–", "nobody"), "tool": ("yes", "no", "harness"),
            "tool_history": ("yes", "yes", "harness"), "agentic_tools": ("yes", "yes", "model"),
            "prompt_only_noex": ("no", "–", "nobody"), "agentic_noex": ("no", "yes", "model")}
    for cond, c in s["conditions"].items():
        w, ci = c["repeat1_valid"], c["pooled_valid_ci95_case_bootstrap"]
        lines.append(f"| `{cond}` | {' | '.join(meta[cond])} | {_f(w['rate'])} [{_f(w['lo'])}, {_f(w['hi'])}] "
                     f"({w['k']}/{w['n']}) | {_f(c['pooled_valid_rate'])} [{_f(ci[0])}, {_f(ci[1])}] | "
                     f"{', '.join(_f(v) for v in c['valid_rate_by_repeat'].values())} | "
                     f"{c['cases_valid_in_every_repeat']} / {c['cases_valid_in_no_repeat']} of {c['cases']} | "
                     f"{_f(c['calls_per_case'])} | {c['tokens_per_case']:.0f} |")
    lines += ["", "## Paired comparisons (same cases)", "",
              "| x vs y | Question | Scope | Pairs | x only | y only | Difference (x − y) | Exact McNemar p |",
              "|---|---|---|---|---|---|---|---|"]
    for p in s["paired"]:
        ci = p.get("difference_ci95_case_bootstrap")
        diff = f"{p['difference']:+.2f}" + (f" [{ci[0]:+.2f}, {ci[1]:+.2f}]" if ci else "")
        lines.append(f"| `{p['x']}` vs `{p['y']}` | {p['label']} | {p['scope']} | {p['n_pairs']} | {p['x_only']} | "
                     f"{p['y_only']} | {diff} | {_f(p['p_exact'], 3) if p['p_exact'] is not None else 'n/a (dependent)'} |")
    lines += ["", ("Repeat 1 is the primary analysis. Pooled rows count every repeat; repeats of one case are not "
                   "independent, so they get a bootstrap interval over cases instead of a p-value. A non-significant "
                   "difference is not evidence that two methods are equal."), "",
              "## What the first draft was (string comparison only, all repeats)", "",
              ("| Condition | Bank's wrong sentence | Correct sentence (leak) | Other, with a wrong-only word | Other "
               "| No sentence | Retried cases that repeated one draft |"), "|---|---|---|---|---|---|---|"]
    for cond, c in s["conditions"].items():
        k = c["first_draft_kinds"]
        lines.append(f"| `{cond}` | {k['bank_wrong_form']} | {k['correct_form']} | {k['other_with_planted_word']} | "
                     f"{k['other']} | {k['none']} | {_f(c['same_draft_repeated_share_of_retried'])} |")
    lines += ["", ("'Other, with a wrong-only word' are sentences that differ from the bank's wrong sentence but "
                   "contain a word that appears only in it (for example the Hindi negator). The filter rejects them "
                   "because it cannot verify a paraphrase. Whether they are acceptable planted errors is NOT judged "
                   "here: that needs a native speaker."), "",
              "## Compute", "", (f"{s['total_calls']} model calls, {s['total_tokens']:,} tokens in the rows on disk. "
                                 "Provider errors in the last run: "
                                 f"{report.get('provider_calls', {}).get('errors', {}) or 'none'}."), ""]
    return "\n".join(lines)


def build_report(extra: dict | None = None) -> dict:
    rows = load_rows()
    models = sorted({r["model"] for r in rows if r.get("model")})
    report = {"status": "run" if rows else "not_run", "model": models[0] if len(models) == 1 else models,
              "repeats_planned": REPEATS, "cases": sum(1 for _ in cases()), "hypotheses_written_before_run": "2026-11-15",
              "post_hoc": True, **(extra or {}), "summary": summarise(rows)}
    OUT_JSON.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    OUT_MD.write_text(markdown(report), encoding="utf-8")
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--repeats", type=int, default=REPEATS)
    ap.add_argument("--limit", type=int, default=None, help="first N cases only (smoke test)")
    args = ap.parse_args(argv)
    extra = {}
    if not args.report_only:
        envfile.load(ROOT / ".env")
        provider = OpenAICompatible.from_environment()
        if provider is None:
            print("no model endpoint (SETU_LLM_URL unset): nothing run")
        else:
            provider = Throttled(provider, float(os.environ.get("SETU_EVAL_INTERVAL", "6")))
            try:
                collect(provider, repeats=args.repeats, limit=args.limit)
            finally:
                extra = {"reasoning_effort": provider.reasoning_effort,
                         "provider_calls": {"sent": provider.sent, "ok": provider.ok, "errors": dict(provider.errors)}}
    elif OUT_JSON.is_file():
        old = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        extra = {k: old[k] for k in ("reasoning_effort", "provider_calls") if k in old}
    report = build_report(extra)
    print(json.dumps({k: v for k, v in report.items() if k != "summary"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
