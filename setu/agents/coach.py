"""The AI coach (P-ARCH-07, F-COACH, X-COACH-01). Slice: mid-submission.

After a first wrong or partial answer the model may propose one short Hindi hint of a requested type. The proposal
is shown only if `check_hint_has_no_answer` passes (no corrected form in Telugu, Devanagari or Latin, no Latin text,
length) and it is Hindi; otherwise the approved hint, or the generic catalog hint, is used. The model never sees the
learner's identity, cannot decide correctness, and its hint is never shown after the answer is revealed. A model
hint may not contain Telugu script at all (approved teacher hints may, after validation).
"""
import dataclasses
import re

from setu.domain import leakfilter

from .llm import Completion, parse_json

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_TELUGU = re.compile(r"[\u0C00-\u0C7F]")
SYSTEM = ("तुम एक शांत हिंदी शिक्षक हो। विद्यार्थी ने तेलुगु वाक्य सुधारने में गलती की। उसे एक छोटा इशारा दो जो सही वाक्य "
          "या सही शब्द कभी न बताए, सिर्फ़ यह बताए कि कहाँ देखना है। जवाब सिर्फ़ JSON में: {\"hint\": \"...\"}")


@dataclasses.dataclass(frozen=True)
class CoachHint:
    text: str | None  # None: show the generic catalog hint
    hint_type: str
    source: str  # model | approved | generic
    rejected: tuple
    completion: Completion | None
    # research modes only (`hint_with_mode`); the shipped `hint` leaves these at their defaults
    mode: str = "shipped"
    retrieved: tuple = ()  # retrieval.Hit, in rank order
    cited_rule_id: str | None = None
    abstained: bool = False


def hint(provider, item, *, rule_title: str, approved: tuple[str, str | None], wrong_sentence: str) -> CoachHint:
    """`approved` is (type, text) from `exchange.choose_hint`, the deterministic fallback."""
    if provider is None:
        return CoachHint(approved[1], approved[0], "approved" if approved[1] else "generic", (), None)
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"नियम: {rule_title}\nराजू का वाक्य: {wrong_sentence}\nएक इशारा दो।"}]
    c = provider.complete(msgs, max_tokens=120)
    obj = parse_json(c.text, ("hint",)) if c.ok else None
    text = obj["hint"].strip() if obj and isinstance(obj["hint"], str) else None
    reasons = list(leakfilter.check_hint(item, text)) if text else ["NO_HINT"]
    if text and not _DEVANAGARI.search(text):
        reasons.append("NOT_HINDI")
    if text and _TELUGU.search(text):  # a model hint is Hindi only: no Telugu the learner may not know (real-model
        reasons.append("TELUGU_IN_HINT")  # finding, 31 Oct 2026: hints mixed in unseen Telugu words)
    if not reasons:
        return CoachHint(text, "l1_rule", "model", (), c)
    return CoachHint(approved[1], approved[0], "approved" if approved[1] else "generic", tuple(reasons), c)


# ---------------------------------------------------------------- research modes (TASKS.md task 9; not used by the app)

# A hint that points at the coach's own numbered source list ("नियम 3", "rule 2", "तीसरा नियम"): the learner never
# sees that list, so such a hint is not usable. Found in the task 16 run (post-hoc).
NUMBERED_SOURCE = re.compile(
    r"(?:नियम|स्रोत|सोर्स|rule|source)\s*(?:नं\.?|नंबर|संख्या|#|no\.?)?\s*[0-9०-९]+"
    r"|(?:पहल|दूसर|तीसर)[ाेी]\s+(?:नियम|स्रोत)", re.IGNORECASE)
MODES = ("blind", "rag", "oracle")
TOP_K = 3
SYSTEM_RAG = ("तुम एक शांत हिंदी शिक्षक हो। विद्यार्थी ने तेलुगु वाक्य सुधारने में गलती की। नीचे कुछ नियम दिए हैं। जो नियम इस "
              "गलती पर लागू होता है, उसी के आधार पर एक छोटा हिंदी इशारा दो जो सही वाक्य या सही शब्द कभी न बताए, "
              "सिर्फ़ यह बताए कि कहाँ देखना है। इशारे में तेलुगु लिपि बिल्कुल नहीं। "
              "जवाब सिर्फ़ JSON में: {\"hint\": \"...\", \"source\": <नियम का नंबर>}")


def _situation(raju_sentence: str, learner_attempt: str) -> str:
    return f"राजू का वाक्य: {raju_sentence}\nविद्यार्थी का सुधार: {learner_attempt}"


def _sources_block(retriever, hits) -> str:
    """Numbered sources. Rule ids are never shown to the model: it cites a number, mapped back by the harness."""
    lines = []
    for n, h in enumerate(hits, 1):
        d = retriever.by_id(h.rule_id)
        s = f"नियम {n}: {d.title}\nव्याख्या: {d.explanation or '—'}"
        if retriever.with_examples:
            ex = [f"{e.meaning} = {e.correct}" for e in d.examples if e.item_id not in retriever.exclude_items]
            if ex:
                s += "\nउदाहरण: " + "; ".join(ex)
        lines.append(s)
    return "\n\n".join(lines)


