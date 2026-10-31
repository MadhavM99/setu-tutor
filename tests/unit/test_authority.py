"""TS-AUTH-01..03, 05: only checker verdicts and signed teacher resolutions can reach the OutcomeWriter,
and no agent, tool or offline pipeline code can reach it at all (architecture.md §2, ADR-0004)."""
import ast
import dataclasses
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{a.name}" for a in node.names)
    return names


def _python_files(*dirs):
    for d in dirs:
        yield from (ROOT / d).rglob("*.py")


# ---------------------------------------------------------------- TS-AUTH-01: import boundaries

FORBIDDEN_FROM_MODEL_SIDE = ("setu.store.outcome_writer", "setu.store.resolution", "setu.store.grants")


@pytest.mark.parametrize("package", ["setu/agents", "setu/memory", "setu/speech", "setu/domain", "pipeline"])
def test_model_side_packages_cannot_reach_the_writer(package):
    offenders = [
        (p.relative_to(ROOT).as_posix(), name)
        for p in _python_files(package)
        for name in _imports(p)
        if name.startswith(FORBIDDEN_FROM_MODEL_SIDE)
    ]
    assert offenders == []


def test_only_the_checker_mints_verdicts():
    allowed = {"setu/domain/checker.py", "setu/domain/verdict.py"}
    users = {
        p.relative_to(ROOT).as_posix()
        for p in _python_files("setu", "pipeline")
        if any(m in p.read_text(encoding="utf-8") for m in ("_mint_verdict", "_CHECKER_CAPABILITY", "issue_verdict"))
    }
    # issue_verdict is the checker's minting entry point; until the real checker lands (slice 2.2) only tests use it.
    assert users <= allowed


def test_only_the_scheduler_mints_forget_decisions():
    allowed = {"setu/domain/scheduler.py"}
    users = {
        p.relative_to(ROOT).as_posix()
        for p in _python_files("setu", "pipeline")
        if "_SCHEDULER_CAPABILITY" in p.read_text(encoding="utf-8")
    }
    assert users <= allowed


def test_only_the_diagnostic_mints_placement_decisions():
    users = {
        p.relative_to(ROOT).as_posix()
        for p in _python_files("setu", "pipeline")
        if "object.__new__(PlacementDecision)" in p.read_text(encoding="utf-8")
    }
    assert users == {"setu/domain/placement.py"}


def test_writer_credentials_are_read_only_by_the_writer():
    users = {
        p.relative_to(ROOT).as_posix()
        for p in _python_files("setu", "pipeline")
        if "SETU_WRITER_DATABASE_URL" in p.read_text(encoding="utf-8")
    }
    assert users <= {"setu/store/outcome_writer.py"}


# ---------------------------------------------------------------- TS-AUTH-02: verdicts cannot be forged


def _a_real_verdict(outcome="correct", kind="fix"):
    from setu.domain.checker import _issue_verdict as issue_verdict  # tests mint arbitrary verdicts

    return issue_verdict(attempt_id=uuid.uuid4(), outcome=outcome, kind=kind, reason_code="accepted_form")


def test_verdict_cannot_be_constructed_directly():
    from setu.domain.verdict import Verdict

    with pytest.raises(TypeError):
        Verdict(attempt_id=uuid.uuid4(), outcome="correct", kind="fix", reason_code="x", checker_version="v")


def test_verdict_cannot_be_copied_into_a_different_outcome():
    v = _a_real_verdict(outcome="wrong")
    with pytest.raises(dataclasses.FrozenInstanceError):
        v.outcome = "correct"  # type: ignore[misc]
    with pytest.raises(TypeError):
        dataclasses.replace(v, outcome="correct")


def test_verdict_rejects_values_outside_the_four_outcomes():
    from setu.domain.checker import _issue_verdict as issue_verdict  # tests mint arbitrary verdicts

    with pytest.raises(ValueError):
        issue_verdict(attempt_id=uuid.uuid4(), outcome="approved", kind="fix", reason_code="x")


def test_writer_rejects_anything_that_is_not_a_minted_verdict():
    from setu.domain.verdict import Verdict
    from setu.store.outcome_writer import NotAVerdict, OutcomeWriter

    class Fake:  # duck-typed lookalike
        attempt_id = uuid.uuid4()
        outcome = "correct"
        kind = "fix"
        reason_code = "x"
        checker_version = "v"

    forged = object.__new__(Verdict)  # bypasses __init__ entirely
    for bogus in ({"outcome": "correct"}, Fake(), forged, "correct"):
        with pytest.raises(NotAVerdict):
            OutcomeWriter.validate_verdict(bogus)
    OutcomeWriter.validate_verdict(_a_real_verdict())


# ---------------------------------------------------------------- TS-AUTH-05: teacher resolutions are signed

KEY = b"test-resolution-key-0123456789abcdef"


def _resolution(**over):
    from setu.store.resolution import TeacherResolution

    base = {"queue_item_id": uuid.uuid4(), "teacher_id": uuid.uuid4(), "outcome": "correct", "note_hi": "ठीक है"}
    base.update(over)
    return TeacherResolution.sign(key=KEY, **base)


def test_signed_resolution_verifies():
    r = _resolution()
    assert r.verify(KEY)


def test_tampered_or_wrongly_keyed_resolution_fails():
    import dataclasses as dc

    from setu.store.resolution import BadSignature

    r = _resolution(outcome="wrong")
    tampered = dc.replace(r, outcome="correct")
    with pytest.raises(BadSignature):
        tampered.verify(KEY)
    with pytest.raises(BadSignature):
        r.verify(b"another-key-another-key-another-key!")


def test_resolution_outcome_must_be_a_settled_verdict():
    with pytest.raises(ValueError):
        _resolution(outcome="unsure")


def test_signing_key_must_be_long_enough():
    from setu.store.resolution import TeacherResolution

    with pytest.raises(ValueError):
        TeacherResolution.sign(key=b"short", queue_item_id=uuid.uuid4(), teacher_id=uuid.uuid4(),
                               outcome="correct", note_hi=None)


# ---------------------------------------------------------------- forget decisions


def test_forget_decision_requires_predicted_recall_below_half():
    from setu.domain.scheduler import decide_forget

    assert decide_forget(learner_id=uuid.uuid4(), rule_id="HI-TE-001", predicted_recall=0.49,
                         tracker_version="t") is not None
    assert decide_forget(learner_id=uuid.uuid4(), rule_id="HI-TE-001", predicted_recall=0.5,
                         tracker_version="t") is None


def test_forget_decision_cannot_be_constructed_directly():
    from setu.domain.scheduler import ForgetDecision

    with pytest.raises(TypeError):
        ForgetDecision(learner_id=uuid.uuid4(), rule_id="HI-TE-001", predicted_recall=0.1, tracker_version="t")
