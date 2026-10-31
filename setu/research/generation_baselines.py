"""Raju generation baselines (P-EVAL-04/05, P-MODEL; mid-submission sprint): prompt-only vs blind resampling vs
tool-assisted generation, on the same planting cases (every HI→TE bank item with a planted error), with a real
self-hosted model only. Without SETU_LLM_URL nothing is run and the report says so: no numbers are invented, and
the test mock is never used here.

    SETU_LLM_URL=http://localhost:1234/v1 SETU_LLM_MODEL=qwen/qwen3.5-9b python -m setu.research.generation_baselines

Per method: valid output rate (a proposal passed the filter), planting precision (the passed sentence is the planned
planted error), leakage (drafts that contained the answer), vocabulary violations (OOV drafts), fallback rate,
model calls, latency and tokens.
"""
import json
import statistics
from pathlib import Path

from setu.agents import classmate
from setu.agents.llm import OpenAICompatible
from setu.domain import leakfilter
from setu.domain.tokenize import tokens

from .stage_a import _items, item_key

OUT = Path(__file__).resolve().parents[2] / "reports/generation_baselines.json"


def cases():
    items = [(r, it) for r, it in _items() if r["direction"] == "HI->TE" and it.get("wrong_form")]
    for rule, it in items:
        key = item_key(rule, it, items)
        seen = frozenset(set(tokens(it["wrong_form"])) | set(tokens(it["correct_form"])))
        yield rule, it, leakfilter.Context(item=key, turn="planted", seen_words=seen)


def run(provider) -> dict:
    out = {}
    for method in classmate.METHODS:
        rows = []
        for rule, it, ctx in cases():
            t = classmate.propose(provider, ctx, rule_title=rule.get("title_l1") or "", hindi_meaning=it["l1_meaning"],
                                  bank_sentence=it["wrong_form"], method=method)
            reasons = [r for d in t.drafts for r in d.reasons]
            rows.append({"valid": t.source == "model", "planted": t.source == "model" and t.text == it["wrong_form"],
                         "leak": "ANSWER_LEAK" in reasons, "oov": "OOV" in reasons, "calls": len(t.drafts),
                         "latency": [d.completion.latency_ms for d in t.drafts],
                         "tokens": [(d.completion.prompt_tokens or 0) + (d.completion.completion_tokens or 0)
                                    for d in t.drafts]})
        n = len(rows)
        out[method] = {"n": n, "valid_rate": sum(r["valid"] for r in rows) / n,
                       "planting_precision": (sum(r["planted"] for r in rows) / max(1, sum(r["valid"] for r in rows))),
                       "leak_rate": sum(r["leak"] for r in rows) / n, "oov_rate": sum(r["oov"] for r in rows) / n,
                       "fallback_rate": 1 - sum(r["valid"] for r in rows) / n,
                       "calls_per_case": sum(r["calls"] for r in rows) / n,
                       "median_latency_ms": statistics.median([x for r in rows for x in r["latency"]]),
                       "tokens_per_case": sum(sum(r["tokens"]) for r in rows) / n}
    return out


def main() -> int:
    provider = OpenAICompatible.from_environment()
    if provider is None:
        report = {"status": "not_run", "reason": "no self-hosted model endpoint (SETU_LLM_URL unset)"}
    else:
        report = {"status": "run", "model": provider.model, "endpoint": provider.base_url, "methods": run(provider)}
    OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
