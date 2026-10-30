"""Scheduler: FSRS for discrete items, the mastery tracker for rules and skills, the unlock rule, baselines, and the
forgetting decision: the classmate forgets a rule only when the learner's predicted recall falls below 0.5
(paper §5, P8b-01)."""
import dataclasses
import datetime as _dt
import math
import uuid
import weakref

import fsrs as _fsrs

FORGET_BELOW = 0.5

_SCHEDULER_CAPABILITY = object()
_MINTED: "weakref.WeakSet[ForgetDecision]" = weakref.WeakSet()


class ForgetDecision:
    __slots__ = ("__weakref__", "learner_id", "predicted_recall", "rule_id", "tracker_version")

    def __init__(self, *args, **kwargs):
        raise TypeError("ForgetDecision is issued only by the scheduler")

    def __setattr__(self, name, value):
        raise dataclasses.FrozenInstanceError(f"cannot assign to field {name!r}")

    def __repr__(self):
        return (f"ForgetDecision(learner_id={self.learner_id}, rule_id={self.rule_id!r}, "
                f"predicted_recall={self.predicted_recall:.3f})")


def decide_forget(*, learner_id, rule_id, predicted_recall, tracker_version) -> ForgetDecision | None:
    """Return a decision to forget `rule_id`, or None if the learner is not predicted to be forgetting it."""
    p = float(predicted_recall)
    if not 0.0 <= p <= 1.0:
        raise ValueError(f"predicted_recall must be in [0, 1], got {p}")
    if p >= FORGET_BELOW:
        return None
    d = object.__new__(ForgetDecision)
    for name, value in (("learner_id", uuid.UUID(str(learner_id))), ("rule_id", rule_id),
                        ("predicted_recall", p), ("tracker_version", tracker_version)):
        object.__setattr__(d, name, value)
    _MINTED.add(d)
    return d


def is_minted(obj) -> bool:
    return type(obj) is ForgetDecision and obj in _MINTED and obj.predicted_recall < FORGET_BELOW


# =============================================================== slice 2.6: FSRS, mastery tracker, unlock, baselines
#
# Every update comes from a checker verdict (or a teacher resolution) through the OutcomeWriter. Answers given with a
# recall cue or after the answer was revealed are never mastery evidence (A1, R-INPUT); for FSRS they are capped at
# Hard. Unsure verdicts change nothing.

FSRS_VERSION = "fsrs-6.3.2"
TRACKER_VERSION = "tracker-1"
_SCHEDULER = _fsrs.Scheduler(enable_fuzzing=False)  # deterministic intervals (E-12)
DAY = _dt.timedelta(days=1)


def fsrs_rating(*, outcome: str, cue_level: int, kind: str) -> int | None:
    """Again 1, Hard 2, Good 3 (Easy is never inferred). A visible cue or a recognition answer caps at Hard."""
    if outcome == "unsure":
        return None
    if outcome == "wrong":
        return 1
    if outcome == "partial":
        return 2
    return 2 if cue_level > 0 or kind == "recognition" else 3


@dataclasses.dataclass(frozen=True)
class CardState:
    stability: float | None = None
    difficulty: float | None = None
    due: _dt.datetime | None = None
    last_review: _dt.datetime | None = None
    reps: int = 0
    lapses: int = 0
    state: int = int(_fsrs.State.Learning)
    step: int | None = 0
    version: str = FSRS_VERSION


def new_card() -> CardState:
    return CardState()


def _to_fsrs(c: CardState, at: _dt.datetime) -> "_fsrs.Card":
    return _fsrs.Card(card_id=1, state=_fsrs.State(c.state), step=c.step, stability=c.stability,
                      difficulty=c.difficulty, due=c.due or at, last_review=c.last_review)


def fsrs_review(card: CardState, *, rating: int, at: _dt.datetime) -> CardState:
    new, _log = _SCHEDULER.review_card(_to_fsrs(card, at), _fsrs.Rating(rating), at)
    lapsed = rating == 1 and card.state == int(_fsrs.State.Review)
    return CardState(new.stability, new.difficulty, new.due, new.last_review, card.reps + 1,
                     card.lapses + (1 if lapsed else 0), int(new.state), new.step)


