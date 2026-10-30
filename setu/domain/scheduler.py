"""Scheduler decisions. The FSRS scheduler and mastery tracker land in slice 2.6; this module already owns the
forgetting decision: the classmate forgets a rule only when the learner's predicted recall falls below 0.5
(paper §5, P8b-01)."""
import dataclasses
import uuid
import weakref

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
