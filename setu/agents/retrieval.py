"""Rule retrieval for the coach (TASKS.md task 9). Research option: the shipped coach does not call it.

The coach sees only what a human coach would see: Raju's sentence and the learner's wrong attempt. `build_query`
takes exactly those two strings and nothing else, so the planted rule's id or title can never reach the query.

Index: one document per rule (all 25: HI->TE and TE->HI) = title + explanation (+ approved examples: the Hindi
meaning and the correct form of each item). Explanations missing from `explanation_l1` fall back to the unreviewed
draft in `needs_rewrite.explanation_l1` and are tagged `explanation_source="draft"`.

Scoring: Okapi BM25 over character 2-4-grams of `normalise.canonical` words (padded with a space so word edges
count), which works for Devanagari and Telugu without a tokenizer. The score used for abstention is BM25 divided by
the number of query n-grams, so it does not grow with sentence length. Deterministic: ties break by rule id.

`oracle_hits` looks the planted rule up by id. It exists only as the upper bound in `setu.research.rag_eval`.
"""
import dataclasses
import functools
import math
import os
from collections import Counter
from pathlib import Path

import yaml

from setu.domain.normalise import canonical

ROOT = Path(__file__).resolve().parents[2]
NGRAMS = (2, 3, 4)
DEFAULT_THRESHOLD = 0.5  # per-n-gram BM25. Fixed a priori (not tuned on the eval cases); rag_eval also sweeps it.


def threshold() -> float:
    """The abstention threshold: SETU_RAG_THRESHOLD if set, else DEFAULT_THRESHOLD."""
    v = os.environ.get("SETU_RAG_THRESHOLD")
    return float(v) if v else DEFAULT_THRESHOLD


@dataclasses.dataclass(frozen=True)
class Example:
    item_id: str
    meaning: str  # Hindi (HI->TE) or Telugu (TE->HI) meaning
    correct: str  # the approved correct form


@dataclasses.dataclass(frozen=True)
class RuleDoc:
    rule_id: str
    direction: str
    title: str
    explanation: str
    examples: tuple  # tuple[Example, ...]
    explanation_source: str  # approved | draft | none


@dataclasses.dataclass(frozen=True)
class Hit:
    rule_id: str
    score: float  # BM25 / number of query n-grams
    rank: int  # 1-based


def _rule_doc(rule: dict) -> RuleDoc:
    expl, src = rule.get("explanation_l1"), "approved"
    if not expl:
        expl, src = (rule.get("needs_rewrite") or {}).get("explanation_l1"), "draft"
    if not expl:
        expl, src = "", "none"
    examples = tuple(Example(it["item_id"], it.get("l1_meaning") or "", it["correct_form"]) for it in rule["items"])
    return RuleDoc(rule["rule_id"], rule["direction"], rule.get("title_l1") or "", expl, examples, src)


@functools.lru_cache(maxsize=4)
def load_rule_docs(root: Path | None = None) -> tuple:
    root = Path(root or ROOT)
    docs = []
    for folder in ("hi-te", "te-hi"):
        for p in sorted((root / "content" / folder / "rules").glob("*.yaml")):
            docs.append(_rule_doc(yaml.safe_load(p.read_text(encoding="utf-8"))))
    return tuple(docs)


def grams(text: str) -> list[str]:
    out = []
    for w in canonical(text).split():
        w = f" {w} "
        for n in NGRAMS:
            out.extend(w[i:i + n] for i in range(len(w) - n + 1))
    return out


def doc_text(doc: RuleDoc, *, with_examples: bool = True, exclude_items: frozenset = frozenset()) -> str:
    parts = [doc.title, doc.explanation]
    if with_examples:
        parts += [f"{e.meaning} {e.correct}" for e in doc.examples if e.item_id not in exclude_items]
    return " ".join(p for p in parts if p)


def build_query(raju_sentence: str, learner_attempt: str) -> str:
    """What the coach may look at. Deliberately has no rule, item or title parameter."""
    return " ".join(s.strip() for s in (raju_sentence, learner_attempt) if s and s.strip())


class Retriever:
    """BM25 over the rule documents. `exclude_items` drops those items' examples from the index (leave-item-out,
    so an evaluation case never retrieves its own correct answer as an 'example')."""

    def __init__(self, docs, *, with_examples: bool = True, exclude_items=frozenset(), k1: float = 1.5,
                 b: float = 0.75):
        self.docs = tuple(docs)
        self.with_examples, self.exclude_items = with_examples, frozenset(exclude_items)
        self.k1, self.b = k1, b
        self._tf = [Counter(grams(doc_text(d, with_examples=with_examples, exclude_items=self.exclude_items)))
                    for d in self.docs]
        self._len = [sum(tf.values()) for tf in self._tf]
        self._avg = (sum(self._len) / len(self._len)) if self._len else 0.0
        df = Counter(g for tf in self._tf for g in tf)
        n = len(self.docs)
        self._idf = {g: math.log(1 + (n - f + 0.5) / (f + 0.5)) for g, f in df.items()}

    def by_id(self, rule_id: str) -> RuleDoc:
        return next(d for d in self.docs if d.rule_id == rule_id)

    def search(self, query: str, k: int = 3) -> list[Hit]:
        q = Counter(grams(query))
        nq = sum(q.values())
        if not nq or not self.docs:
            return []
        scores = []
        for d, tf, dl in zip(self.docs, self._tf, self._len):
            s = 0.0
            for g, qf in q.items():
                f = tf.get(g)
                if f:
                    s += qf * self._idf[g] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self._avg))
            scores.append((-s / nq, d.rule_id))
        scores.sort()
        return [Hit(rid, round(-neg, 6), i + 1) for i, (neg, rid) in enumerate(scores[:k])]


def oracle_hits(docs, rule_id: str) -> list[Hit]:
    """Upper bound only: the planted rule, as if retrieval were perfect."""
    if not any(d.rule_id == rule_id for d in docs):
        raise KeyError(rule_id)
    return [Hit(rule_id, math.inf, 1)]
