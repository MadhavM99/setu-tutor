"""RAG evaluation for the coach (TASKS.md task 16), on the frozen planting cases.

    .venv/bin/python -m setu.research.rag_eval --tag dev          # LM Studio (SETU_LLM_URL=http://localhost:1234/v1)
    .venv/bin/python -m setu.research.rag_eval                    # final run (gemini-3.5-flash, from .env)
    .venv/bin/python -m setu.research.rag_eval --retrieval-only   # deterministic part only, no model

Cases (read, never edited):
- positives: the 29 frozen planting cases (`generation_baselines.cases()`, asserted equal to tests/eval_sets by
  test_eval_sets). Raju's sentence = wrong_form; the learner's wrong attempt = wrong_form submitted unchanged (the miss
  that triggers a hint). Retrieval is leave-item-out: the case's own example is not in the index.
- negatives (no hint should cite a rule): the 29 correct_forms presented as Raju's sentence, and the 11
  `learner_message` attacks from tests/eval_sets/attacks.jsonl, used as the only text the coach sees.

Conditions: a blind (no rule, no retrieval) · a' shipped coach given the planted rule title ("oracle title") ·
b RAG · c oracle retrieval · d RAG explanations only · e RAG threshold off. Negatives run for a, a', b, e.

A case counts only if the model replied (or RAG abstained, which needs no reply). Provider errors are logged by type
and excluded, never counted as results. Every rate has a Wilson 95% interval; paired comparisons use exact McNemar.
Outputs: reports/rag_eval{_tag}.json, .md and _rows.jsonl.
"""
import argparse
import json
import os
import statistics
from collections import Counter
from pathlib import Path

from setu.agents import coach, retrieval
from setu.agents.llm import OpenAICompatible

from . import envfile
from .generation_baselines import Throttled, cases
from .stage_a import _items, item_key
from .stats import mcnemar, wilson

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports"
ATTACKS = ROOT / "tests/eval_sets/attacks.jsonl"
SWEEP = (0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5)
CONDITIONS = {  # name: (coach mode or "shipped", with_examples, use threshold, run on negatives)
    "a_blind": ("blind", True, False, True),
    "a_prime_oracle_title": ("shipped", True, False, True),
    "b_rag": ("rag", True, True, True),
    "c_oracle_retrieval": ("oracle", True, False, False),
    "d_rag_explanations_only": ("rag", False, True, False),
    "e_rag_no_threshold": ("rag", True, False, True),
    # post-hoc (designed after seeing the run): (b) with the fixed prompt and the NUMBERED_SOURCE check, positives only
    "b_fixed_posthoc": ("rag", True, True, False),
}
POSTHOC = {"b_fixed_posthoc"}
MEASURES = {  # one name and one definition per measure; the markdown, results draft, slides and HANDOFF use these names
    "hint_shown": ("hint shown", "a model hint passed every filter and was shown (else the generic hint)"),
    "shown_and_usable": ("shown and usable", ("shown, and no reference to the coach's numbered sources "
                                              "(coach.NUMBERED_SOURCE); defined after seeing the run (post-hoc)")),
    "top1_retrieved_is_planted": ("top-1 retrieved = planted", ("the first rule given to the model is the planted "
                                                                "rule (retrieval only; oracle: always)")),
    "citation_faithful": ("model cites planted", ("the rule the model names in its `source` field is the planted "
                                                  "rule, whether or not the hint was shown")),
    "faithful_hint_shown": ("shown hint cites planted", "hint shown AND the model's `source` is the planted rule"),
}
NOTE = ("The title-given coach (a') works only for Raju's planted mistakes, where the planted rule is known. For the "
        "learner's own sentences there is no planted rule; that is the case retrieval is for.")


# ---------------------------------------------------------------- cases

def positives():
    for rule, it, ctx in cases():
        yield {"case_id": f"pos:{it['item_id']}", "kind": "planted", "item": ctx.item, "item_id": it["item_id"],
               "rule_id": rule["rule_id"], "rule_title": rule.get("title_l1") or "",
               "raju": it["wrong_form"], "attempt": it["wrong_form"]}


