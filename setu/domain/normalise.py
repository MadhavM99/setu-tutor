"""Normaliser: what the learner typed -> canonical text in the target script (P-ARCH-05, P8b-06, X-CHK-01).

It never decides whether an answer is right; it reports how it got from the raw input to canonical text so the
checker can decide and the learner can be told.

- Canonical text: NFC, no invisible characters, digits as 0-9, punctuation as spaces, single spaces.
- Hindi keyboards: Devanagari is converted to Telugu letter by letter. Unicode lays both scripts out in the same
  order (offset 0x300), but the table here is built from matching character names, not the raw offset, because
  some offset slots hold unrelated characters (U+0904 -> a Telugu combining sign) and the e/o names differ
  (Hindi ए is Telugu's long ఏ). Characters with no Telugu twin (ॉ ॅ ॐ ...) are reported, never dropped silently.
  Nukta is dropped and chandrabindu becomes anusvara; both are reported in `notes`.
- Forgiveness (`match_forgiving`) for Hindi-keyboard habits, only when the learner typed Devanagari:
  ए/ओ for Telugu's short ఎ/ఒ (Hindi has no short e/o), and a final म for ం. Each use is reported.
  These conversion and forgiveness rules are drafts that need a native check (paper §9).
- Romanised input goes to an optional transliterator (IndicXlit adapter, P-DATA-07). Without one it is flagged,
  never guessed; with one, the result is a list of candidates the checker must treat as weaker evidence.
- Explanations ("why?") are cleaned but never converted.
"""
import dataclasses
import re
import unicodedata
from collections.abc import Iterable
from typing import Protocol

VERSION = "normaliser-1"
MAX_INPUT = 300
TARGETS = ("telugu", "devanagari")

DEVA = range(0x0900, 0x0980)
TELU = range(0x0C00, 0x0C80)
OFFSET = 0x300
INVISIBLE = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad"))
DIGITS = str.maketrans("०१२३४५६७८९౦౧౨౩౪౫౬౭౮౯", "01234567890123456789")

# Devanagari name -> Telugu name where the two scripts name the same sound differently.
_NAME_EXCEPTIONS = {
    "LETTER E": "LETTER EE", "LETTER O": "LETTER OO", "LETTER SHORT E": "LETTER E", "LETTER SHORT O": "LETTER O",
    "VOWEL SIGN E": "VOWEL SIGN EE", "VOWEL SIGN O": "VOWEL SIGN OO",
    "VOWEL SIGN SHORT E": "VOWEL SIGN E", "VOWEL SIGN SHORT O": "VOWEL SIGN O",
}


def _build_tables():
    d2t = {}
    for cp in DEVA:
        d, t = chr(cp), chr(cp + OFFSET)
        dn, tn = unicodedata.name(d, ""), unicodedata.name(t, "")
        if not dn or not tn or "DIGIT" in dn:
            continue
        dn, tn = dn.removeprefix("DEVANAGARI "), tn.removeprefix("TELUGU ")
        if _NAME_EXCEPTIONS.get(dn, dn) == tn:
            d2t[d] = t
    return d2t, {t: d for d, t in d2t.items()}


DEVA_TO_TELU, TELU_TO_DEVA = _build_tables()
_NUKTA, _CHANDRABINDU, _ANUSVARA = "़", "ँ", "ं"
_FOLD_EO = str.maketrans({"ఎ": "ఏ", "ఒ": "ఓ", "ె": "ే", "ొ": "ో"})
_FINAL_M = re.compile(r"(?<!్)మ(?= |$)")


class Transliterator(Protocol):
    version: str

    def transliterate(self, text: str, target: str) -> list[str]: ...


@dataclasses.dataclass(frozen=True)
class Normalised:
    text: str
    target_script: str
    input_script: str          # telugu | devanagari | latin | mixed | none
    status: str                # ok | empty | too_long | foreign_script | mixed_script | unconvertible
    #                            | needs_transliteration | transliterated
    converted: bool = False
    typed_devanagari: bool = False
    notes: tuple = ()
    unconvertible: tuple = ()
    candidates: tuple = ()
    transliterator_version: str | None = None
    normaliser_version: str = VERSION


@dataclasses.dataclass(frozen=True)
class Match:
    form: str
    forgiveness: tuple  # ("eo_length", "final_m") in that order, or ()


# ---------------------------------------------------------------- helpers


def canonical(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "").translate(INVISIBLE).translate(DIGITS)
    s = "".join(" " if unicodedata.category(ch).startswith("P") else ch for ch in s)
    return " ".join(s.split())