def fsrs_recall(card: CardState, *, at: _dt.datetime) -> float:
    if card.last_review is None:
        return 0.0
    return float(_SCHEDULER.get_card_retrievability(_to_fsrs(card, at), at))


# ---------------------------------------------------------------- Beta posterior helpers


def _betacf(a: float, b: float, x: float) -> float:
    tiny, qab, qap, qam = 1e-300, a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > tiny else tiny)
        c = 1 + aa / c if abs(1 + aa / c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > tiny else tiny)
        c = 1 + aa / c if abs(1 + aa / c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-12:
            break
    return h


def beta_cdf(x: float, a: float, b: float) -> float:
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x) / a
    return 1 - front * _betacf(b, a, 1 - x) / b


def beta_quantile(a: float, b: float, q: float) -> float:
    lo, hi = 0.0, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if beta_cdf(mid, a, b) < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# ---------------------------------------------------------------- mastery tracker (tracker-1, E-05)

EVIDENCE_HALF_LIFE_DAYS = 60.0  # old evidence fades towards the prior Beta(1, 1)
MIN_HALF_LIFE_DAYS = 0.5


@dataclasses.dataclass(frozen=True)
class TrackerState:
    """Beta(alpha, beta) belief that the learner has the skill, plus a memory half-life in days.

    Draft parameters (to calibrate on pilot data): a cue-free correct answer adds 1 to alpha and multiplies the
    half-life by 1.2 + 3(1 - p), where p is the predicted recall at that moment (harder recall, larger gain, as in
    the paper's simulator); partial adds 0.5 to each; wrong adds 1 to beta and halves the half-life."""

    alpha: float
    beta: float
    half_life_days: float
    last_practised: _dt.datetime
    version: str = TRACKER_VERSION

    @classmethod
    def new(cls, *, at: _dt.datetime) -> "TrackerState":
        return cls(1.0, 1.0, 1.0, at)

    @property
    def mean(self) -> float:
        return self.alpha / (self.alpha + self.beta)

    @property
    def lo(self) -> float:
        return beta_quantile(self.alpha, self.beta, 0.05)

    @property
    def hi(self) -> float:
        return beta_quantile(self.alpha, self.beta, 0.95)


def predicted_recall(t: TrackerState, *, at: _dt.datetime) -> float:
    days = max(0.0, (at - t.last_practised) / DAY)
    return 2 ** (-days / t.half_life_days)


def track(t: TrackerState, *, outcome: str, cue_level: int, after_reveal: bool, at: _dt.datetime) -> TrackerState:
    days = max(0.0, (at - t.last_practised) / DAY)
    w = 2 ** (-days / EVIDENCE_HALF_LIFE_DAYS)
    alpha, beta = 1 + (t.alpha - 1) * w, 1 + (t.beta - 1) * w
    if outcome == "unsure" or cue_level > 0 or after_reveal:
        return dataclasses.replace(t, alpha=alpha, beta=beta) if days else t
    p = predicted_recall(t, at=at)
    h = t.half_life_days
    if outcome == "correct":
        alpha, h = alpha + 1, h * (1.2 + 3 * (1 - p))
    elif outcome == "partial":
        alpha, beta = alpha + 0.5, beta + 0.5
    elif outcome == "wrong":
        beta, h = beta + 1, max(MIN_HALF_LIFE_DAYS, h / 2)
    else:
        raise ValueError(f"unknown outcome {outcome!r}")
    return TrackerState(alpha, beta, h, at)


def forget_if_due(*, learner_id, rule_id: str, tracker: TrackerState, at: _dt.datetime) -> ForgetDecision | None:
    """The classmate forgets a rule when the learner's own predicted recall of it falls below 0.5 (P8b-01)."""
    return decide_forget(learner_id=learner_id, rule_id=rule_id, predicted_recall=predicted_recall(tracker, at=at),
                         tracker_version=tracker.version)