def negatives():
    for rule, it, ctx in cases():
        yield {"case_id": f"neg:correct:{it['item_id']}", "kind": "correct_sentence", "item": ctx.item,
               "item_id": it["item_id"], "rule_id": None, "rule_title": rule.get("title_l1") or "",
               "raju": it["correct_form"], "attempt": it["correct_form"]}
    items = [(r, i) for r, i in _items()]
    by_id = {i["item_id"]: (r, i) for r, i in items}
    for line in ATTACKS.read_text(encoding="utf-8").splitlines():
        a = json.loads(line) if line.strip() else None
        if not a or a["surface"] != "learner_message":
            continue
        rule, it = by_id[a["item_id"]]
        yield {"case_id": f"neg:attack:{a['id']}", "kind": "attack", "item": item_key(rule, it, items),
               "item_id": it["item_id"], "rule_id": None, "rule_title": rule.get("title_l1") or "",
               "raju": a["input"], "attempt": a["input"]}


# ---------------------------------------------------------------- retrieval only (deterministic, no model)

def retrieval_report(docs) -> dict:
    pos, neg = list(positives()), list(negatives())
    indexes = {"all_25": docs, "hi_te_15": tuple(d for d in docs if d.direction == "HI->TE")}
    out = {"indexes": {}, "sweep": [], "misses": []}
    per_case = {}  # all_25 with examples: hit@1 per case, paired with the oracle below
    for name, ds in indexes.items():
        for with_ex in (True, False):
            h1 = h3 = 0
            for c in pos:
                hits = retrieval.Retriever(ds, with_examples=with_ex, exclude_items={c["item_id"]}).search(
                    retrieval.build_query(c["raju"], c["attempt"]))
                h1 += bool(hits) and hits[0].rule_id == c["rule_id"]
                if name == "all_25" and with_ex:
                    per_case[c["case_id"]] = bool(hits) and hits[0].rule_id == c["rule_id"]
                h3 += any(h.rule_id == c["rule_id"] for h in hits)
                if name == "all_25" and with_ex and (not hits or hits[0].rule_id != c["rule_id"]):
                    out["misses"].append({"case_id": c["case_id"], "planted": c["rule_id"], "query": c["raju"],
                                          "top3": [[h.rule_id, round(h.score, 3)] for h in hits]})
            out["indexes"][f"{name}{'' if with_ex else '_explanations_only'}"] = {
                "hit@1": wilson(h1, len(pos)), "hit@3": wilson(h3, len(pos))}
    oracle = {c["case_id"]: retrieval.oracle_hits(docs, c["rule_id"])[0].rule_id == c["rule_id"] for c in pos}
    out["indexes"]["oracle_upper_bound"] = {"hit@1": wilson(sum(oracle.values()), len(pos)),
                                            "hit@3": wilson(sum(oracle.values()), len(pos))}
    ids = sorted(per_case)
    out["rag_vs_oracle_hit@1"] = mcnemar([per_case[i] for i in ids], [oracle[i] for i in ids])
    top = {}
    for c in pos + neg:
        hits = retrieval.Retriever(docs, exclude_items={c["item_id"]}).search(
            retrieval.build_query(c["raju"], c["attempt"]))
        top[c["case_id"]] = (c["kind"], hits[0].score if hits else 0.0)
    out["top_score"] = {kind: {"min": round(min(sc), 3), "median": round(statistics.median(sc), 3),
                               "max": round(max(sc), 3)}
                        for kind in ("planted", "correct_sentence", "attack")
                        for sc in [[s for k, s in top.values() if k == kind]]}
    for t in SWEEP:
        row = {"threshold": t}
        for kind in ("planted", "correct_sentence", "attack"):
            scores = [s for k, s in top.values() if k == kind]
            row[f"abstain_{kind}"] = wilson(sum(s < t for s in scores), len(scores))
        out["sweep"].append(row)
    return out


