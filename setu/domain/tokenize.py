"""Tokenizer and Token Miss Rate (E-16, P-DIFF-03, paper Eq. 1).

tokenizer-1: canonical text (normaliser) split on whitespace into surface forms. Clitics and suffixes are not split
(ఇంట్లో stays one token); a morphological analyser may replace this in Phase 4 under a new version, and every TMR
records the tokenizer version so values stay comparable.

TMR(s) = |{tokens of s not in VL}| / |tokens of s|, counted over token occurrences. Tokens exempt from the count:
the allowed target forms of the planted rule (passed as `exempt`) and pure numbers.
"""
import dataclasses

from .normalise import canonical

VERSION = "tokenizer-1"


def tokens(text: str) -> list[str]:
    return canonical(text).split()


@dataclasses.dataclass(frozen=True)
class Tmr:
    value: float
    oov: tuple
    n_tokens: int
    tokenizer_version: str = VERSION


def tmr(text: str, *, known, exempt=()) -> Tmr:
    toks = tokens(text)
    if not toks:
        raise ValueError("TMR is undefined for an empty sentence")
    known, exempt = set(map(canonical, known)), set(map(canonical, exempt))
    missing = [t for t in toks if t not in known and t not in exempt and not t.isdigit()]
    return Tmr(len(missing) / len(toks), tuple(dict.fromkeys(missing)), len(toks))
