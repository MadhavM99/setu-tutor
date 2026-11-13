"""Training pairs for the Raju QLoRA model (TASKS.md task 10, step 2), checked by a RESEARCH validator.

The app's leak filter (`leakfilter.check_sentence`) can only certify the ~29 approved planted sentences, so it cannot
label new training data. This module adds a separate, weaker validator for (correct, wrong) pairs; the leak filter is
not changed, and task 17 still scores the tuned model with the strict app filter on the frozen cases.

A pair (correct, wrong) for rule R is accepted only if:
- both are one plain Telugu student sentence (the leak filter's surface checks: script, format, gloss, persona, ...);
- every word of both is in the bank vocabulary (all Telugu words in content/);
- they differ in exactly one contiguous region (common prefix and suffix removed) of at most MAX_REGION words a side;
- the wrong sentence matches one of R's wrong markers (item `wrong_patterns` + `rejected_patterns` kind=wrong), the
  match overlaps that region, and the correct sentence matches none of R's markers;
- the corrected words (the correct side of the region) do not appear, in order, in the wrong sentence.
It cannot check meaning or naturalness: nobody native has read the generated pairs.

Sources, in priority order, each pair tagged: `bank` (approved HI->TE pairs that are not frozen cases: there are
none, all 29 are frozen), `slot` (a shared word of a frozen pair swapped for the word another item of the same rule
has in that position), `gemini` (new meanings, generated with the rule explanation and the bank vocabulary).
The 29 frozen pairs and their near-duplicates never enter training (see `near_duplicate`).

    .venv/bin/python -m setu.research.ft_data                       # validator checks + slot source, no model
    .venv/bin/python -m setu.research.ft_data --gemini --calls 120  # + model top-up (resumable, throttled)
"""
import argparse
import dataclasses
import functools
import json
import os
import re
import time
from collections import Counter
from pathlib import Path

import yaml

from setu.agents.llm import OpenAICompatible
from setu.domain import leakfilter
from setu.domain.normalise import canonical

from . import envfile

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/ft"
REPORT = ROOT / "reports/ft_data.json"
MANIFEST = ROOT / "tests/eval_sets/manifest.json"
MAX_REGION = 4  # the bank's longest planted error (HI-TE-010, relative clause) changes 4 words
NEAR = 0.3  # normalised character edit distance at or below this is a near-duplicate
# go/no-go (user decision, 13 Nov 2026): all must hold
GO_MIN_RULES, GO_MIN_PAIRS, GO_MIN_PER_FROZEN_RULE, GO_MIN_RECALL = 12, 200, 10, 0.9
GO_DECISION_RULE = ("go uses pairs_per_frozen_rule WITHOUT HI-TE-006 (decided 13 Nov 2026, before any data was "
                    "generated): HI-TE-006 is excluded from training by design because its right form (మేము vs మనం) "
                    "depends on the meaning, which a pair cannot show. go_strict, which counts it, can never be met.")
_TELUGU_WORD = re.compile(r"[ఀ-౿]+")


@dataclasses.dataclass(frozen=True)
class RuleSpec:
    rule_id: str
    direction: str
    title: str
    explanation: str
    markers: tuple  # regexes for this rule's error, on canonical text
    items: tuple  # (item_id, l1_meaning, correct_form, wrong_form)


def _spec(rule: dict) -> RuleSpec:
    markers = []
    for it in rule["items"]:
        markers += it.get("wrong_patterns") or []
        markers += [p["pattern"] for p in it.get("rejected_patterns") or [] if p.get("kind") == "wrong"]
    expl = rule.get("explanation_l1") or (rule.get("needs_rewrite") or {}).get("explanation_l1") or ""
    items = tuple((it["item_id"], it.get("l1_meaning") or "", it["correct_form"], it.get("wrong_form") or "")
                  for it in rule["items"])
    return RuleSpec(rule["rule_id"], rule["direction"], rule.get("title_l1") or "", expl,
                    tuple(dict.fromkeys(markers)), items)