# ---------------------------------------------------------------- model conditions

def _one(provider, cond: str, c: dict, docs, threshold: float) -> dict:
    mode, with_ex, use_thr, _ = CONDITIONS[cond]
    approved = ("generic", None)
    if mode == "shipped":
        h = coach.hint(provider, c["item"], rule_title=c["rule_title"], approved=approved, wrong_sentence=c["raju"])
    else:
        r = retrieval.Retriever(docs, with_examples=with_ex, exclude_items={c["item_id"]})
        h = coach.hint_with_mode(provider, c["item"], mode=mode, raju_sentence=c["raju"], learner_attempt=c["attempt"],
                                 approved=approved, retriever=r,
                                 oracle_rule_id=c["rule_id"] if mode == "oracle" else None,
                                 threshold=threshold if use_thr else None, fixed=cond in POSTHOC)
    comp = h.completion
    return {"condition": cond, "case_id": c["case_id"], "kind": c["kind"], "planted": c["rule_id"],
            "evaluable": h.abstained or bool(comp and comp.ok), "provider_error": comp.error if comp else None,
            "shown": h.source == "model", "text": h.text if h.source == "model" else None,
            "rejected": list(h.rejected), "rejected_text": (comp.text if comp and h.source != "model" else None),
            "abstained": h.abstained, "cited": h.cited_rule_id,
            "retrieved": [[x.rule_id, x.score if x.score != float("inf") else None] for x in h.retrieved],
            "latency_ms": comp.latency_ms if comp else 0,
            "tokens": ((comp.prompt_tokens or 0) + (comp.completion_tokens or 0)) if comp else 0,
            "called": comp is not None}


def _numbered(r: dict) -> bool:
    """A shown hint that refers to the coach's numbered sources ("नियम 3"), which the learner never sees."""
    return bool(r["shown"] and r["text"] and coach.NUMBERED_SOURCE.search(r["text"]))


def _usable(r: dict) -> bool:
    return bool(r["shown"]) and not _numbered(r)


def summarise(rows: list[dict], cond: str) -> dict:
    mode = CONDITIONS[cond][0]
    out = {}
    for kind_group, kinds in (("positives", {"planted"}), ("negatives", {"correct_sentence", "attack"})):
        allr = [r for r in rows if r["condition"] == cond and r["kind"] in kinds]
        if not allr:
            continue
        ev = [r for r in allr if r["evaluable"]]
        n = len(ev)
        s = {"cases": len(allr), "evaluable": n, "provider_errors": sum(1 for r in allr if r["provider_error"])}
        if kind_group == "positives":
            s["hint_shown"] = wilson(sum(r["shown"] for r in ev), n)
            s["shown_with_numbered_source"] = {"k": sum(_numbered(r) for r in ev), "of_shown": sum(r["shown"] for r in ev)}
            s["shown_and_usable"] = wilson(sum(_usable(r) for r in ev), n)
            s["answer_leak"] = wilson(sum("ANSWER_FORM" in r["rejected"] for r in ev), n)
            s["telugu_in_hint"] = wilson(sum("TELUGU_IN_HINT" in r["rejected"] for r in ev), n)
            s["false_abstention"] = wilson(sum(r["abstained"] for r in ev), n)
            if mode in ("rag", "oracle"):
                cited = [r for r in ev if r["cited"]]
                s["top1_retrieved_is_planted"] = wilson(
                    sum(bool(r["retrieved"]) and r["retrieved"][0][0] == r["planted"] for r in ev), n)
                s["citation_faithful"] = wilson(sum(r["cited"] == r["planted"] for r in cited), len(cited))
                s["faithful_hint_shown"] = wilson(sum(r["shown"] and r["cited"] == r["planted"] for r in ev), n)
        else:
            s["correct_abstention"] = wilson(sum(r["abstained"] for r in ev), n)
            s["no_rule_hint_shown"] = wilson(sum(not r["shown"] for r in ev), n)
            for k in ("correct_sentence", "attack"):
                sub = [r for r in ev if r["kind"] == k]
                s[f"correct_abstention_{k}"] = wilson(sum(r["abstained"] for r in sub), len(sub))
        out[kind_group] = s
    called = [r for r in rows if r["condition"] == cond and r["called"]]
    ok = [r for r in called if not r["provider_error"]]
    out["compute"] = {"model_calls": len(called), "ok_calls": len(ok), "tokens": sum(r["tokens"] for r in called),
                      "median_latency_ms": statistics.median(r["latency_ms"] for r in ok) if ok else None}
    return out


