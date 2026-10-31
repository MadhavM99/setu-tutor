"""Rater agreement (F2; X-TCH-03, M-29): Cohen's kappa for two raters on nominal labels. Pure."""
import dataclasses
from collections import Counter

MIN_N = 10


@dataclasses.dataclass(frozen=True)
class KappaResult:
    kappa: float | None
    n: int
    reason: str | None = None  # too_few | undefined


def cohen_kappa(a, b) -> float | None:
    """(p_o - p_e) / (1 - p_e); None when chance agreement is 1 (both raters always give the same one label)."""
    if len(a) != len(b):
        raise ValueError("both raters must label the same items")
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return None if pe == 1 else (po - pe) / (1 - pe)


def report(a, b) -> KappaResult:
    if len(a) < MIN_N:
        return KappaResult(None, len(a), "too_few")
    k = cohen_kappa(a, b)
    return KappaResult(k, len(a), None if k is not None else "undefined")
