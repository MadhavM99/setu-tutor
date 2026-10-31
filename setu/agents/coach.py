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
