"""The checker's verdict: the only kind of evidence the OutcomeWriter accepts besides a signed teacher
resolution (architecture.md §2, ADR-0004).

A Verdict cannot be built with its constructor, copied with changes, or mutated. Only the checker module mints
one (through `_mint_verdict` with the checker capability), and every minted instance is registered so a
lookalike or an `object.__new__` forgery is rejected by `is_minted`. Python cannot stop determined in-process
code; the import-boundary tests, the database grants and the classmate-state trigger are the other layers.
"""
import dataclasses
import uuid
import weakref

OUTCOMES = ("correct", "partial", "wrong", "unsure")
KINDS = ("fix", "no_error", "explanation", "own", "recall", "recognition")

_CHECKER_CAPABILITY = object()
_MINTED: "weakref.WeakSet[Verdict]" = weakref.WeakSet()


class Verdict:
    __slots__ = ("__weakref__", "attempt_id", "checker_version", "false_alarm", "kind", "outcome", "reason_code")

    def __init__(self, *args, **kwargs):
        raise TypeError("Verdict is issued only by the checker")

    @classmethod
    def _mint_verdict(cls, capability, *, attempt_id, outcome, kind, reason_code, checker_version,
                      false_alarm=False):
        if capability is not _CHECKER_CAPABILITY:
            raise TypeError("Verdict is issued only by the checker")
        if outcome not in OUTCOMES:
            raise ValueError(f"outcome must be one of {OUTCOMES}, got {outcome!r}")
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}, got {kind!r}")
        if not checker_version:
            raise ValueError("checker_version is required")
        v = object.__new__(cls)
        for name, value in (("attempt_id", uuid.UUID(str(attempt_id))), ("outcome", outcome), ("kind", kind),
                            ("reason_code", reason_code), ("checker_version", checker_version),
                            ("false_alarm", bool(false_alarm))):
            object.__setattr__(v, name, value)
        _MINTED.add(v)
        return v

    def __setattr__(self, name, value):
        raise dataclasses.FrozenInstanceError(f"cannot assign to field {name!r}")

    def __delattr__(self, name):
        raise dataclasses.FrozenInstanceError(f"cannot delete field {name!r}")

    def __repr__(self):
        return (f"Verdict(attempt_id={self.attempt_id}, outcome={self.outcome!r}, kind={self.kind!r}, "
                f"reason_code={self.reason_code!r}, checker_version={self.checker_version!r})")


def is_minted(obj) -> bool:
    return type(obj) is Verdict and obj in _MINTED
