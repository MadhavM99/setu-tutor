"""OutcomeWriter: the only code that writes learning state (P-SESS-11, P-ARCH-11, ADR-0004, E-01).

It accepts exactly three kinds of evidence:
- a `Verdict` minted by the checker;
- a `TeacherResolution` signed by an authenticated teacher session;
- a `ForgetDecision` issued by the scheduler.

Every call runs in one transaction under the `setu_writer` role (`SET LOCAL ROLE`), so it never uses more than
writer privileges even if it connects as the owner. Every change is appended to the event ledger, and the
`classmate_rule_state` trigger re-checks in the database that each change is backed by that evidence.

Mastery and FSRS updates join here in slice 2.6; until then the writer records verdicts, the teacher queue,
the classmate's knowledge and the ledger.
"""
import dataclasses
import json
import os
import uuid

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from setu.domain import scheduler
from setu.domain.verdict import is_minted

from .resolution import TeacherResolution


class NotAVerdict(TypeError):
    """Raised for anything that is not a verdict minted by the checker."""


class ConflictingVerdict(Exception):
    """The attempt already has a different verdict; verdicts are immutable."""


class ResolutionRefused(Exception):
    """The resolution is well signed but cannot be applied (not a teacher, item missing or already settled)."""


@dataclasses.dataclass(frozen=True)
class VerdictRecord:
    verdict_id: uuid.UUID
    queue_item_id: uuid.UUID | None
    classmate_change: str | None
    classmate_event_id: int | None


@dataclasses.dataclass(frozen=True)
class ResolutionRecord:
    resolution_id: uuid.UUID
    resolution_event_id: int
    classmate_change: str | None
    classmate_event_id: int | None