# Post-hoc fix (task 16, 14 Nov 2026, designed AFTER seeing the run): the RAG prompt told the model to cite a rule by
# number, and 8 of 20 shown RAG hints then told the learner to "read rule N". The fixed prompt keeps the number in the
# `source` field only and asks for the rule in Hindi words; `NUMBERED_SOURCE` also becomes a filter check. Used only
# with `hint_with_mode(..., fixed=True)`; the original prompt stays for reproducing the primary result.
SYSTEM_RAG_FIXED = SYSTEM_RAG.replace(
    "सिर्फ़ यह बताए कि कहाँ देखना है।",
    "सिर्फ़ यह बताए कि कहाँ देखना है। इशारे में नियमों को कभी नंबर से मत बताओ (जैसे 'नियम 2' नहीं): विद्यार्थी को यह सूची "
    "नहीं दिखती। नियम की बात अपने हिंदी शब्दों में समझाओ। नंबर सिर्फ़ \"source\" में लिखो।")
assert SYSTEM_RAG_FIXED != SYSTEM_RAG


def numbered_source_check(text: str | None) -> list[str]:
    """['NUMBERED_SOURCE'] if the hint refers to the coach's numbered sources, else []."""
    return ["NUMBERED_SOURCE"] if text and NUMBERED_SOURCE.search(text) else []


def _checks(item, text: str | None) -> list[str]:
    """The shipped coach's checks, unchanged: answer leak, Latin, length, unsafe, Hindi only, no Telugu."""
    reasons = list(leakfilter.check_hint(item, text)) if text else ["NO_HINT"]
    if text and not _DEVANAGARI.search(text):
        reasons.append("NOT_HINDI")
    if text and _TELUGU.search(text):
        reasons.append("TELUGU_IN_HINT")
    return reasons


def hint_with_mode(provider, item, *, mode: str, raju_sentence: str, learner_attempt: str,
                   approved: tuple[str, str | None], retriever=None, oracle_rule_id: str | None = None,
                   threshold: float | None = None, fixed: bool = False) -> CoachHint:
    """A hint from what a real coach sees (Raju's sentence and the learner's attempt), for the RAG evaluation.

    blind:  no rule, no retrieval;
    rag:    BM25 retrieval from the query of those two sentences; abstains (fallback, no model call) when the top
            score is below `threshold` (None: never abstain);
    oracle: the planted rule given directly (`oracle_rule_id`): the upper bound.
    The hint must cite one of the shown rules by number; the cited rule id is recorded, never shown to the learner.
    Any failed check returns the approved/generic fallback, with the reasons.
    fixed: the post-hoc variant (SYSTEM_RAG_FIXED prompt + the NUMBERED_SOURCE check); see above.
    """
    from . import retrieval  # local: keeps the shipped coach import-light

    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")

    def fallback(reasons=(), completion=None, hits=(), abstained=False, cited=None):
        return CoachHint(approved[1], approved[0], "approved" if approved[1] else "generic", tuple(reasons),
                         completion, mode, tuple(hits), cited, abstained)

    hits: list = []
    if mode == "rag":
        if retriever is None:
            raise ValueError("rag mode needs a retriever")
        hits = retriever.search(retrieval.build_query(raju_sentence, learner_attempt), k=TOP_K)
        if not hits or (threshold is not None and hits[0].score < threshold):
            return fallback(("ABSTAINED",), hits=hits, abstained=True)
    elif mode == "oracle":
        if retriever is None or oracle_rule_id is None:
            raise ValueError("oracle mode needs a retriever and oracle_rule_id")
        hits = retrieval.oracle_hits(retriever.docs, oracle_rule_id)
    if provider is None:
        return fallback(hits=hits)

    situation = _situation(raju_sentence, learner_attempt)
    if mode == "blind":
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"{situation}\nएक इशारा दो।"}]
        need = ("hint",)
    else:
        msgs = [{"role": "system", "content": SYSTEM_RAG_FIXED if fixed else SYSTEM_RAG},
                {"role": "user", "content": f"{_sources_block(retriever, hits)}\n\n{situation}\nएक इशारा दो।"}]
        need = ("hint", "source")
    c = provider.complete(msgs, max_tokens=160)
    obj = parse_json(c.text, need) if c.ok else None
    text = obj["hint"].strip() if obj and isinstance(obj["hint"], str) else None
    reasons = _checks(item, text)
    if fixed:
        reasons += numbered_source_check(text)
    cited = None
    if mode != "blind":
        src = obj.get("source") if obj else None
        try:
            n = int(src)
        except (TypeError, ValueError):
            n = 0
        if 1 <= n <= len(hits):
            cited = hits[n - 1].rule_id
        else:
            reasons.append("CITATION_NOT_RETRIEVED")
    if reasons:
        return fallback(reasons, c, hits, cited=cited)
    return CoachHint(text, "l1_rule", "model", (), c, mode, tuple(hits), cited, False)