@functools.lru_cache(maxsize=1)
def rule_specs() -> tuple:
    out = []
    for folder in ("hi-te", "te-hi"):
        for p in sorted((ROOT / "content" / folder / "rules").glob("*.yaml")):
            out.append(_spec(yaml.safe_load(p.read_text(encoding="utf-8"))))
    return tuple(out)


@functools.lru_cache(maxsize=1)
def vocabulary() -> frozenset:
    """Telugu words of the bank's sentences only (rule forms, lexicon, chunks, scene lines, TE->HI meanings), not of
    explanations or notes, which contain word fragments such as suffixes."""
    texts = []
    for spec in rule_specs():
        texts += [t for _, m, c, w in spec.items for t in (m, c, w)]
    for p in sorted((ROOT / "content/hi-te/rules").glob("*.yaml")):
        for it in yaml.safe_load(p.read_text(encoding="utf-8"))["items"]:
            texts += [v["form"] for v in it["accepted_variants"]]
    hi = ROOT / "content/hi-te"
    texts += [e.get("telugu") or "" for e in yaml.safe_load((hi / "lexicon.yaml").read_text(encoding="utf-8"))]
    texts += [e.get("telugu") or "" for e in yaml.safe_load((hi / "chunks.yaml").read_text(encoding="utf-8"))]
    for sc in yaml.safe_load((hi / "scene_scripts.yaml").read_text(encoding="utf-8")):
        texts += [ln.get("telugu") or "" for ln in sc.get("lines", [])]
        texts += list((sc.get("vocabulary") or {}).get("required") or [])
        texts += list((sc.get("vocabulary") or {}).get("permitted") or [])
    return frozenset(canonical(w) for t in texts for w in _TELUGU_WORD.findall(t or ""))


@functools.lru_cache(maxsize=1)
def frozen_pairs() -> tuple:
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return tuple((c["rule_id"], c["item_id"], c["correct_form"], c["wrong_form"]) for c in m["planting_cases"])


# Rules whose right form depends on the meaning, not on the sentence: a pair alone cannot show which side is the
# error (for HI-TE-006 the validator accepts both directions), so they are excluded from training.
MEANING_DEPENDENT = frozenset({"HI-TE-006"})


@functools.lru_cache(maxsize=1)
def rule_shapes() -> dict:
    """(correct words changed, wrong words changed) of each rule's approved planted errors."""
    out: dict = {}
    for spec in rule_specs():
        for _, _, c, w in spec.items:
            if w:
                creg, wreg, _ = region(c, w)
                out.setdefault(spec.rule_id, set()).add((len(creg), len(wreg)))
    return out


# ---------------------------------------------------------------- validator

def region(correct: str, wrong: str) -> tuple[list, list, int]:
    """Words that differ after removing the common prefix and suffix: (correct side, wrong side, prefix length)."""
    c, w = canonical(correct).split(), canonical(wrong).split()
    i = 0
    while i < min(len(c), len(w)) and c[i] == w[i]:
        i += 1
    j = 0
    while j < min(len(c), len(w)) - i and c[-1 - j] == w[-1 - j]:
        j += 1
    return c[i:len(c) - j], w[i:len(w) - j], i


def _char_span(words: list, start: int, n: int) -> tuple[int, int]:
    """Character span in ' '.join(words) of words[start:start+n] (n = 0: the insertion point)."""
    pre = len(" ".join(words[:start])) + (1 if start else 0)
    return (pre, pre + len(" ".join(words[start:start + n]))) if n else (pre, pre)