def _paired(rows, x: str, y: str, field: str) -> dict:
    """Exact McNemar on positives evaluable under both conditions."""
    def get(cond):
        return {r["case_id"]: r for r in rows if r["condition"] == cond and r["kind"] == "planted" and r["evaluable"]}
    a, b = get(x), get(y)
    ids = sorted(set(a) & set(b))

    def ok(r):
        if field in ("usable", "shown_and_usable"):
            return _usable(r)
        return r["shown"] and (r["cited"] == r["planted"]) if field == "faithful_hint_shown" else r["shown"]
    return {"x": x, "y": y, "outcome": field, **mcnemar([ok(a[i]) for i in ids], [ok(b[i]) for i in ids])}


COMPARISONS = (("b_rag", "a_blind", "hint_shown"), ("b_rag", "a_blind", "shown_and_usable"), ("b_rag", "a_prime_oracle_title", "hint_shown"),
               ("b_rag", "c_oracle_retrieval", "faithful_hint_shown"),
               ("d_rag_explanations_only", "b_rag", "faithful_hint_shown"),
               ("e_rag_no_threshold", "b_rag", "faithful_hint_shown"),
               ("b_fixed_posthoc", "b_rag", "shown_and_usable"), ("b_fixed_posthoc", "a_blind", "shown_and_usable"),
               ("b_fixed_posthoc", "a_blind", "hint_shown"))


def qualitative(rows, retr) -> dict:
    out = {"retrieval_miss": retr["misses"][0] if retr["misses"] else None, "blocked_hint": None}
    for reason in ("ANSWER_FORM", "TELUGU_IN_HINT", "NOT_HINDI", "LATIN"):
        r = next((r for r in rows if reason in r["rejected"] and r["rejected_text"]), None)
        if r:
            out["blocked_hint"] = {"reason": reason, "case_id": r["case_id"], "condition": r["condition"],
                                   "model_reply": r["rejected_text"], "all_reasons": r["rejected"]}
            break
    return out


PRIORITY = ("a_blind", "b_rag", "c_oracle_retrieval", "a_prime_oracle_title", "d_rag_explanations_only",
            "e_rag_no_threshold")  # run order for the final run: a partial run still has the main comparison


def run_models(provider, docs, threshold: float, conditions=PRIORITY, log=print, done=frozenset(), on_row=None,
               on_condition=None, limit: int | None = None) -> list[dict]:
    """Every case of every condition, in order. `done` = (condition, case_id) already answered (resume): skipped.
    `on_row(row)` after each case (append to disk); `on_condition(cond)` after each condition (rewrite the report).
    `limit`: only the first `limit` planted cases per condition and no negatives (small quota: the same cases under
    every condition, so they can still be paired)."""
    pos, neg = list(positives()), list(negatives())
    if limit is not None:
        pos, neg = pos[:limit], []
    rows = []
    for cond in conditions:
        for c in pos + (neg if CONDITIONS[cond][3] else []):
            if (cond, c["case_id"]) in done:
                continue
            r = _one(provider, cond, c, docs, threshold)
            if r["provider_error"]:
                log(f"provider error [{cond} {c['case_id']}]: {r['provider_error']}")
            rows.append(r)
            if on_row:
                on_row(r)
        if on_condition:
            on_condition(cond)
    return rows


def latest_rows(rows: list[dict]) -> list[dict]:
    """One row per (condition, case): the evaluable one if a retry succeeded, else the last attempt."""
    out = {}
    for r in rows:
        k = (r["condition"], r["case_id"])
        if r["evaluable"] or k not in out or not out[k]["evaluable"]:
            out[k] = r
    return list(out.values())


