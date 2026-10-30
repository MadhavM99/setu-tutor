"""Deterministic checker. The answer-checking logic lands in slice 2.2; this module already owns the only way
to issue a Verdict, so nothing else in the codebase can produce one (TS-AUTH-01/02)."""
from .verdict import _CHECKER_CAPABILITY, Verdict


def issue_verdict(*, attempt_id, outcome, kind, reason_code, checker_version, false_alarm=False) -> Verdict:
    return Verdict._mint_verdict(_CHECKER_CAPABILITY, attempt_id=attempt_id, outcome=outcome, kind=kind,
                                 reason_code=reason_code, checker_version=checker_version,
                                 false_alarm=false_alarm)
