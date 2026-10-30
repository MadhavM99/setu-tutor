"""Raju's notebook. Raju is weaker than the learner *by construction*: what he knows is this data,
never the model's own knowledge, and only checked answers change it.

    unknown --(learner's checked correct fix)--> learning --(all follow-ups passed)--> taught
    taught --(learner's recall drops below the threshold)--> forgotten --(fixed again)--> learning
A unit only enters the notebook after the learner has had its lesson and answered its check correctly."""
from __future__ import annotations
from typing import Dict, List

FORGET_BELOW = 0.5


def add_unit(raju: Dict[str, str], unit_id: str) -> None:
    raju.setdefault(unit_id, "unknown")


def fixed(raju: Dict[str, str], fu_done: Dict[str, int], unit_id: str, n_followups: int) -> str:
    """The learner corrected Raju and the checker said correct."""
    if raju.get(unit_id) in ("unknown", "forgotten"):
        if n_followups > 0:
            raju[unit_id] = "learning"
            fu_done[unit_id] = 0
        else:
            raju[unit_id] = "taught"
    return raju[unit_id]


def followup_passed(raju: Dict[str, str], fu_done: Dict[str, int], unit_id: str, n_followups: int) -> bool:
    """One follow-up answered correctly. True when Raju now knows the unit."""
    if raju.get(unit_id) != "learning":
        return False
    fu_done[unit_id] = fu_done.get(unit_id, 0) + 1
    if fu_done[unit_id] >= n_followups:
        raju[unit_id] = "taught"
        return True
    return False


def forget(raju: Dict[str, str], fu_done: Dict[str, int], p_recall: Dict[str, float],
           threshold: float = FORGET_BELOW) -> List[str]:
    """Raju forgets a unit exactly when the learner is about to. Returns the units forgotten now."""
    gone = [u for u, p in p_recall.items() if raju.get(u) == "taught" and p < threshold]
    for u in gone:
        raju[u] = "forgotten"
        fu_done[u] = 0                                  # when re-taught, he asks his follow-ups again
    return gone


def in_state(raju: Dict[str, str], *states: str) -> List[str]:
    return [u for u, s in raju.items() if s in states]