# ---------------------------------------------------------------- report

def _fmt(w: dict | None) -> str:
    if not w or w.get("rate") is None:
        return "–"
    return f"{w['rate']:.2f} [{w['lo']:.2f}, {w['hi']:.2f}] ({w['k']}/{w['n']})"


def markdown(rep: dict) -> str:
    L = [f"# Coach RAG evaluation{(' (' + rep['tag'] + ')') if rep.get('tag') else ''}", "",
         (f"Model: `{rep.get('model', '–')}` · threshold: {rep['threshold']} · status: {rep['status']}"
          f"{' · ' + rep['limit'] if rep.get('limit') else ''}. "
         "Rates with Wilson 95% intervals (k/n). Generated by `setu/research/rag_eval.py`; do not edit by hand."), "",
         "## Retrieval (deterministic, positives n=29, leave-item-out)", "",
         "| Index | hit@1 | hit@3 |", "|---|---|---|"]
    for name, v in rep["retrieval"]["indexes"].items():
        L.append(f"| {name} | {_fmt(v['hit@1'])} | {_fmt(v['hit@3'])} |")
    if "rag_vs_oracle_hit@1" in rep["retrieval"]:
        m = rep["retrieval"]["rag_vs_oracle_hit@1"]
        L += ["", (f"RAG (all_25) vs oracle, hit@1, exact McNemar: oracle right where RAG missed on {m['y_only']} "
                   f"cases, the reverse on {m['x_only']}; p = {m['p_exact']:.4f}. The oracle is right by construction: "
                   "the gap is what retrieval costs.")]
    L += ["", "## Abstention threshold sweep (share abstained)", "",
          "| Threshold | planted (should be 0) | correct sentence (should be 1) | attack (should be 1) |",
          "|---|---|---|---|"]
    for r in rep["retrieval"]["sweep"]:
        L.append(f"| {r['threshold']} | {_fmt(r['abstain_planted'])} | {_fmt(r['abstain_correct_sentence'])} | "
                 f"{_fmt(r['abstain_attack'])} |")
    if rep.get("conditions"):
        L += ["", "## Hints on the planted cases (positives)", "",
              ("| Condition | evaluable | hint shown | shown and usable | shown hints citing a numbered source | "
               "answer leak | Telugu in hint | top-1 retrieved = planted | model cites planted | "
               "shown hint cites planted | false abstention |"),
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for name, s in rep["conditions"].items():
            p = s.get("positives", {})
            name = name + (" (reduced-n)" if s.get("reduced_n") else "") + (" **(post-hoc)**" if name in POSTHOC else "")
            ns = p.get("shown_with_numbered_source") or {"k": 0, "of_shown": 0}
            L.append(f"| {name} | {p.get('evaluable', 0)}/{p.get('cases', 0)} | {_fmt(p.get('hint_shown'))} | "
                     f"{_fmt(p.get('shown_and_usable'))} | {ns['k']} of {ns['of_shown']} | "
                     f"{_fmt(p.get('answer_leak'))} | {_fmt(p.get('telugu_in_hint'))} | "
                     f"{_fmt(p.get('top1_retrieved_is_planted'))} | {_fmt(p.get('citation_faithful'))} | {_fmt(p.get('faithful_hint_shown'))} | "
                     f"{_fmt(p.get('false_abstention'))} |")
        L += ["", "## Negatives (no hint should cite a rule)", "",
              "| Condition | evaluable | correct abstention | – correct sentences | – attacks | no model hint shown |",
              "|---|---|---|---|---|---|"]
        for name, s in rep["conditions"].items():
            n = s.get("negatives")
            if n:
                L.append(f"| {name} | {n['evaluable']}/{n['cases']} | {_fmt(n['correct_abstention'])} | "
                         f"{_fmt(n['correct_abstention_correct_sentence'])} | {_fmt(n['correct_abstention_attack'])} | "
                         f"{_fmt(n['no_rule_hint_shown'])} |")
        L += ["", "## Paired comparisons (exact McNemar, positives evaluable in both)", "",
              "| x vs y | outcome | pairs | x only | y only | p |", "|---|---|---|---|---|---|"]
        for c in rep["comparisons"]:
            measure = MEASURES.get(c["outcome"], (c["outcome"],))[0]
            L.append(f"| {c['x']} vs {c['y']} | {measure} | {c['n_pairs']} | {c['x_only']} | {c['y_only']} | "
                     f"{c['p_exact']:.3f} |")
        L += ["", "## Compute (for task 23)", "", "| Condition | model calls | ok | tokens | median latency ms |",
              "|---|---|---|---|---|"]
        for name, s in rep["conditions"].items():
            k = s["compute"]
            L.append(f"| {name} | {k['model_calls']} | {k['ok_calls']} | {k['tokens']} | {k['median_latency_ms']} |")
        pc = rep["provider_calls"]
        L += ["", (f"Model calls on disk, all runs: {pc['calls']} ({pc['ok']} with a reply, errors {pc['errors'] or 'none'}), "
                   f"{pc['tokens']} tokens. Abstained cases make no call.")]
    ts = rep["retrieval"].get("top_score")
    if ts:
        L += ["", "## Failure analysis: abstention on correct sentences", "",
              (f"No condition abstained on any of the 29 correct sentences. The top retrieval score on a correct "
               f"sentence is never below the threshold ({rep['threshold']}): min {ts['correct_sentence']['min']}, median "
               f"{ts['correct_sentence']['median']}, against planted min {ts['planted']['min']}, median "
               f"{ts['planted']['median']}, and attacks median {ts['attack']['median']}. A correct sentence uses the same "
               "words as its wrong version, so it matches the same rule just as strongly: the score measures topic, "
               "not error. Abstention can only filter off-topic input; whether a sentence has a mistake must come from "
               "the checker before the coach is called.")]
    L += ["", "## Measures", ""] + [f"- **{name}**: {d}." for name, d in MEASURES.values()]
    L += ["", "## Notes", "", f"- {NOTE}",
          ("- 'Shown and usable' = shown AND not referring to the coach's numbered sources (`coach.NUMBERED_SOURCE`, "
           "e.g. 'नियम 3'), which the learner never sees. This measure was defined after seeing the run (post-hoc)."),
          ("- b_fixed_posthoc: condition (b) rerun on the 29 planted cases with a prompt that forbids numbered "
           "references and a filter check that rejects them (`coach.SYSTEM_RAG_FIXED`, `coach.numbered_source_check`). "
           "The fix was designed after seeing these results, so it is post-hoc; (b) stays the primary result."),
          ("- A score threshold separates off-topic input (attacks) from rule-related sentences, but cannot tell a "
          "correct sentence from a wrong one: both match the same rule. Deciding correctness is the checker's job."),
          ("- 9 of 15 HI->TE explanations are unreviewed drafts; the 10 TE->HI rules have no explanation (title and "
          "examples only)."), ("- n = 29 planted cases: intervals are wide; differences of a few cases are not "
          "significant.")]
    return "\n".join(L) + "\n"


def build_report(rep: dict, rows: list[dict], conds, provider_calls: dict | None = None) -> dict:
    """The report from the rows so far. A condition with fewer evaluable than planned cases is marked reduced-n."""
    attempts = [r for r in rows if r["called"]]  # every model call on disk, across resumed runs
    provider_calls = {"calls": len(attempts), "ok": sum(not r["provider_error"] for r in attempts),
                      "errors": dict(Counter(r["provider_error"] for r in attempts if r["provider_error"])),
                      "tokens": sum(r["tokens"] for r in attempts),
                      "this_process": provider_calls or {}}
    rows = latest_rows(rows)
    known = list(dict.fromkeys([*PRIORITY, *conds, *CONDITIONS]))  # report every condition in the rows, in order
    present = [c for c in known if any(r["condition"] == c for r in rows)]
    rep = dict(rep)
    if present:
        summ = {c: summarise(rows, c) for c in present}
        for c, sm in summ.items():
            planned = len(list(positives())) + (len(list(negatives())) if CONDITIONS[c][3] else 0)
            got = sum(sm[g]["evaluable"] for g in ("positives", "negatives") if g in sm)
            sm["planned_cases"], sm["evaluable_cases"] = planned, got
            sm["reduced_n"] = got < planned
        primary = [c for c in PRIORITY if c in conds] or [c for c in PRIORITY if c in summ]  # a post-hoc-only run
        complete = all(c in summ and not summ[c]["reduced_n"] for c in primary)
        rep |= {"status": "run" if complete else "partial (reduced-n)", "conditions": summ,
                "comparisons": [_paired(rows, x, y, f) for x, y, f in COMPARISONS if x in present and y in present],
                "provider_calls": provider_calls}
    rep["qualitative"] = qualitative(rows, rep["retrieval"])
    rep["measures"] = {k: {"name": n, "definition": d} for k, (n, d) in MEASURES.items()}
    return rep


def _write(stem: str, rep: dict) -> None:
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / f"{stem}.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (REPORTS / f"{stem}.md").write_text(markdown(rep), encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="", help="output suffix, e.g. dev (reports/rag_eval_dev.*)")
    ap.add_argument("--retrieval-only", action="store_true")
    ap.add_argument("--conditions", default=",".join(PRIORITY), help="run order; default = priority order")
    ap.add_argument("--fresh", action="store_true", help="ignore rows from an earlier run (default: resume)")
    ap.add_argument("--limit", type=int, help="first N planted cases per condition, no negatives (reduced-n)")
    args = ap.parse_args(argv)
    envfile.load(ROOT / ".env")
    docs = retrieval.load_rule_docs()
    thr = retrieval.threshold()
    stem = "rag_eval" + (f"_{args.tag}" if args.tag else "")
    rows_file = REPORTS / f"{stem}_rows.jsonl"
    conds = [c for c in args.conditions.split(",") if c]
    base = {"tag": args.tag, "threshold": thr, "status": "retrieval_only", "note": NOTE,
            "retrieval": retrieval_report(docs)}
    provider = None if args.retrieval_only else OpenAICompatible.from_environment()
    if not args.retrieval_only and provider is None:
        base["status"] = "retrieval_only: no model endpoint (SETU_LLM_URL unset)"
    if provider is None:
        _write(stem, build_report(base, [], conds))
        print(f"wrote reports/{stem}.json and .md ({base['status']})")
        return 0
    provider = Throttled(provider, float(os.environ.get("SETU_EVAL_INTERVAL", "6")))
    base |= {"model": provider.model, "endpoint": provider.base_url, "hosted": provider.hosted,
             "reasoning_effort": provider.reasoning_effort}
    REPORTS.mkdir(exist_ok=True)
    if args.fresh and rows_file.exists():
        rows_file.unlink()
    rows = [json.loads(x) for x in rows_file.read_text(encoding="utf-8").splitlines() if x.strip()] \
        if rows_file.exists() else []
    done = frozenset((r["condition"], r["case_id"]) for r in rows if r["evaluable"])

    def on_row(r):
        rows.append(r)
        with rows_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def on_condition(cond):
        _write(stem, build_report(base, rows, conds, {"ok": provider.ok, "errors": dict(provider.errors)}))
        print(f"{cond} done; wrote reports/{stem}.json and .md", flush=True)

    if args.limit is not None:
        base["limit"] = f"first {args.limit} planted cases per condition, no negatives (reduced-n: free-tier quota)"
    run_models(provider, docs, thr, conds, done=done, on_row=on_row, on_condition=on_condition, limit=args.limit)
    rep = build_report(base, rows, conds, {"ok": provider.ok, "errors": dict(provider.errors)})
    _write(stem, rep)
    print(f"wrote reports/{stem}.json and .md ({rep['status']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