def validate_pair(spec: RuleSpec, correct: str, wrong: str, vocab=None) -> list[str]:
    vocab = vocabulary() if vocab is None else vocab
    out: list[str] = []
    for tag, s in (("CORRECT", correct), ("WRONG", wrong)):
        surf: list = []
        leakfilter._surface(s or "", "telugu", surf)  # the app filter's own surface checks, unchanged
        out += [f"{tag}_{r}" for r in surf]
        if any(t not in vocab and not t.isdigit() for t in canonical(s).split()):
            out.append(f"{tag}_OOV")
    c, w = canonical(correct), canonical(wrong)
    if not c or not w:
        return out + ["EMPTY"]
    if c == w:
        return out + ["NO_EDIT"]
    creg, wreg, start = region(correct, wrong)
    if len(creg) > MAX_REGION or len(wreg) > MAX_REGION:
        out.append("REGION_TOO_LONG")
    hits = [(p, m) for p in spec.markers for m in re.finditer(p, w)]
    lo, hi = _char_span(w.split(), start, len(wreg))
    at = [(p, m) for p, m in hits if m.start() <= hi and m.end() >= lo]
    if not hits:
        out.append("NOT_RULE_ERROR")
    elif not at:
        out.append("EDIT_NOT_AT_MARKER")
    else:
        # the edit must have the shape of the rule's approved planted errors (words changed on each side): an extra
        # edit next to the error would otherwise merge into the same region
        shapes = rule_shapes().get(spec.rule_id)
        if shapes and (len(creg), len(wreg)) not in shapes:
            out.append("EDIT_SHAPE")
        # the correct side must not carry the error it is said to fix (only the markers that matched: a rule like
        # HI-TE-006 has opposite markers on its two items)
        if any(re.search(p, c) for p in {p for p, _ in at}):
            out.append("CORRECT_HAS_ERROR")
    if creg and f" {' '.join(creg)} " in f" {w} ":
        out.append("CORRECTION_IN_WRONG")
    return list(dict.fromkeys(out))


# ---------------------------------------------------------------- overlap with the frozen cases

