"""The leak filter: decides whether a line Raju (or a model writing for Raju) may show the learner.
Pure rules, no model. A line is shown only if it passes ALL five checks:

  1 UNSEEN_TELUGU  it contains a Telugu letter the learner has not been shown in any lesson yet
  2 NOT_ONE_CLAIM  it does not state exactly the one planned claim ("ఖ = क"), or it adds another claim
  3 UNKNOWN_UNIT   it mentions something from a unit Raju has not been taught (only the planned one is allowed)
  4 ANSWER_LEAK    it contains the right answer on a mistake turn
  5 EXPLANATION    it explains or teaches ("क्योंकि", "नियम", "because", ...)
plus FORMAT: one short line, no English letters.

Raju's REACTION after an answer has its own check (check_reaction): same FORMAT / UNSEEN_TELUGU / EXPLANATION,
no other item (OTHER_ITEM); when he is confused he may not give or hint the answer and writes no Telugu
(ANSWER_LEAK); when he thanks or celebrates he may not repeat his old mistake (WRONG_CLAIM).
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List
from .contracts import Item, Unit
from .text import normalize

EXPLAIN = ["क्योंकि", "नियम", "मतलब", "व्याकरण", "ఎందుకంటే", "నియమం", "because", "rule", "means", "grammar"]
MAX_LEN = 140
NAMES_OK = re.compile(r"\b(Hindi|Telugu|Raju|OK|ok)\b")       # harmless names in English letters


def has_english(n: str) -> bool:
    return any(c.isascii() and c.isalpha() for c in NAMES_OK.sub("", n))


@dataclass
class Decision:
    ok: bool
    reasons: List[str] = field(default_factory=list)


def telugu_chars(s: str) -> set:
    return {c for c in s if "ఀ" <= c <= "౿"}


def seen_telugu(units: Iterable[Unit], introduced: Iterable[str]) -> set:
    """Every Telugu letter/sign shown in the lessons the learner has had."""
    ids = set(introduced)
    out: set = set()
    for u in units:
        if u.unit_id in ids:
            for line in u.lesson:
                out |= telugu_chars(line.telugu)
    return out


def check_line(line: str, item: Item, claim: str, mistake: bool, units: List[Unit],
               raju: Dict[str, str], seen: set, unit_id: str, seen_words: set = None) -> Decision:
    """`claim` is what Raju must say this item is: his planted mistake (mistake=True) or the right answer
    (mistake=False: a spot check, allowed only for units Raju already knows)."""
    reasons: List[str] = []
    n = normalize(line)
    limit = 220 if item.kind == "sentence" else MAX_LEN
    if not n or "\n" in line.strip() or len(n) > limit or has_english(n):
        reasons.append("FORMAT")
    if telugu_chars(n) - seen:
        reasons.append("UNSEEN_TELUGU")
    if item.kind == "sentence" and seen_words is not None:
        # paper Eq. 1: Token Miss Rate = 0 — every Telugu word is one the learner has met, apart from the words
        # of the planted sentence itself
        allowed = set(seen_words) | {normalize(w) for w in claim.split()}
        words = [normalize(w) for w in re.findall(r"[\u0C00-\u0C7F]+", n)]
        if any(w not in allowed for w in words):
            reasons.append("UNSEEN_TELUGU")
        if mistake:                                       # a word of the right answer that is not in his mistake
            right = {normalize(w) for a in item.accepted for w in a.split()} - {normalize(w) for w in claim.split()}
            if any(w in right for w in words):
                reasons.append("ANSWER_LEAK")
    if normalize(item.prompt) not in n or normalize(claim) not in n:
        reasons.append("NOT_ONE_CLAIM")
    for u in units:                                      # any other item's prompt = a second claim
        for it in [u.check, *u.items]:
            if normalize(it.prompt) == normalize(item.prompt):
                continue
            if _as_token(n, it.prompt):
                known = u.unit_id == unit_id or raju.get(u.unit_id) in ("taught", "learning")
                reasons.append("NOT_ONE_CLAIM" if known else "UNKNOWN_UNIT")
    if mistake and any(_as_token(n, a) for a in item.accepted):
        reasons.append("ANSWER_LEAK")
    if not mistake and raju.get(unit_id) not in ("taught", "learning"):
        reasons.append("UNKNOWN_UNIT")                    # Raju can't state a correct form he wasn't taught
    low = n.lower()
    if any(m.lower() in low for m in EXPLAIN):
        reasons.append("EXPLANATION")
    return Decision(ok=not reasons, reasons=sorted(set(reasons)))


def _format_ok(line: str, n: str) -> bool:
    return bool(n) and "\n" not in line.strip() and len(n) <= MAX_LEN and not has_english(n)


def check_reaction(line: str, item, event: str, units: List[Unit], seen: set) -> Decision:
    """event: 'fixed' | 'knows' | 'spot_ok' (Raju thanks or celebrates) or 'doubt' (the answer was wrong)."""
    reasons: List[str] = []
    n = normalize(line)
    if not _format_ok(line, n):
        reasons.append("FORMAT")
    if telugu_chars(n) - seen:
        reasons.append("UNSEEN_TELUGU")
    own = normalize(item.prompt) if item is not None else None
    for u in units:
        for it in [u.check, *u.items]:
            if normalize(it.prompt) != own and _as_token(n, it.prompt):
                reasons.append("OTHER_ITEM")
    if event == "doubt":
        if telugu_chars(n) or (item is not None and any(_as_token(n, a) for a in item.accepted)):
            reasons.append("ANSWER_LEAK")
    elif item is not None and any(_as_token(n, w) for w in [item.raju_wrong, *item.wrong_forms]):
        reasons.append("WRONG_CLAIM")
    if any(m.lower() in n.lower() for m in EXPLAIN):
        reasons.append("EXPLANATION")
    return Decision(ok=not reasons, reasons=sorted(set(reasons)))


TRICK_MAX = 200


def check_trick(text: str, line) -> Decision:
    """A memory trick the model wrote for one lesson card. Rules only:
    FORMAT (one line, Hindi, no English letters, short) · OTHER_TELUGU (any Telugu letter not in this card) ·
    MISSING (must name this letter and its sound) · WRONG_PAIR (pairs this letter with a different sound) ·
    EXPLANATION is allowed here: teaching is the point of a trick."""
    reasons: List[str] = []
    n = normalize(text)
    if not n or "\n" in text.strip() or len(n) > TRICK_MAX or has_english(n):
        reasons.append("FORMAT")
    te = normalize(line.telugu)
    if telugu_chars(n) - telugu_chars(te):
        reasons.append("OTHER_TELUGU")
    hi = normalize(line.hindi).split(" ")[0]
    if te not in n or hi not in n:
        reasons.append("MISSING")
    for m in re.finditer(re.escape(te) + r"\s*(?:=|→|->|माने|यानी|मतलब)\s*([^\s,।!?]+)", n):
        if not normalize(m.group(1)).startswith(hi):
            reasons.append("WRONG_PAIR")
    return Decision(ok=not reasons, reasons=sorted(set(reasons)))


DIDI_MAX = 450


def check_didi(text: str, seen: set, pairs: Dict[str, str], avoid: Iterable[str] = ()) -> Decision:
    """What Didi (the AI teacher) says. Rules only:
    FORMAT (Hindi, no English letters, not too long) · UNSEEN_TELUGU (only letters the learner has been shown) ·
    WRONG_PAIR (writes 'X = Y' where Y is not X's sound in the lessons) · ANSWER_LEAK (a hint gives the answer)."""
    reasons: List[str] = []
    n = normalize(text)
    if not n or len(n) > DIDI_MAX or has_english(n):
        reasons.append("FORMAT")
    if telugu_chars(n) - seen:
        reasons.append("UNSEEN_TELUGU")
    for te, hi in pairs.items():
        for m in re.finditer(r"(?<![\u0C00-\u0C7F])" + re.escape(te) + r"(?![\u0C00-\u0C7F])\s*(?:=|→|->)\s*([^\s,।!?]+)", n):
            if not normalize(m.group(1)).startswith(normalize(hi).split(" ")[0]):
                reasons.append("WRONG_PAIR")
    if any(_as_token(n, a) for a in avoid):
        reasons.append("ANSWER_LEAK")
    return Decision(ok=not reasons, reasons=sorted(set(reasons)))


def _as_token(text: str, piece: str) -> bool:
    """`piece` appears in `text` as its own token (so ख is not found inside खाना)."""
    p = normalize(piece)
    if not p:
        return False
    return re.search(r"(?<![ऀ-ॿఀ-౿])" + re.escape(p) + r"(?![ऀ-ॿఀ-౿])", text) is not None
