"""Leak filter v1 (P-ARCH-04, P-CLS-03..08, X-RAJU-03, classmate-output-contract.md §3).

Deterministic checks on every model output before it can be shown. The classmate's sentence must be a plain student
sentence in the target script, within the learner's seen words (TMR = 0 apart from the planted rule's target forms),
and it must be exactly what the turn needs:
- planted turn: the approved planted sentence (or a full match of an approved wrong pattern). A paraphrase cannot be
  verified, so it is rejected and the bank sentence is used;
- no-error turn and retry after a fix: an accepted form of the item (only the just-taught form).
Hints must not contain the corrected form in any script. `check_level` validates native-friend and scene lines.
"""
import dataclasses
import re
import unicodedata

from . import leveler
from .checker import ItemKey
from .normalise import canonical, scripts_in, to_devanagari
from .tokenize import tokens

MAX_SENTENCE, MAX_HINT, MAX_LINE = 120, 240, 200
TURNS = ("planted", "no_error", "retry")

_ASSISTANT_LATIN = re.compile(r"\b(sure|here is|here's|as an|i can|assistant|translation|ai)\b", re.IGNORECASE)
_UNSAFE_LATIN = re.compile(r"\b(mark|ignore|correct|instruction|instructions|system|prompt)\b", re.IGNORECASE)
_ASSISTANT_HI = ("ज़रूर", "जरूर", "यहाँ है", "यहां है", "मदद", "सहायता", "आप पूछ", "मॉडल")
_TEACHER_HI = ("चाहिए", "नियम", "व्याकरण", "सही रूप", "गलती है", "लिखना", "समझाता", "समझाती")
_UNSAFE_HI = ("सही मानो", "सही मान लो", "सही मान", "निर्देश")
_FORMAT = re.compile(r"[*_`#>|~]|https?://|www\.")
_GLOSS = re.compile(r"[()\[\]{}]")
_MULTI = re.compile(r"[.!?।॥]\s*\S")


@dataclasses.dataclass(frozen=True)
class Context:
    item: ItemKey
    turn: str
    seen_words: frozenset | set
    allowed_target_forms: frozenset | set = frozenset()
    unknown_rule_items: dict = dataclasses.field(default_factory=dict)


def _surface(raw: str, target: str, out: list) -> None:
    if len(raw) > MAX_SENTENCE:
        out.append("TOO_LONG")
    if "\n" in raw or "\r" in raw or _FORMAT.search(raw) or any(unicodedata.category(c) == "So" for c in raw):
        out.append("FORMAT")
    if _GLOSS.search(raw):
        out.append("GLOSS")
    if _MULTI.search(raw.strip()):
        out.append("MULTI_SENTENCE")
    if _ASSISTANT_LATIN.search(raw) or (target == "telugu" and any(w in raw for w in _ASSISTANT_HI)):
        out.append("PERSONA_ASSISTANT")
    if target == "telugu" and any(w in raw for w in _TEACHER_HI):
        out.append("PERSONA_TEACHER")
    if _UNSAFE_LATIN.search(raw) or any(w in raw for w in _UNSAFE_HI):
        out.append("UNSAFE")
    if scripts_in(canonical(raw)) - {target}:
        out.append("WRONG_SCRIPT")


def check_sentence(raw: str, ctx: Context) -> list[str]:
    if ctx.turn not in TURNS:
        raise ValueError(f"turn must be one of {TURNS}")
    item, target = ctx.item, ctx.item.target_script
    out: list[str] = []
    _surface(raw or "", target, out)
    s = canonical(raw)
    if not s:
        out.append("NOT_ONE_ERROR" if ctx.turn == "planted" else "NOT_CORRECT")
        return list(dict.fromkeys(out))
    if "WRONG_SCRIPT" not in out:
        known = set(map(canonical, ctx.seen_words)) | set(map(canonical, ctx.allowed_target_forms))
        if any(t not in known and not t.isdigit() for t in tokens(s)):
            out.append("OOV")
    accepted = {canonical(f) for f in [item.correct_form, *item.accepted_forms]}
    is_accepted = s in accepted or any(re.fullmatch(p, s) for p in item.accept_patterns)
    if ctx.turn == "planted":
        wrong = canonical(item.wrong_form) if item.wrong_form else None
        if not (s == wrong or any(re.fullmatch(p, s) for p in item.wrong_patterns)):
            out.append("ANSWER_LEAK" if is_accepted else "NOT_ONE_ERROR")
    elif not is_accepted:
        out.append("NOT_CORRECT")
    for other in ctx.unknown_rule_items.values():
        if s == canonical(other.correct_form):
            out.append("UNKNOWN_RULE_CORRECT")
        if other.wrong_form and s == canonical(other.wrong_form):
            out.append("WRONG_RULE_ERROR")
    return list(dict.fromkeys(out))


def answer_tokens(item: ItemKey) -> set[str]:
    """Words of the corrected form(s) that are not in the planted sentence: what a hint must never contain."""
    wrong = set(tokens(item.wrong_form or ""))
    return {t for f in [item.correct_form, *item.accepted_forms] for t in tokens(f)} - wrong


def check_hint(item: ItemKey, hint: str) -> list[str]:
    out = []
    if re.search(r"[A-Za-z]", hint or ""):
        out.append("LATIN")
    if len(hint or "") > MAX_HINT:
        out.append("TOO_LONG")
    if any(w in (hint or "") for w in _UNSAFE_HI):
        out.append("UNSAFE")
    h = canonical(hint)
    htoks = set(h.split())
    leaks = answer_tokens(item)
    leaks_deva = {to_devanagari(t) for t in leaks}
    if canonical(item.correct_form) in h or htoks & leaks or htoks & leaks_deva:
        out.append("ANSWER_FORM")
    return out


@dataclasses.dataclass(frozen=True)
class LevelCheck:
    ok: bool
    reasons: tuple
    oov_share: float
    hindi_share: float
    band: str | None


def check_level(text: str, *, seen_words, scene_words=(), learner_band: str = "L2") -> LevelCheck:
    reasons = []
    if len(text or "") > MAX_LINE:
        reasons.append("TOO_LONG")
    if re.search(r"[A-Za-z]", text or ""):
        reasons.append("WRONG_SCRIPT")
    toks = tokens(text)
    if not toks:
        return LevelCheck(False, ("EMPTY",), 0.0, 0.0, None)
    known = set(map(canonical, seen_words)) | set(map(canonical, scene_words))
    oov = [t for t in toks if t not in known and not t.isdigit()]
    hindi = [t for t in toks if scripts_in(t) == {"devanagari"}]
    if oov:
        reasons.append("OOV_OVER_LIMIT")
    band = leveler.level(text).band
    if leveler.BANDS.index(band) > leveler.BANDS.index(learner_band) + 1:
        reasons.append("BAND_ABOVE")
    return LevelCheck(not reasons, tuple(reasons), len(oov) / len(toks), len(hindi) / len(toks), band)