def _script(ch: str) -> str | None:
    cp = ord(ch)
    if cp in TELU:
        return "telugu"
    if cp in DEVA:
        return "devanagari"
    cat = unicodedata.category(ch)
    if not cat.startswith(("L", "M")):
        return None
    return "latin" if unicodedata.name(ch, "").startswith("LATIN") else "other"


def scripts_in(s: str) -> set[str]:
    return {sc for sc in map(_script, s) if sc}


def to_telugu(devanagari: str) -> str:
    """Exact twin mapping (for round trips and the reading aid). Unmapped characters are left as they are."""
    return "".join(DEVA_TO_TELU.get(ch, ch) for ch in devanagari)


def to_devanagari(telugu: str) -> str:
    return "".join(TELU_TO_DEVA.get(ch, ch) for ch in telugu)


def _convert(text: str, table: dict, block: range) -> tuple[str, tuple]:
    out, bad = [], []
    for ch in text:
        if ord(ch) in block:
            if ch in table:
                out.append(table[ch])
            else:
                bad.append(ch)
                out.append(ch)
        else:
            out.append(ch)
    return "".join(out), tuple(dict.fromkeys(bad))


def _clean_candidates(cands: Iterable[str], target: str) -> tuple:
    keep = []
    for c in cands or []:
        c = canonical(str(c))
        if c and scripts_in(c) == {target} and c not in keep:
            keep.append(c)
    return tuple(keep[:5])


# ---------------------------------------------------------------- entry points


def normalise_answer(raw: str, *, target_script: str, transliterator: Transliterator | None = None) -> Normalised:
    if target_script not in TARGETS:
        raise ValueError(f"target_script must be one of {TARGETS}")
    if len(raw or "") > MAX_INPUT:
        return Normalised("", target_script, "none", "too_long")
    text = canonical(raw)
    found = scripts_in(text)
    other = "devanagari" if target_script == "telugu" else "telugu"
    input_script = ("none" if not found else next(iter(found)) if len(found) == 1 else "mixed")
    base = {"target_script": target_script, "input_script": input_script}
    if not text:
        return Normalised("", status="empty", **base)
    if "other" in found:
        return Normalised("", status="foreign_script", **base)
    if found == {"latin"}:
        if transliterator is None:
            return Normalised("", status="needs_transliteration", **base)
        cands = _clean_candidates(transliterator.transliterate(text, target_script), target_script)
        return Normalised(cands[0] if cands else "", status="transliterated" if cands else "needs_transliteration",
                          candidates=cands, transliterator_version=getattr(transliterator, "version", None), **base)
    if "latin" in found:
        return Normalised("", status="mixed_script", **base)

    notes = []
    converted = other in found
    if target_script == "telugu" and converted:
        if _NUKTA in text:
            notes.append("nukta_dropped")
            text = text.replace(_NUKTA, "")
        if _CHANDRABINDU in text:
            notes.append("chandrabindu_as_anusvara")
            text = text.replace(_CHANDRABINDU, _ANUSVARA)
        text, bad = _convert(text, DEVA_TO_TELU, DEVA)
    elif target_script == "devanagari" and converted:
        text, bad = _convert(text, TELU_TO_DEVA, TELU)
    else:
        bad = ()
    status = "unconvertible" if bad else "ok"
    return Normalised(unicodedata.normalize("NFC", text), status=status, converted=converted,
                      typed_devanagari="devanagari" in found, notes=tuple(notes), unconvertible=bad, **base)


def normalise_explanation(raw: str) -> Normalised:
    """Explanations keep their script and punctuation: NFC, no invisible characters, single spaces."""
    text = " ".join(unicodedata.normalize("NFC", raw or "").translate(INVISIBLE).split())
    found = scripts_in(text)
    input_script = "none" if not found else next(iter(found)) if len(found) == 1 else "mixed"
    return Normalised(text, "any", input_script, "ok" if text else "empty")


def match_forgiving(n: Normalised, candidates: Iterable[str]) -> Match | None:
    """Match against accepted forms, forgiving Hindi-keyboard habits only for Devanagari-typed Telugu answers."""
    if n.status not in ("ok", "transliterated") or not n.text:
        return None
    forms = [canonical(c) for c in candidates]
    texts = n.candidates or (n.text,)
    for text in texts:
        if text in forms:
            return Match(text, ())
    if not (n.typed_devanagari and n.target_script == "telugu"):
        return None
    for text in texts:
        final_m = _FINAL_M.sub("ం", text)
        for form in forms:
            options = [(("eo_length",), text.translate(_FOLD_EO), form.translate(_FOLD_EO)),
                       (("final_m",), final_m, form),
                       (("eo_length", "final_m"), final_m.translate(_FOLD_EO), form.translate(_FOLD_EO))]
            for kinds, a, b in options:
                if a == b:
                    return Match(form, kinds)
    return None
