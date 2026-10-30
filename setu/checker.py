"""The checker: the only part that decides whether an answer is right. Deterministic, no language model.

  correct : the answer is one of the item's accepted forms
  wrong   : Raju's mistake left unchanged, a known wrong form, or (closed items) anything else
  unsure  : an open item got an answer the checker does not know -> a teacher decides; it never counts
"""
from __future__ import annotations
import re
from .contracts import Item, CheckResult
from .text import normalize, script_of, deva_to_telugu, fold_eo

NO_ERROR = "<NO_ERROR>"        # sent by the "there is no mistake" button (used from step 4)


def check(item: Item, answer: str) -> CheckResult:
    n = normalize(answer)
    r = lambda verdict, reason: CheckResult(item_id=item.item_id, answer=answer, verdict=verdict, reason=reason)
    if item.answer_script == "telugu" and script_of(n) in ("devanagari", "mixed"):
        n = deva_to_telugu(n)                    # Telugu typed with a Hindi keyboard (पुस्तकं -> పుస్తకం), even in part
    if not n:
        return r("unsure", "empty answer")
    if item.kind == "sentence":                   # short/long e-o: the Hindi keyboard cannot type the short ones
        n = fold_eo(n)
        item = item.model_copy(update={"accepted": [fold_eo(a) for a in item.accepted],
                                       "raju_wrong": fold_eo(item.raju_wrong),
                                       "accept_regex": [fold_eo(x) for x in item.accept_regex],
                                       "wrong_regex": [fold_eo(x) for x in item.wrong_regex]})
    if n in {normalize(a) for a in item.accepted}:
        return r("correct", "accepted form")
    if any(re.search(rx, n) for rx in item.accept_regex):
        return r("correct", "accepted pattern")
    if n == normalize(item.raju_wrong):
        return r("wrong", "Raju's mistake left unchanged")
    if any(re.search(rx, n) for rx in item.wrong_regex):
        return r("wrong", "the planted mistake is still in the sentence")
    if n in {normalize(w) for w in item.wrong_forms}:
        return r("wrong", "a known mistake")
    if item.answer_script != "any" and script_of(n) not in (item.answer_script, "none"):
        hint = "हिंदी (देवनागरी) में लिखिए" if item.answer_script == "devanagari" else "తెలుగు లిపిలో రాయండి"
        return r("wrong" if item.closed else "unsure", f"wrong script: {hint}")
    if item.closed:
        return r("wrong", "not the right answer")
    return r("unsure", "not a known right or wrong answer; a teacher will check")


DONT_KNOW = ("पता नहीं", "नहीं पता", "मालूम नहीं", "नहीं मालूम", "pata nahi", "don't know", "dont know", "no idea")


def _has(text: str, words: list, key: str) -> bool:
    """Long keywords may sit inside a word (जुड़ -> जुड़ता); short ones (आ, को, ने) must be a whole word."""
    k = key.lower().lstrip("-")
    if len(k) >= 3:
        return k in text
    return k in words


def check_why(key_ideas, answer: str) -> CheckResult:
    """Self-explanation (paper §5): the learner says WHY in their own words; the reason is scored against the rule's
    key ideas (keyword groups), with no model. All ideas -> correct; some -> 'partial' (reported as wrong, with the
    reason 'partial'); none, or "I don't know" -> wrong; nothing typed -> unsure."""
    n = normalize(answer).lower()
    r = lambda v, why: CheckResult(item_id="why", answer=answer, verdict=v, reason=why)
    if not n:
        return r("unsure", "empty answer")
    if any(d in n for d in DONT_KNOW) and len(n.split()) <= 4:
        return r("wrong", "none")
    words = [w.strip("-.,!?।'\"()") for w in n.replace("-", " -").split()]
    found = [g for g in key_ideas if any(_has(n, words, k) for k in g)]
    if found and len(found) == len(key_ideas):
        return r("correct", f"{len(found)}/{len(key_ideas)} key ideas")
    return r("wrong", "partial" if found else "none")