def _lev(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def norm_distance(a: str, b: str) -> float:
    a, b = canonical(a), canonical(b)
    return _lev(a, b) / max(1, len(a), len(b))


def near_duplicate(correct: str, wrong: str, near: float = NEAR) -> str | None:
    """The frozen item id this pair is (near-)identical to, on EITHER side, or None."""
    for _, iid, fc, fw in frozen_pairs():
        if norm_distance(correct, fc) <= near or norm_distance(wrong, fw) <= near:
            return iid
    return None


# ---------------------------------------------------------------- validator checks

def recall_on_frozen() -> dict:
    specs = {s.rule_id: s for s in rule_specs()}
    rows = [{"item_id": iid, "reasons": validate_pair(specs[rid], c, w)} for rid, iid, c, w in frozen_pairs()]
    return {"n": len(rows), "accepted": sum(not r["reasons"] for r in rows),
            "rejected": [r for r in rows if r["reasons"]]}


def synthetic_negatives() -> list[dict]:
    """Pairs known NOT to be one planted error of the rule they are checked against."""
    specs = {s.rule_id: s for s in rule_specs()}
    frozen = frozen_pairs()
    vocab = sorted(vocabulary())
    out = []
    for rid, iid, c, w in frozen:
        spec = specs[rid]
        out.append({"kind": "no_edit", "rule_id": rid, "src": iid, "correct": c, "wrong": c})
        out.append({"kind": "reversed", "rule_id": rid, "src": iid, "correct": w, "wrong": c})
        # second, unrelated edit: change the first word outside the error region to another bank word
        _creg, wreg, start = region(c, w)
        words = canonical(w).split()
        outside = [k for k in range(len(words)) if not start <= k < start + len(wreg)]
        if outside:
            k = outside[0]
            repl = next(v for v in vocab if len(v) >= 3 and v not in words)
            w2 = " ".join(words[:k] + [repl] + words[k + 1:])
            out.append({"kind": "double_edit", "rule_id": rid, "src": iid, "correct": c, "wrong": w2})
        for orid, oiid, oc, ow in frozen:
            if orid != rid:
                out.append({"kind": "wrong_rule", "rule_id": rid, "src": oiid, "correct": oc, "wrong": ow,
                            "spec": spec.rule_id})
    return out


def false_accepts() -> dict:
    specs = {s.rule_id: s for s in rule_specs()}
    negs = synthetic_negatives()
    by_kind: dict = {}
    examples = []
    for n in negs:
        ok = not validate_pair(specs[n["rule_id"]], n["correct"], n["wrong"])
        k = by_kind.setdefault(n["kind"], {"n": 0, "accepted": 0})
        k["n"] += 1
        k["accepted"] += ok
        if ok and len(examples) < 10:
            examples.append(n)
    return {"by_kind": by_kind, "n": len(negs), "accepted": sum(v["accepted"] for v in by_kind.values()),
            "examples": examples}


# ---------------------------------------------------------------- sources

def slot_pairs() -> list[dict]:
    """For each frozen pair, swap one shared word (outside the error region) for the word another item of the same
    rule has at that position (same length, same rule). Grammatical by construction only as far as the bank is."""
    out = []
    by_rule: dict = {}
    for rid, iid, c, w in frozen_pairs():
        by_rule.setdefault(rid, []).append((iid, canonical(c).split(), canonical(w).split()))
    for rid, rows in by_rule.items():
        for iid, c, w in rows:
            _, wreg, start = region(" ".join(c), " ".join(w))
            for oid, oc, ow in rows:
                if oid == iid or len(oc) != len(c) or len(ow) != len(w):
                    continue
                for k in range(len(c)):
                    kw = k if k < start else k + len(w) - len(c)  # same word on the wrong side
                    if not (0 <= kw < len(w)) or c[k] != w[kw] or start <= kw < start + len(wreg):
                        continue
                    if oc[k] == c[k] or k >= len(oc) or kw >= len(ow) or oc[k] != ow[kw]:
                        continue
                    c2 = c[:k] + [oc[k]] + c[k + 1:]
                    w2 = w[:kw] + [ow[kw]] + w[kw + 1:]
                    out.append({"rule_id": rid, "source": "slot", "from": [iid, oid],
                                "correct": " ".join(c2), "wrong": " ".join(w2), "hindi": None})
    uniq = {(p["rule_id"], p["correct"], p["wrong"]): p for p in out}
    return list(uniq.values())


GEN_SYSTEM = ("You write training data for a Telugu tutor. For the grammar rule given, write NEW pairs: a correct, "
              "simple Telugu sentence a beginner could say, and the same sentence with exactly ONE mistake of this "
              "rule, the mistake a Hindi speaker makes. Change nothing else. Use only words from the word list. "
              "Reply with JSON only: {\"pairs\": [{\"hindi\": \"...\", \"correct\": \"...\", \"wrong\": \"...\"}]}")


def _gen_prompt(spec: RuleSpec, words: list, k: int, avoid: list) -> list:
    ex = "\n".join(f"- hindi: {m} | correct: {c} | wrong: {w}" for _, m, c, w in spec.items if w)
    return [{"role": "system", "content": GEN_SYSTEM},
            {"role": "user", "content": f"Rule: {spec.title}\nExplanation (Hindi): {spec.explanation}\n"
                                        f"Examples (do NOT repeat these):\n{ex}\n"
                                        f"Already written (do not repeat): {'; '.join(avoid[-20:]) or '-'}\n"
                                        f"Word list: {' '.join(words)}\nWrite {k} new pairs."}]


def _prompt_words(spec: RuleSpec, limit: int = 160) -> list:
    """The rule's own words first, then the rest of the bank vocabulary, deterministic order."""
    own = [t for _, _, c, w in spec.items for t in canonical(f"{c} {w}").split()]
    rest = sorted(vocabulary())
    return list(dict.fromkeys(own + rest))[:limit]


def generate(provider, specs, *, calls_per_rule: int, k: int = 8, interval: float = 6.0, log=print) -> None:
    """Resumable: a call (rule, index) already in drafts.jsonl is skipped. Every call is logged, errors included;
    a failed call is not counted and is retried on the next run."""
    DATA.mkdir(parents=True, exist_ok=True)
    drafts_p = DATA / "drafts.jsonl"
    done = set()
    avoid: dict = {}
    if drafts_p.exists():
        for line in drafts_p.read_text(encoding="utf-8").splitlines():
            d = json.loads(line)
            if d.get("ok"):
                done.add((d["rule_id"], d["call"]))
                avoid.setdefault(d["rule_id"], []).extend(p.get("correct", "") for p in d.get("pairs", []))
    last = 0.0
    with drafts_p.open("a", encoding="utf-8") as f:
        for spec in specs:
            for i in range(calls_per_rule):
                if (spec.rule_id, i) in done:
                    continue
                wait = last + interval - time.monotonic()
                if wait > 0:
                    time.sleep(wait)
                c = provider.complete(_gen_prompt(spec, _prompt_words(spec), k, avoid.get(spec.rule_id, [])),
                                      max_tokens=900, temperature=0.9)
                last = time.monotonic()
                rec = {"rule_id": spec.rule_id, "call": i, "ok": c.ok, "error": c.error, "latency_ms": c.latency_ms,
                       "tokens": (c.prompt_tokens or 0) + (c.completion_tokens or 0), "model": c.model, "pairs": []}
                if c.ok:
                    try:
                        obj = json.loads(re.search(r"\{.*\}", c.text, re.DOTALL).group(0))
                        rec["pairs"] = [p for p in obj.get("pairs", []) if isinstance(p, dict)]
                    except (AttributeError, ValueError):
                        rec["ok"], rec["error"] = False, "unparseable_reply"
                        rec["raw"] = c.text[:2000]
                if not rec["ok"]:
                    log(f"model call failed [{spec.rule_id} #{i}]: {rec['error']}")
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
                avoid.setdefault(spec.rule_id, []).extend(p.get("correct", "") for p in rec["pairs"])


def gemini_pairs() -> tuple[list, dict]:
    """Every generated pair from drafts.jsonl, validated (accepted and rejected), plus call stats."""
    p = DATA / "drafts.jsonl"
    if not p.exists():
        return [], {"calls": 0}
    pairs, calls, ok, errors, tokens = [], 0, 0, Counter(), 0
    for line in p.read_text(encoding="utf-8").splitlines():
        d = json.loads(line)
        calls += 1
        tokens += d.get("tokens") or 0
        if not d["ok"]:
            errors[d["error"]] += 1
            continue
        ok += 1
        for q in d["pairs"]:
            pairs.append({"rule_id": d["rule_id"], "source": "gemini", "model": d.get("model"),
                          "correct": str(q.get("correct", "")), "wrong": str(q.get("wrong", "")),
                          "hindi": q.get("hindi")})
    return pairs, {"calls": calls, "ok_calls": ok, "errors": dict(errors), "tokens": tokens}


# ---------------------------------------------------------------- build

def build(candidates: list[dict]) -> tuple[list, list]:
    specs = {s.rule_id: s for s in rule_specs()}
    frozen = {(canonical(c), canonical(w)) for _, _, c, w in frozen_pairs()}
    accepted, rejected, seen = [], [], set()
    for p in candidates:
        key = (canonical(p["correct"]), canonical(p["wrong"]))
        reasons = validate_pair(specs[p["rule_id"]], p["correct"], p["wrong"]) if p["rule_id"] in specs else [
            "UNKNOWN_RULE"]
        if p["rule_id"] in MEANING_DEPENDENT:
            reasons.append("MEANING_DEPENDENT_RULE")
        if key in frozen:
            reasons.append("FROZEN_CASE")
        else:
            nd = near_duplicate(p["correct"], p["wrong"])
            if nd:
                reasons.append(f"NEAR_FROZEN:{nd}")
        if key in seen:
            reasons.append("DUPLICATE")
        row = {**p, "correct": key[0], "wrong": key[1], "reasons": reasons}
        if reasons:
            rejected.append(row)
        else:
            seen.add(key)
            accepted.append(row)
    return accepted, rejected


FUNNEL_STAGES = (  # a rejected pair is counted at the FIRST stage it fails
    ("form_and_vocabulary", lambda r: (r.startswith(("CORRECT_", "WRONG_")) and r != "CORRECT_HAS_ERROR")
     or r in ("EMPTY", "UNKNOWN_RULE", "MEANING_DEPENDENT_RULE")),
    ("one_edit_of_this_rule", lambda r: r in ("NOT_RULE_ERROR", "NO_EDIT", "REGION_TOO_LONG", "CORRECT_HAS_ERROR",
                                              "CORRECTION_IN_WRONG") or r.startswith("EDIT_")),
    ("not_a_frozen_case_or_near_duplicate", lambda r: r.startswith(("FROZEN_CASE", "NEAR_FROZEN"))),
    ("not_a_duplicate", lambda r: r == "DUPLICATE"),
)


def funnel(accepted, rejected, gen_stats, source: str = "gemini") -> dict:
    """Yield of one source, stage by stage: how many candidates survive each check, in order."""
    rej = [p for p in rejected if p.get("source") == source]
    acc = [p for p in accepted if p.get("source") == source]
    first = Counter()
    for p in rej:
        stage = next((name for name, hit in FUNNEL_STAGES if any(hit(r) for r in p["reasons"])), "other")
        first[stage] += 1
    left, stages = len(rej) + len(acc), []
    out = {"source": source, "calls": gen_stats.get("calls", 0), "calls_with_reply": gen_stats.get("ok_calls", 0),
           "call_errors": gen_stats.get("errors", {}), "candidates": left}
    for name, _ in FUNNEL_STAGES:
        left -= first[name]
        stages.append({"check": name, "removed": first[name], "remaining": left})
    if first["other"]:
        left -= first["other"]
        stages.append({"check": "other", "removed": first["other"], "remaining": left})
    out["stages"], out["accepted"] = stages, len(acc)
    return out


def summary(accepted, rejected, gen_stats, recall: dict | None = None) -> dict:
    hi_te = [s.rule_id for s in rule_specs() if s.direction == "HI->TE"]
    te_hi = [s.rule_id for s in rule_specs() if s.direction == "TE->HI"]
    trainable = [r for r in hi_te if r not in MEANING_DEPENDENT]  # the validator checks Telugu only
    by_rule = Counter(p["rule_id"] for p in accepted)
    covered = [r for r in trainable if by_rule[r]]
    frozen_dirs = {s.rule_id: s.direction for s in rule_specs()}
    frozen_rules = sorted({rid for rid, *_ in frozen_pairs()})
    per_rule = {r: {"pairs": by_rule[r], "met": by_rule[r] >= GO_MIN_PER_FROZEN_RULE,
                    "note": "excluded (meaning-dependent): cannot be met" if r in MEANING_DEPENDENT else None}
                for r in frozen_rules if frozen_dirs[r] == "HI->TE"}
    recall = recall or recall_on_frozen()
    recall_rate = recall["accepted"] / recall["n"] if recall["n"] else 0.0
    checks = {
        "rules_covered": {"value": f"{len(covered)} of {len(trainable)}", "need": f">= {GO_MIN_RULES}",
                          "met": len(covered) >= GO_MIN_RULES},
        "total_pairs": {"value": len(accepted), "need": f">= {GO_MIN_PAIRS}", "met": len(accepted) >= GO_MIN_PAIRS},
        "pairs_per_frozen_rule": {"need": f">= {GO_MIN_PER_FROZEN_RULE} for every HI->TE rule in the frozen cases",
                                  "met": all(v["met"] for v in per_rule.values()),
                                  "met_excluding_meaning_dependent": all(
                                      v["met"] for r, v in per_rule.items() if r not in MEANING_DEPENDENT),
                                  "failing": sorted(r for r, v in per_rule.items() if not v["met"])},
        "validator_recall": {"value": round(recall_rate, 3), "need": f">= {GO_MIN_RECALL}",
                             "met": recall_rate >= GO_MIN_RECALL},
    }
    return {"accepted": len(accepted), "rejected": len(rejected),
            "by_source": dict(Counter(p["source"] for p in accepted)),
            "by_rule": {r: by_rule[r] for r in hi_te + te_hi},
            "rejection_reasons": dict(Counter(r.split(":")[0] for p in rejected for r in p["reasons"])),
            "coverage": {"hi_te_trainable": f"{len(covered)} of {len(trainable)}",
                         "scope": "HI->TE only: the validator checks Telugu sentences; HI-TE-006 excluded because "
                                  "its right form (మేము vs మనం) depends on the meaning, which a pair cannot show",
                         "te_hi": "out of scope (0 of 10)"},
            "frozen_cases_by_direction": {d: sum(frozen_dirs[rid] == d for rid, *_ in frozen_pairs())
                                          for d in ("HI->TE", "TE->HI")},
            "pairs_per_frozen_rule": per_rule,
            "generation": gen_stats,
            "funnel_gemini": funnel(accepted, rejected, gen_stats),
            "go_no_go": {"go": all(c["met"] for k, c in checks.items() if k != "pairs_per_frozen_rule")
                         and checks["pairs_per_frozen_rule"]["met_excluding_meaning_dependent"],
                         "go_strict": all(c["met"] for c in checks.values()),
                         "decision_rule": GO_DECISION_RULE, "checks": checks}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gemini", action="store_true", help="top up with model-generated pairs (SETU_LLM_* from .env)")
    ap.add_argument("--calls", type=int, default=8, help="model calls per rule")
    ap.add_argument("--rules", default="HI->TE", help="HI->TE, TE->HI or all")
    args = ap.parse_args(argv)
    envfile.load(ROOT / ".env")
    specs = [s for s in rule_specs() if s.markers and s.rule_id not in MEANING_DEPENDENT
             and (args.rules == "all" or s.direction == args.rules)]
    if args.gemini:
        provider = OpenAICompatible.from_environment()
        if provider is None:
            print("no model endpoint (SETU_LLM_URL unset); skipping generation")
        else:
            generate(provider, specs, calls_per_rule=args.calls,
                     interval=float(os.environ.get("SETU_EVAL_INTERVAL", "6")))
    gen, gen_stats = gemini_pairs()
    accepted, rejected = build(slot_pairs() + gen)
    DATA.mkdir(parents=True, exist_ok=True)
    for name, rows in (("pairs.jsonl", accepted), ("rejected.jsonl", rejected)):
        (DATA / name).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    (DATA / "config.json").write_text(json.dumps(
        {"max_region": MAX_REGION, "near_duplicate": NEAR, "calls_per_rule": args.calls, "rules": args.rules,
         "generation_system_prompt": GEN_SYSTEM, "model": os.environ.get("SETU_LLM_MODEL")},
        indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    recall = recall_on_frozen()
    rep = {"validator": {"recall_on_frozen": recall, "false_accepts_synthetic": false_accepts(),
                         "note": "research validator, weaker than the app leak filter; checks form, not meaning"},
           "data": summary(accepted, rejected, gen_stats, recall)}
    REPORT.write_text(json.dumps(rep, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    v, d = rep["validator"], rep["data"]
    print(f"recall {v['recall_on_frozen']['accepted']}/{v['recall_on_frozen']['n']} · false accepts "
          f"{v['false_accepts_synthetic']['accepted']}/{v['false_accepts_synthetic']['n']} · accepted {d['accepted']} "
          f"{d['by_source']} · coverage {d['coverage']['hi_te_trainable']} · go={d['go_no_go']['go']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
