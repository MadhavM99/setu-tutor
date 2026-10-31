"""Placement diagnostic v1 (F-PLACE, X-PERS-03; learning-ladder.md §5, journey J-3). Pure.

The walk starts at L2 (or the nearest band with approved content). Each band is probed with approved units in two
task types: `recall` (Hindi prompt → the learner builds the Telugu: production) and `read` (Telugu → the learner
types how it is read in Devanagari). A band passes on correct, cue-free answers to at least two different units
covering both task types; it fails on two misses, or when MAX_PROBES_PER_BAND probes have not passed it. Unsure
answers count for neither. A pass moves up a band, a fail moves down; the walk ends when the next band was already
decided, or at either end. Passing a band places it and every band below it.

Placement is a decision issued here (like a forget decision) and applied by the OutcomeWriter, which re-checks the
verdicts it rests on. Placed skills are `placed`, not mastered, and get a confirmation review within CONFIRM_DAYS.
v1 covers L0–L3; rules (L4) are reached through own sentences in the correction exchange.
"""
import dataclasses
import random
import uuid
import weakref
from collections.abc import Sequence

VERSION = "placement-1"
BANDS = ("L0", "L1", "L2", "L3")
START = "L2"
TASKS = ("recall", "read")
MAX_PROBES_PER_BAND = 6
CONFIRM_DAYS = 2

_MINTED: "weakref.WeakSet[PlacementDecision]" = weakref.WeakSet()


@dataclasses.dataclass(frozen=True)
class Probe:
    band: str
    item_ref: str
    task_type: str  # recall | read
    outcome: str


@dataclasses.dataclass(frozen=True)
class WalkState:
    band: str | None  # the band to probe next; None when done
    passed: tuple
    failed: tuple

    @property
    def done(self) -> bool:
        return self.band is None

    @property
    def placed_bands(self) -> tuple:
        if not self.passed:
            return ()
        top = max(BANDS.index(b) for b in self.passed)
        return BANDS[:top + 1]


def band_result(probes: Sequence[Probe]) -> str | None:
    right = [x for x in probes if x.outcome == "correct"]
    if len({x.item_ref for x in right}) >= 2 and {x.task_type for x in right} >= set(TASKS):
        return "pass"
    if sum(x.outcome in ("wrong", "partial") for x in probes) >= 2 or len(probes) >= MAX_PROBES_PER_BAND:
        return "fail"
    return None


def walk(probes: Sequence[Probe], available: Sequence[str]) -> WalkState:
    """Replay the probes so far; `available` are the bands that have approved units to probe."""
    bands = [b for b in BANDS if b in available]
    if not bands:
        return WalkState(None, (), ())
    start = min(bands, key=lambda b: abs(BANDS.index(b) - BANDS.index(START)))
    passed, failed, cur = [], [], start
    while cur is not None:
        result = band_result([x for x in probes if x.band == cur])
        if result is None:
            return WalkState(cur, tuple(passed), tuple(failed))
        (passed if result == "pass" else failed).append(cur)
        i = bands.index(cur) + (1 if result == "pass" else -1)
        cur = bands[i] if 0 <= i < len(bands) and bands[i] not in passed + failed else None
    return WalkState(None, tuple(passed), tuple(failed))


def next_probe(band: str, probes: Sequence[Probe], units: Sequence[str], *, seed: int):
    """(unit, task_type) for the next probe in `band`: tasks alternate (recall first), units never repeat."""
    mine = [x for x in probes if x.band == band]
    used = {x.item_ref for x in mine}
    fresh = [u for u in units if u not in used]
    if not fresh:
        return None
    recalls = sum(x.task_type == "recall" for x in mine)
    task = "recall" if recalls <= len(mine) - recalls else "read"
    return random.Random(f"{seed}:{band}:{len(mine)}").choice(fresh), task


class PlacementDecision:
    __slots__ = ("__weakref__", "bands", "learner_id", "skill_ids", "verdict_ids", "version")

    def __init__(self, *args, **kwargs):
        raise TypeError("PlacementDecision is issued only by the placement diagnostic")

    def __setattr__(self, name, value):
        raise dataclasses.FrozenInstanceError(f"cannot assign to field {name!r}")

    def __repr__(self):
        return f"PlacementDecision(learner_id={self.learner_id}, bands={self.bands})"


def decide(*, learner_id, bands, skill_ids, verdict_ids) -> PlacementDecision | None:
    """The decision to place `skill_ids` (the skills of the placed `bands`), resting on `verdict_ids`."""
    if not bands or not skill_ids:
        return None
    d = object.__new__(PlacementDecision)
    for name, value in (("learner_id", uuid.UUID(str(learner_id))), ("bands", tuple(bands)),
                        ("skill_ids", tuple(skill_ids)), ("verdict_ids", tuple(uuid.UUID(str(v)) for v in verdict_ids)),
                        ("version", VERSION)):
        object.__setattr__(d, name, value)
    _MINTED.add(d)
    return d


def is_minted(obj) -> bool:
    return type(obj) is PlacementDecision and obj in _MINTED
