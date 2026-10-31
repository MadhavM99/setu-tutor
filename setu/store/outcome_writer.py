"""OutcomeWriter: the only code that writes learning state (P-SESS-11, P-ARCH-11, ADR-0004, E-01).

It accepts exactly three kinds of evidence:
- a `Verdict` minted by the checker;
- a `TeacherResolution` signed by an authenticated teacher session;
- a `ForgetDecision` issued by the scheduler.

Every call runs in one transaction under the `setu_writer` role (`SET LOCAL ROLE`), so it never uses more than
writer privileges even if it connects as the owner. Every change is appended to the event ledger, and the
`classmate_rule_state` trigger re-checks in the database that each change is backed by that evidence.

From slice 2.6 a verdict may also name the FSRS card (`CardTarget`) and the skill (`SkillTarget`) it is evidence
for; the writer then updates the card and its review log (the rating comes from the verdict and the attempt's cue
level) and the mastery tracker, skill evidence and status, all in the same transaction. Unsure changes nothing.
From slice S5 an own sentence that still has the Hindi habit of a rule the learner taught the classmate is logged
as a `copy_event` (M-37).
"""
import dataclasses
import datetime as dt
import json
import os
import uuid

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from setu.domain import exchange, scheduler
from setu.domain.checker import INDEPENDENT_MODES
from setu.domain.verdict import is_minted

from .resolution import TeacherResolution


class NotAVerdict(TypeError):
    """Raised for anything that is not a verdict minted by the checker."""


class ConflictingVerdict(Exception):
    """The attempt already has a different verdict; verdicts are immutable."""


class ResolutionRefused(Exception):
    """The resolution is well signed but cannot be applied (not a teacher, item missing or already settled)."""


@dataclasses.dataclass(frozen=True)
class CardTarget:
    """The FSRS card a recall or recognition answer is about (letter, akshara, lexeme or chunk, per modality)."""
    card_kind: str
    card_ref: str
    modality: str


