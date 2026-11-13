"""Small-sample statistics for the final evaluations (TASKS.md tasks 16, 17). No dependencies.

- `wilson`: Wilson score 95% interval for a proportion (good at n = 29 and at 0 or n successes).
- `mcnemar`: exact (binomial) McNemar test for paired binary outcomes on the same cases.
"""
import math


def wilson(k: int, n: int, z: float = 1.959964) -> dict:
    """{"k", "n", "rate", "lo", "hi"}; rate/lo/hi are None when n == 0."""
    if n == 0:
        return {"k": k, "n": 0, "rate": None, "lo": None, "hi": None}
    if not 0 <= k <= n:
        raise ValueError("need 0 <= k <= n")
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    lo = 0.0 if k == 0 else max(0.0, centre - half)
    hi = 1.0 if k == n else min(1.0, centre + half)
    return {"k": k, "n": n, "rate": p, "lo": lo, "hi": hi}


def _binom_two_sided(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def mcnemar(x: list, y: list) -> dict:
    """Paired outcomes x[i], y[i] (truthy = success) on the same cases. b = x only, c = y only.
    Exact two-sided p (binomial on the discordant pairs)."""
    if len(x) != len(y):
        raise ValueError("paired lists must have the same length")
    b = sum(1 for a, d in zip(x, y) if a and not d)
    c = sum(1 for a, d in zip(x, y) if d and not a)
    return {"n_pairs": len(x), "x_only": b, "y_only": c, "p_exact": _binom_two_sided(b, c)}