class OutcomeWriter:
    def __init__(self, engine: Engine | None = None, *, resolution_key: bytes | None = None):
        self._engine = engine or create_engine(os.environ["SETU_WRITER_DATABASE_URL"])
        key = resolution_key if resolution_key is not None else os.environ.get("SETU_RESOLUTION_KEY", "").encode()
        self._resolution_key = key

    # ------------------------------------------------------------------ plumbing

    def _tx(self):
        engine = self._engine.execution_options(isolation_level="READ COMMITTED")
        return _WriterTx(engine)

    def effective_role(self) -> str:
        with self._tx() as c:
            return c.execute(text("SELECT current_user")).scalar_one()

    @staticmethod
    def validate_verdict(v) -> None:
        if not is_minted(v):
            raise NotAVerdict("the OutcomeWriter accepts only verdicts issued by the checker")

    @staticmethod
    def _event(c: Connection, actor: str, event_type: str, payload: dict) -> int:
        return c.execute(
            text("INSERT INTO event_ledger (actor, event_type, payload) VALUES (:a, :t, CAST(:p AS jsonb)) "
                 "RETURNING id"),
            {"a": actor, "t": event_type, "p": json.dumps(payload, ensure_ascii=False, sort_keys=True)},
        ).scalar_one()

    # ------------------------------------------------------------------ verdicts

    def record_verdict(self, v) -> VerdictRecord:
        self.validate_verdict(v)
        with self._tx() as c:
            existing = c.execute(
                text("SELECT v.id, v.outcome, v.kind, v.reason_code, v.checker_version, q.id AS queue_id "
                     "FROM verdict v LEFT JOIN teacher_queue_item q ON q.verdict_id = v.id "
                     "WHERE v.attempt_id = :a"), {"a": v.attempt_id}).first()
            if existing:
                same = (existing.outcome, existing.kind, existing.reason_code, existing.checker_version) == (
                    v.outcome, v.kind, v.reason_code, v.checker_version)
                if not same:
                    raise ConflictingVerdict(f"attempt {v.attempt_id} already has verdict {existing.outcome!r}")
                return VerdictRecord(existing.id, existing.queue_id, None, None)

            context = self._attempt_context(c, v.attempt_id)
            verdict_id = c.execute(
                text("INSERT INTO verdict (attempt_id, outcome, kind, reason_code, checker_version, false_alarm) "
                     "VALUES (:a, :o, :k, :r, :cv, :fa) RETURNING id"),
                {"a": v.attempt_id, "o": v.outcome, "k": v.kind, "r": v.reason_code, "cv": v.checker_version,
                 "fa": v.false_alarm}).scalar_one()
            self._event(c, "checker", "verdict_recorded", {
                "verdict_id": str(verdict_id), "attempt_id": str(v.attempt_id),
                "learner_id": str(context["learner_id"]), "outcome": v.outcome, "kind": v.kind,
                "checker_version": v.checker_version})

            queue_id = None
            if v.outcome == "unsure":
                # Unsure changes neither mastery nor the classmate until a teacher settles it (paper §5).
                queue_id = c.execute(text("INSERT INTO teacher_queue_item (verdict_id) VALUES (:v) RETURNING id"),
                                     {"v": verdict_id}).scalar_one()
                return VerdictRecord(verdict_id, queue_id, None, None)

            change = event_id = None
            if v.outcome == "correct" and v.kind == "fix":
                change, event_id = self._maybe_teach(c, context, "checker", {"verdict_id": str(verdict_id)})
            return VerdictRecord(verdict_id, queue_id, change, event_id)

    @staticmethod
    def _attempt_context(c: Connection, attempt_id) -> dict:
        row = c.execute(
            text("SELECT s.learner_id, e.kind, e.planted, rv.rule_id FROM attempt a "
                 "JOIN exchange e ON e.id = a.exchange_id JOIN session s ON s.id = e.session_id "
                 "LEFT JOIN rule_version rv ON rv.id = e.rule_version_id WHERE a.id = :a"),
            {"a": attempt_id}).first()
        if row is None:
            raise LookupError(f"attempt {attempt_id} does not exist")
        return row._asdict()

    def _maybe_teach(self, c: Connection, context: dict, actor: str, evidence: dict):
        """k = 1: one checked correct fix of a planted error teaches the classmate that rule."""
        if not (context["kind"] == "correction" and context["planted"] and context["rule_id"]):
            return None, None
        learner_id, rule_id = context["learner_id"], context["rule_id"]
        current = c.execute(
            text("SELECT state, state_version FROM classmate_rule_state WHERE learner_id = :l AND rule_id = :r "
                 "FOR UPDATE"), {"l": learner_id, "r": rule_id}).first()
        if current is not None and current.state == "taught":
            return None, None
        event_id = self._event(c, actor, "classmate_taught",
                               {"learner_id": str(learner_id), "rule_id": rule_id, **evidence})
        if current is None:
            c.execute(text("INSERT INTO classmate_rule_state (learner_id, rule_id, state, state_version, "
                           "last_event_id) VALUES (:l, :r, 'taught', 1, :e)"),
                      {"l": learner_id, "r": rule_id, "e": event_id})
        else:
            c.execute(text("UPDATE classmate_rule_state SET state = 'taught', state_version = :v, last_event_id = :e "
                           "WHERE learner_id = :l AND rule_id = :r"),
                      {"v": current.state_version + 1, "e": event_id, "l": learner_id, "r": rule_id})
        return "taught", event_id

    # ------------------------------------------------------------------ forgetting

    def apply_forget(self, decision) -> str | None:
        if not scheduler.is_minted(decision):
            raise TypeError("the OutcomeWriter accepts only forget decisions issued by the scheduler")
        with self._tx() as c:
            current = c.execute(
                text("SELECT state, state_version FROM classmate_rule_state WHERE learner_id = :l AND rule_id = :r "
                     "FOR UPDATE"), {"l": decision.learner_id, "r": decision.rule_id}).first()
            if current is None or current.state != "taught":
                return None
            event_id = self._event(c, "scheduler", "classmate_forgot", {
                "learner_id": str(decision.learner_id), "rule_id": decision.rule_id,
                "predicted_recall": decision.predicted_recall, "tracker_version": decision.tracker_version})
            c.execute(text("UPDATE classmate_rule_state SET state = 'forgotten', state_version = :v, "
                           "last_event_id = :e WHERE learner_id = :l AND rule_id = :r"),
                      {"v": current.state_version + 1, "e": event_id, "l": decision.learner_id,
                       "r": decision.rule_id})
            return "forgotten"

    # ------------------------------------------------------------------ teacher resolutions

    def apply_resolution(self, r: TeacherResolution) -> ResolutionRecord:
        if not isinstance(r, TeacherResolution):
            raise TypeError("expected a TeacherResolution")
        r.verify(self._resolution_key)  # raises BadSignature before anything touches the database
        with self._tx() as c:
            role = c.execute(text("SELECT role FROM learner WHERE id = :t"), {"t": r.teacher_id}).scalar()
            if role != "teacher":
                raise ResolutionRefused("only a teacher can settle an answer")
            item = c.execute(
                text("SELECT q.id, q.status, v.id AS verdict_id, v.kind, v.attempt_id FROM teacher_queue_item q "
                     "JOIN verdict v ON v.id = q.verdict_id WHERE q.id = :q FOR UPDATE OF q"),
                {"q": r.queue_item_id}).first()
            if item is None:
                raise ResolutionRefused("no such queue item")
            if item.status != "open":
                raise ResolutionRefused("this answer has already been settled")
            context = self._attempt_context(c, item.attempt_id)
            resolution_id = c.execute(
                text("INSERT INTO teacher_resolution (queue_item_id, teacher_id, outcome, note_hi) "
                     "VALUES (:q, :t, :o, :n) RETURNING id"),
                {"q": r.queue_item_id, "t": r.teacher_id, "o": r.outcome, "n": r.note_hi}).scalar_one()
            c.execute(text("UPDATE teacher_queue_item SET status = 'resolved' WHERE id = :q"), {"q": r.queue_item_id})
            actor = f"teacher:{r.teacher_id}"
            event_id = self._event(c, actor, "teacher_resolution", {
                "resolution_id": str(resolution_id), "queue_item_id": str(r.queue_item_id),
                "verdict_id": str(item.verdict_id), "learner_id": str(context["learner_id"]),
                "outcome": r.outcome})
            change = classmate_event = None
            if r.outcome == "correct" and item.kind == "fix":
                change, classmate_event = self._maybe_teach(c, context, actor,
                                                            {"resolution_id": str(resolution_id)})
            return ResolutionRecord(resolution_id, event_id, change, classmate_event)


class _WriterTx:
    """A transaction that runs under the setu_writer role and commits only if the block succeeds."""

    def __init__(self, engine: Engine):
        self._engine = engine

    def __enter__(self) -> Connection:
        self._ctx = self._engine.begin()
        conn = self._ctx.__enter__()
        conn.execute(text("SET LOCAL ROLE setu_writer"))
        return conn

    def __exit__(self, *exc):
        return self._ctx.__exit__(*exc)
