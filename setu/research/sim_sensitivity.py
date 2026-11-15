"""Why the two simulators disagree: a sensitivity map of sim-0.2's A/B/C ordering (final audit, 15 Nov 2026).

STILL A SOFTWARE SIMULATION, NOT EVIDENCE ABOUT HUMAN LEARNING. This adds no claim about learners. It checks which
unmeasured assumptions the order of the three conditions depends on, so that neither simulator's order is read as a
finding.

sim-0.1 (`simulator.py`) puts A (correct Raju) above B (same content, no classmate); sim-0.2 (`simulator_v2.py`)
puts A last. What differs between them:

- sim-0.1: typing a visible answer (B's restudy) never lengthens the memory half-life; only a successful retrieval on
  a later day does. B is last by construction.
- sim-0.2: memory is the app's FSRS scheduler. Typing a visible answer is always a successful "Hard" review, so B's
  stability grows on every exchange. An attempt that fails is an FSRS "Again" (a lapse). Simulated learners start
  with about a 0.29 chance of producing the form, and in A they must also notice the error first (`detect`, mean
  0.33), so most of A's planted turns are lapses.

So the two simulators make opposite assumptions about one thing: whether an error-free restudy or an attempt that
fails and is then corrected leaves the more durable memory. FSRS is fitted to flashcard review logs, where a failed
review means a learned card was forgotten; here it is applied to first attempts at material not yet learned.

Result of this map (see the JSON): inside sim-0.2 the order B > C > A holds in all 28 cells of the first four
variants below. Making detection near-perfect, rating a fix as cue-free, or giving A and C the app's copy step
changes A's gap but never the order. A leaves last place only in the fifth variant, and only through an artifact.

Four knobs, none of them measured on people:
- `detect`: every rule's probability of noticing a planted error, set to one value (default: the Beta(2, 4) draw);
- `feedback_restudy`: after a miss in A or C the learner types the shown answer once and that counts as the same
  restudy review B gets. The app does this (`exchange.step`: hint, then copy); sim-0.2 gives it to B only;
- `planted_cue`: is a correct fix rated Hard (cued, sim-0.2) or Good (cue-free);
- `unnoticed_is_lapse`: is an unnoticed error a memory lapse (sim-0.2: yes) or no memory event. CAUTION: in sim-0.2 a
  card that was never reviewed does not decay (`_r` returns 1.0), so "no memory event" also means "no forgetting".
  Rows of that variant are shown to expose the artifact, not as a better model.

    python -m setu.research.sim_sensitivity      # about 1 minute, writes reports/simulation_sensitivity.json

Same learners, seeds, planner and FSRS scheduler as sim-0.2 (20 matched profiles x 5 seeds, matched exchanges).
"""
import dataclasses
import json
from pathlib import Path

from . import simulator_v2 as v2

OUT = Path(__file__).resolve().parents[2] / "reports/simulation_sensitivity.json"
DETECT = (None, 0.2, 0.35, 0.5, 0.65, 0.8, 0.95)
VARIANTS = {
    "sim-0.2 as published": {},
    "copy step after a miss counts as restudy (as in the app)": {"feedback_restudy": True},
    "correct fix rated Good (cue-free)": {"planted_cue": 0},
    "copy step + fix rated Good": {"feedback_restudy": True, "planted_cue": 0},
    "unnoticed error is no memory event (artifact: no decay)": {"unnoticed_is_lapse": False},
}
ARTIFACT = "unnoticed error is no memory event (artifact: no decay)"


@dataclasses.dataclass(frozen=True)
class Params(v2.Params):
    detect_override: float | None = None
    unnoticed_is_lapse: bool = True
    planted_cue: int = 1
    feedback_restudy: bool = False


def cell(p: Params) -> dict:
    s = v2.summarise(v2.run(p))
    rec = {c: s["conditions"][c]["recall_day7"]["mean"] for c in "ABC"}
    d = s["paired_differences"]
    return {"recall_day7": rec, "order": "".join(sorted("ABC", key=lambda c: -rec[c])),
            "A_minus_B": d["A-B"]["recall_day7"]["mean"], "A_minus_B_ci95": d["A-B"]["recall_day7"]["ci95"],
            "A_minus_C": d["A-C"]["recall_day7"]["mean"], "A_minus_C_ci95": d["A-C"]["recall_day7"]["ci95"],
            "wrong_corrections_A": s["conditions"]["A"]["wrong_corrections"]["mean"]}


def main() -> Path:
    report = {"version": v2.VERSION, "kind": "sensitivity map (simulation only; no learner data)",
              "base": "reports/simulation_v2/results.json main_matched_exchanges", "fsrs": v2.scheduler.FSRS_VERSION,
              "n_per_condition": 100, "detect_values": ["beta(2,4) draw" if d is None else d for d in DETECT],
              "note": ("Intervals are simulation noise over 100 simulated learners. They say nothing about how "
                       "certain the result is for people, and get narrower just by simulating more learners."),
              "variants": {}}
    for name, change in VARIANTS.items():
        rows = []
        for d in DETECT:
            rows.append({"detect": "beta(2,4) draw" if d is None else d,
                         **cell(Params(detect_override=d, **change))})
        report["variants"][name] = {"changed": change, "rows": rows}
    for label, names in (("all_variants", list(VARIANTS)), ("without_artifact_variant",
                                                           [n for n in VARIANTS if n != ARTIFACT])):
        cells = [r for n in names for r in report["variants"][n]["rows"]]
        report[label] = {"cells": len(cells),
                         "orders_seen": {o: sum(r["order"] == o for r in cells) for o in sorted({r["order"] for r in cells})},
                         "cells_where_A_is_last": sum(r["order"][-1] == "A" for r in cells),
                         "cells_where_A_is_first": sum(r["order"][0] == "A" for r in cells)}
    OUT.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    return OUT


if __name__ == "__main__":
    print(main())
