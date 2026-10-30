"""Leveler v0 (P-DIFF-01, X-LEV-01, learning-ladder.md §6): the item band is the hardest of four dimensions.

This is the paper's unvalidated baseline, kept so richer levelers can be compared with it (X-LEV-04). Bands are
L0–L5. Each dimension returns a band and the reason; a dimension the available data cannot measure returns no band
("unassessed") and the label is marked incomplete. Nothing is guessed.

- script: L0 if the text is only independent letters; L1 once it uses vowel signs, virama/conjuncts, anusvara or
  visarga. With the learner's known letters, letters they have not met are listed (the planner must not offer them).
- vocabulary: from corpus frequency ranks when available (rank ≤ 300 → L2, ≤ 1,000 → L3, ≤ 2,000 → L4, beyond → L5);
  words without a rank make it unassessed. IndicCorp ranks are not imported yet, so this is unassessed for now.
  With the learner's known words, the TMR is reported as well.
- word forms: unassessed until the morphological analyser is integrated (Phase 4). A surface suffix list would
  misfire (నేను "I" ends in ను) and would be unreviewed Telugu analysis.
- structure: one word → L2; two or three words → L3; four or more → L4; at least the band of the rule's contrast
  family (sentence-level contrasts → L4, clause contrasts → L5).

Thresholds and families are drafts awaiting teacher validation against independent band ratings (κ ≥ 0.6, M-51).
"""
import dataclasses
import unicodedata

from . import tokenize

VERSION = "leveler-v0"
BANDS = ("L0", "L1", "L2", "L3", "L4", "L5")
FREQUENCY_BANDS = ((300, "L2"), (1000, "L3"), (2000, "L4"))
FAMILY_BANDS = {
    "spelling": "L2",
    "agreement": "L4", "case": "L4", "copula": "L4", "gender": "L4", "negation": "L4", "possession": "L4",
    "postposition": "L4", "pronouns": "L4", "questions": "L4", "respect": "L4", "tense": "L4",
    "clauses": "L5", "clause": "L5",
}
SCRIPT_BLOCKS = {"telugu": range(0x0C00, 0x0C80), "devanagari": range(0x0900, 0x0980)}


@dataclasses.dataclass(frozen=True)
class Dimension:
    band: str | None
    reason: str


@dataclasses.dataclass(frozen=True)
class Level:
    band: str
    deciding: str
    reason: str
    dimensions: dict
    complete: bool
    unassessed: tuple
    unknown_letters: tuple = ()
    tmr: float | None = None
    leveler_version: str = VERSION
    tokenizer_version: str = tokenize.VERSION


def _rank(band: str | None) -> int:
    return -1 if band is None else BANDS.index(band)


def _script(text: str, script: str) -> Dimension:
    block = SCRIPT_BLOCKS[script]
    marks = [ch for ch in text if ord(ch) in block and unicodedata.category(ch).startswith("M")]
    if marks:
        return Dimension("L1", f"uses signs {''.join(dict.fromkeys(marks))}")
    return Dimension("L0", "independent letters only")


def _vocabulary(toks: list[str], ranks: dict | None) -> Dimension:
    if not ranks:
        return Dimension(None, "unassessed: no frequency ranks available")
    unranked = [t for t in toks if t not in ranks and not t.isdigit()]
    if unranked:
        return Dimension(None, f"unassessed: no frequency rank for {' '.join(dict.fromkeys(unranked))}")
    worst = max((ranks[t] for t in toks if not t.isdigit()), default=0)
    band = next((b for limit, b in FREQUENCY_BANDS if worst <= limit), "L5")
    return Dimension(band, f"rarest word has frequency rank {worst}")


def _structure(toks: list[str], family: str | None) -> Dimension:
    by_length = "L2" if len(toks) == 1 else "L3" if len(toks) <= 3 else "L4"
    reason = f"{len(toks)} words"
    fam = FAMILY_BANDS.get(family) if family else None
    if fam and _rank(fam) > _rank(by_length):
        return Dimension(fam, f"{reason}; contrast family '{family}'")
    return Dimension(by_length, reason)


def level(text: str, *, contrast_area: str | None = None, script: str = "telugu", frequency_ranks: dict | None = None,
          known_letters=None, known_words=None) -> Level:
    toks = tokenize.tokens(text)
    if not toks:
        raise ValueError("cannot level an empty text")
    dims = {
        "script": _script(text, script),
        "vocabulary": _vocabulary(toks, frequency_ranks),
        "word_forms": Dimension(None, "unassessed: needs the morphological analyser (Phase 4)"),
        "structure": _structure(toks, contrast_area),
    }
    assessed = {k: d for k, d in dims.items() if d.band is not None}
    deciding = max(assessed, key=lambda k: _rank(assessed[k].band))
    unassessed = tuple(k for k, d in dims.items() if d.band is None)
    reason = f"{deciding}: {dims[deciding].reason}"
    if unassessed:
        reason += f"; unassessed: {', '.join(unassessed)}"
    block = SCRIPT_BLOCKS[script]
    unknown = ()
    if known_letters is not None:
        unknown = tuple(dict.fromkeys(ch for ch in unicodedata.normalize("NFC", text)
                                      if ord(ch) in block and ch not in known_letters))
    tmr = tokenize.tmr(text, known=known_words).value if known_words is not None else None
    return Level(dims[deciding].band, deciding, reason, dims, not unassessed, unassessed, unknown, tmr)


LEVELERS = {VERSION: level}