@dataclasses.dataclass(frozen=True)
class SkillTarget:
    """The skill an answer is evidence for, and what kind of evidence it is (learning-ladder.md §3)."""
    skill_id: str
    band: str
    item_ref: str
    task_type: str
    production: bool = False


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
    @classmethod
    def from_environment(cls, *, fallback: Engine) -> "OutcomeWriter":
        url = os.environ.get("SETU_WRITER_DATABASE_URL")
        return cls(create_engine(url) if url else fallback)

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

    def record_verdict(self, v, *, card: CardTarget | None = None, skill: SkillTarget | None = None,
                       at: dt.datetime | None = None) -> VerdictRecord:
        self.validate_verdict(v)
        at = at or dt.datetime.now(dt.UTC)
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

            if card is not None:
                self._review_card(c, context, card, v, verdict_id, at)
            if skill is not None:
                self._update_skill(c, context, skill, v, verdict_id, at)
            if v.kind == "own" and exchange.is_copy(v.reason_code):
                self._maybe_copy(c, context, v.attempt_id, verdict_id)
            change = event_id = None
            if v.outcome == "correct" and v.kind == "fix":
                change, event_id = self._maybe_teach(c, context, "checker", {"verdict_id": str(verdict_id)})
            return VerdictRecord(verdict_id, queue_id, change, event_id)

    # ------------------------------------------------------------------ scheduling (slice 2.6)

    def _review_card(self, c, context, card: CardTarget, v, verdict_id, at):
        rating = scheduler.fsrs_rating(outcome=v.outcome, cue_level=context["cue_level"], kind=v.kind)
        if rating is None:
            return
        row = c.execute(text("SELECT * FROM learner_lexeme_card WHERE learner_id = :l AND card_kind = :k "
                             "AND card_ref = :r AND modality = :m FOR UPDATE"),
                        {"l": context["learner_id"], "k": card.card_kind, "r": card.card_ref,
                         "m": card.modality}).first()
        state = scheduler.new_card() if row is None or row.fsrs_state is None else scheduler.CardState(
            row.stability, row.difficulty, row.due, row.last_review, row.reps, row.lapses, row.fsrs_state,
            row.fsrs_step)
        new = scheduler.fsrs_review(state, rating=rating, at=at)
        values = {"l": context["learner_id"], "k": card.card_kind, "r": card.card_ref, "m": card.modality,
                  "st": new.stability, "d": new.difficulty, "due": new.due, "lr": new.last_review, "reps": new.reps,
                  "lapses": new.lapses, "fs": new.state, "step": new.step, "ver": new.version}
        card_id = c.execute(
            text("INSERT INTO learner_lexeme_card (learner_id, card_kind, card_ref, modality, stability, difficulty, "
                 "due, last_review, reps, lapses, fsrs_state, fsrs_step, fsrs_version) VALUES (:l, :k, :r, :m, :st, "
                 ":d, :due, :lr, :reps, :lapses, :fs, :step, :ver) ON CONFLICT (learner_id, card_kind, card_ref, "
                 "modality) DO UPDATE SET stability = :st, difficulty = :d, due = :due, last_review = :lr, "
                 "reps = :reps, lapses = :lapses, fsrs_state = :fs, fsrs_step = :step, fsrs_version = :ver "
                 "RETURNING id"), values).scalar_one()
        c.execute(text("INSERT INTO fsrs_review_log (card_id, verdict_id, rating, cue_level, reviewed_at) "
                       "VALUES (:c, :v, :r, :cue, :at)"),
                  {"c": card_id, "v": verdict_id, "r": rating, "cue": context["cue_level"], "at": at})

    def _update_skill(self, c, context, skill: SkillTarget, v, verdict_id, at):
        if v.outcome == "unsure":
            return
        learner_id = context["learner_id"]
        c.execute(text("INSERT INTO skill_evidence (learner_id, skill_id, verdict_id, item_ref, task_type, day, outcome, "
                       "cue_level, after_reveal, production) VALUES (:l, :s, :v, :i, :t, :d, :o, :cue, :ar, :p)"),
                  {"l": learner_id, "s": skill.skill_id, "v": verdict_id, "i": skill.item_ref, "t": skill.task_type,
                   "d": at.date(), "o": v.outcome, "cue": context["cue_level"], "ar": context["after_reveal"],
                   "p": skill.production})
        row = c.execute(text("SELECT tracker_alpha, tracker_beta, half_life_days, last_practised FROM "
                             "learner_skill_state WHERE learner_id = :l AND skill_id = :s FOR UPDATE"),
                        {"l": learner_id, "s": skill.skill_id}).first()
        tracker = (scheduler.TrackerState.new(at=at) if row is None or row.last_practised is None else
                   scheduler.TrackerState(row.tracker_alpha, row.tracker_beta, row.half_life_days, row.last_practised))
        tracker = scheduler.track(tracker, outcome=v.outcome, cue_level=context["cue_level"],
                                  after_reveal=context["after_reveal"], at=at)
        evidence = [scheduler.Evidence(r.item_ref, r.task_type, r.day, r.outcome, r.cue_level, r.after_reveal,
                                       r.production)
                    for r in c.execute(text("SELECT * FROM skill_evidence WHERE learner_id = :l AND skill_id = :s"),
                                       {"l": learner_id, "s": skill.skill_id})]
        m = scheduler.mastery_status(evidence, tracker, band=skill.band, at=at)
        event_id = self._event(c, "checker", "skill_updated", {
            "learner_id": str(learner_id), "skill_id": skill.skill_id, "verdict_id": str(verdict_id),
            "status": m.status, "tracker_version": tracker.version})
        due = tracker.last_practised + dt.timedelta(days=tracker.half_life_days)
        c.execute(
            text("INSERT INTO learner_skill_state (learner_id, skill_id, mastery_mean, mastery_lo, mastery_hi, "
                 "evidence_n, distinct_items, distinct_task_types, distinct_days, cuefree_successes, "
                 "production_successes, last_practised, due_at, status, source, updated_by_event, tracker_alpha, "
                 "tracker_beta, half_life_days, tracker_version) VALUES (:l, :s, :mean, :lo, :hi, :n, :items, "
                 ":types, :days, :cf, :prod, :last, :due, :status, 'observed', :ev, :a, :b, :h, :tv) "
                 "ON CONFLICT (learner_id, skill_id) DO UPDATE SET mastery_mean = :mean, mastery_lo = :lo, "
                 "mastery_hi = :hi, evidence_n = :n, distinct_items = :items, distinct_task_types = :types, "
                 "distinct_days = :days, cuefree_successes = :cf, production_successes = :prod, "
                 "last_practised = :last, due_at = :due, status = :status, updated_by_event = :ev, "
                 "tracker_alpha = :a, tracker_beta = :b, half_life_days = :h, tracker_version = :tv"),
            {"l": learner_id, "s": skill.skill_id, "mean": tracker.mean, "lo": tracker.lo, "hi": tracker.hi,
             "n": m.evidence_n, "items": m.distinct_items, "types": m.distinct_task_types, "days": m.distinct_days,
             "cf": m.cuefree_successes, "prod": m.production_successes, "last": tracker.last_practised, "due": due,
             "status": m.status, "ev": event_id, "a": tracker.alpha, "b": tracker.beta, "h": tracker.half_life_days,
             "tv": tracker.version})

    def _maybe_copy(self, c: Connection, context: dict, attempt_id, verdict_id):
        """M-37: the learner's own sentence carries the Hindi habit of a rule they already taught the classmate."""
        if not context["rule_id"] or c.execute(
                text("SELECT 1 FROM classmate_rule_state WHERE learner_id = :l AND rule_id = :r"),
                {"l": context["learner_id"], "r": context["rule_id"]}).first() is None:
            return
        c.execute(text("INSERT INTO copy_event (learner_id, rule_id, attempt_id) VALUES (:l, :r, :a)"),
                  {"l": context["learner_id"], "r": context["rule_id"], "a": attempt_id})
        self._event(c, "checker", "copy_event", {"learner_id": str(context["learner_id"]),
                                                 "rule_id": context["rule_id"], "verdict_id": str(verdict_id)})

    @staticmethod
    def _attempt_context(c: Connection, attempt_id) -> dict:
        row = c.execute(
            text("SELECT s.learner_id, e.kind, e.planted, rv.rule_id, a.response_mode, a.cue_level, a.after_reveal "
                 "FROM attempt a "
                 "JOIN exchange e ON e.id = a.exchange_id JOIN session s ON s.id = e.session_id "
                 "LEFT JOIN rule_version rv ON rv.id = e.rule_version_id WHERE a.id = :a"),
            {"a": attempt_id}).first()
        if row is None:
            raise LookupError(f"attempt {attempt_id} does not exist")
        return row._asdict()

    def _maybe_teach(self, c: Connection, context: dict, actor: str, evidence: dict):
        """k = 1: one checked correct fix of a planted error teaches the classmate that rule.

        The fix must be independent production (typed, on-screen keyboard or spoken), given with no recall cue and
        not after the answer was revealed (R-INPUT; also enforced by the classmate-state trigger)."""
        if not (context["kind"] == "correction" and context["planted"] and context["rule_id"]):
            return None, None
        if context["response_mode"] not in INDEPENDENT_MODES or context["cue_level"] != 0 or context["after_reveal"]:
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
