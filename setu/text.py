"""Small text helpers shared by the checker and (later) the leak filter."""
from __future__ import annotations
import re
import unicodedata

_STRIP = "।॥.,!?;:'\"()[]{}“”‘’ \t\n"


def normalize(s: str) -> str:
    """Unicode NFC, no zero-width joiners, no surrounding punctuation/danda, single spaces."""
    s = unicodedata.normalize("NFC", s or "")
    s = s.replace("‌", "").replace("‍", "")
    s = re.sub(r"\s+", " ", s).strip(_STRIP)
    return s


def script_of(s: str) -> str:
    """'telugu', 'devanagari', 'latin', 'mixed' or 'none' — used to give a helpful message, never to grade."""
    has = {"telugu": any("ఀ" <= c <= "౿" for c in s),
           "devanagari": any("ऀ" <= c <= "ॿ" for c in s),
           "latin": any(c.isascii() and c.isalpha() for c in s)}
    found = [k for k, v in has.items() if v]
    return found[0] if len(found) == 1 else ("none" if not found else "mixed")


def deva_to_telugu(s: str) -> str:
    """Type Telugu with a Hindi keyboard: Devanagari and Telugu share one letter order (Unicode/ISCII),
    so each Devanagari letter/sign maps to its Telugu twin by a fixed offset (पुस्तकं -> పుస్తకం).
    Characters outside the Devanagari block (spaces, digits, punctuation) are kept. Nukta is dropped."""
    out = []
    for c in s:
        o = ord(c)
        if c == "़":                       # nukta (ज़): Telugu has none
            continue
        out.append(chr(o + 0x300) if 0x0900 <= o <= 0x097F and o not in (0x0964, 0x0965) else c)
    return "".join(out)


def telugu_to_deva(s: str) -> str:
    """The reverse of deva_to_telugu: how a Telugu word reads in Devanagari (కమలం -> कमलं)."""
    return "".join(chr(ord(c) - 0x300) if 0x0C00 <= ord(c) <= 0x0C7F else c for c in s)


def reading_forms(te: str) -> list:
    """Every way a Hindi speaker may fairly write how a Telugu word sounds. Built by rule, so any word can be
    checked exactly, with no model: the letter-by-letter twin (కమలం -> कमलं), plus the usual ways of writing
    the ending: final ం as ं / म / म्, a final consonant with its 'a' said long (మామ -> माम / मामा),
    and final ि / ु written long (पुलि / पुली)."""
    d = normalize(telugu_to_deva(te))
    forms = {d}
    if d.endswith("ं"):
        forms |= {d[:-1] + "म", d[:-1] + "म्"}
    elif d and 0x0915 <= ord(d[-1]) <= 0x0939:
        forms.add(d + "ा")
    if d.endswith("ि"):
        forms.add(d[:-1] + "ी")
    if d.endswith("ु"):
        forms.add(d[:-1] + "ू")
    return sorted(forms)


_EO = str.maketrans({"ే": "ె", "ో": "ొ", "ఏ": "ఎ", "ఓ": "ఒ"})


def fold_eo(s: str) -> str:
    """Hindi has no short e/o, so on a Hindi keyboard े/ो always become Telugu's LONG ే/ో. For whole sentences we
    treat short and long e/o as the same, or every correct answer typed on a Hindi keyboard would fail."""
    return (s or "").translate(_EO)