# ---------------------------------------------------------------- unlock rule (learning-ladder.md §3)


@dataclasses.dataclass(frozen=True)
class Evidence:
    item_ref: str
    task_type: str
    day: _dt.date
    outcome: str
    cue_level: int
    after_reveal: bool
    production: bool = False


@dataclasses.dataclass(frozen=True)
class MasteryStatus:
    status: str  # available | learning | mastered | due
    evidence_n: int
    distinct_items: int
    distinct_task_types: int
    distinct_days: int
    cuefree_successes: int
    production_successes: int


UNLOCK = {"successes": 3, "items": 2, "task_types": 2, "days": 2, "lower_bound": 0.6}
PRODUCTION_FROM_BAND = "L2"


def mastery_status(evidence, tracker: TrackerState, *, band: str, at: _dt.datetime | None = None) -> MasteryStatus:
    """Mastered only on varied, cue-free, checked evidence and a confident tracker; never from time, clicks,
    confidence or viewing an aid (X-PERS-02/06)."""
    counted = [e for e in evidence if e.outcome == "correct" and e.cue_level == 0 and not e.after_reveal]
    production = sum(1 for e in counted if e.production)
    s = MasteryStatus(
        "available", len([e for e in evidence if e.outcome != "unsure"]), len({e.item_ref for e in counted}),
        len({e.task_type for e in counted}), len({e.day for e in counted}), len(counted), production)
    if not s.evidence_n:
        return s
    needs_production = BANDS_ORDER.index(band) >= BANDS_ORDER.index(PRODUCTION_FROM_BAND)
    mastered = (s.cuefree_successes >= UNLOCK["successes"] and s.distinct_items >= UNLOCK["items"]
                and s.distinct_task_types >= UNLOCK["task_types"] and s.distinct_days >= UNLOCK["days"]
                and (production >= 1 or not needs_production) and tracker.lo >= UNLOCK["lower_bound"])
    status = "mastered" if mastered else "learning"
    if mastered and at is not None and predicted_recall(tracker, at=at) < FORGET_BELOW:
        status = "due"
    return dataclasses.replace(s, status=status)


BANDS_ORDER = ("L0", "L1", "L2", "L3", "L4", "L5")


# ---------------------------------------------------------------- baselines (M-23 BKT, M-24 SM-2)


@dataclasses.dataclass(frozen=True)
class Bkt:
    p_init: float = 0.2
    p_learn: float = 0.15
    p_slip: float = 0.1
    p_guess: float = 0.2

    def predict(self, p_known: float) -> float:
        return p_known * (1 - self.p_slip) + (1 - p_known) * self.p_guess

    def update(self, p_known: float, *, correct: bool) -> float:
        if correct:
            post = p_known * (1 - self.p_slip) / self.predict(p_known)
        else:
            post = p_known * self.p_slip / (p_known * self.p_slip + (1 - p_known) * (1 - self.p_guess))
        return post + (1 - post) * self.p_learn


@dataclasses.dataclass(frozen=True)
class Sm2:
    repetitions: int = 0
    interval: int = 0
    easiness: float = 2.5
    easiness_before: float = 2.5

    def review(self, *, quality: int) -> "Sm2":
        if quality < 3:
            reps, interval = 0, 1
        else:
            reps = self.repetitions + 1
            interval = 1 if reps == 1 else 6 if reps == 2 else round(self.interval * self.easiness)
        ef = max(1.3, self.easiness + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
        return Sm2(reps, interval, ef, self.easiness)


def log_loss(y, p, eps: float = 1e-12) -> float:
    return -sum(yi * math.log(max(pi, eps)) + (1 - yi) * math.log(max(1 - pi, eps)) for yi, pi in zip(y, p, strict=True)) / len(y)


def auc(y, p) -> float:
    pos = [pi for yi, pi in zip(y, p, strict=True) if yi]
    neg = [pi for yi, pi in zip(y, p, strict=True) if not yi]
    wins = sum(1.0 if a > b else 0.5 if a == b else 0.0 for a in pos for b in neg)
    return wins / (len(pos) * len(neg))
