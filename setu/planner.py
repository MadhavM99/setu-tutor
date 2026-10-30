"""What comes next. Priority, highest first:
  1 due       a unit Raju forgot (the learner is about to forget it)  -> Raju's mistake again, another item
  2 learning  Raju is half-taught (a follow-up is still open)         -> his next follow-up
  3 unknown   a learned unit Raju does not know yet                    -> Raju's mistake
  4 lesson    a new unit may be taught today (limit per day)           -> the next lesson
  5 variety   only when nothing else is left                           -> spot check on a unit Raju knows
About 1 in 5 turns is a spot check whenever there is also something to plant (mixing units).
The unit asked last turn is skipped whenever another one is available."""
from __future__ import annotations
import random
from typing import Dict, List, Optional, Tuple


def choose(raju: Dict[str, str], rng: random.Random, last_unit: Optional[str] = None, p_spot: float = 0.2,
           weights: Optional[Dict[str, float]] = None, can_learn_new: bool = False) -> Optional[Tuple[str, Optional[str]]]:
    def pick(cands: List[str]) -> str:
        fresh = [u for u in cands if u != last_unit] or cands
        w = [max((weights or {}).get(u, 1.0), 0.0) + 1e-9 for u in fresh]
        return rng.choices(fresh, weights=w)[0]
    due = [u for u, s in raju.items() if s == "forgotten"]
    learning = [u for u, s in raju.items() if s == "learning"]
    unknown = [u for u, s in raju.items() if s == "unknown"]
    taught = [u for u, s in raju.items() if s == "taught"]
    if taught and (due or unknown) and rng.random() < p_spot:
        return "spot", pick(taught)
    if due:
        return "mistake", pick(due)
    fresh_learning = [u for u in learning if u != last_unit]
    if fresh_learning:
        return "followup", fresh_learning[0]
    if unknown:
        return "mistake", pick(unknown)
    if can_learn_new:
        return "lesson", None
    if learning:
        return "followup", learning[0]
    if taught:
        return "spot", pick(taught)
    return None
