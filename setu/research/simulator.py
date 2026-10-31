"""Simulator v0.1: an exploratory, parametric simulation of A/B/C (P-EVAL-12, X-SIM; mid-submission sprint).

THIS IS A SOFTWARE SIMULATION, NOT EVIDENCE ABOUT HUMAN LEARNING. Every learning effect below is an assumption
written in `Params`; the results show what follows from those assumptions, and the ablation `no_mechanism_bonus`
shows how much of any A advantage comes only from the assumed reverse-learning effects.

Learner model (per rule): `k` the probability of producing the Telugu form cue-free, `habit` the strength of the
Hindi-transfer habit (it pulls answers toward the planted error), `detect` the probability of noticing such an error,
and a memory half-life `h` (days). Recall after t days: k * 2^(-t/h), minus habit interference. Every condition has
the same learners (matched profiles), the same rules in the same order, the same number of exchanges per session,
the same feedback after a miss and the same forgetting.

Per exchange:
- A (teach Raju): the real planner (`setu.domain.planner`) decides planted / no-error / own turns. Planted turn:
  the learner must notice the error (detect) and produce the corrected sentence with the rest of the sentence as a
  partial cue (`cued_gain`); correcting a contrast lowers the habit (`contrast`); every third correct fix asks "why?"
  (`explain_gain`, assumed). Own turns are full cue-free production (`retrieval_gain`). No-error turns test
  detection (false alarms).
- B (matched examples): the same sentences with the error, the correction and the same explanation are shown (the
  contrast lowers the habit by the same `contrast`), then the learner types the corrected sentence while it is
  visible (`restudy_gain`). Own turns as in A.
- C (conventional tutor): the learner writes the sentence for the Hindi meaning (full retrieval, `retrieval_gain`);
  the tutor corrects the learner's own errors (contrast only when the learner made the error).
After a miss: one hint then a second attempt (progressive hints, `hint_gain`) or the answer shown (`restudy_gain`).
"""
import dataclasses
import json
import math
import random
import statistics
from pathlib import Path

from setu.domain import planner

VERSION = "sim-0.1"
CONDITIONS = ("A", "B", "C")
DAYS_PRACTICE = (0, 1, 2)
DAYS_TEST = (0, 1, 2, 7)


@dataclasses.dataclass(frozen=True)
class Params:
    rules: int = 6
    retrieval_gain: float = 0.15  # cue-free production with feedback (the testing effect)
    cued_gain: float = 0.11  # producing a correction with the rest of the sentence as a cue
    restudy_gain: float = 0.06  # typing a visible answer (restudy)
    hint_gain: float = 0.09  # second attempt after a hint
    contrast: float = 0.08  # habit reduction from seeing an error next to its correction
    explain_gain: float = 0.04  # self-explanation ("why?"), A only (assumed)
    detect_gain: float = 0.08  # practice at noticing errors, A only (assumed)
    half_life0: float = 1.5  # days
    spacing: float = 0.6  # half-life growth per successful retrieval on a later day
    habit_weight: float = 0.35
    no_error_share: float = 0.2
    own_sentences_min: int = 2
    correction_exchanges: int = 5
    forgetting: bool = True  # Raju forgets when the learner is predicted to forget (re-planting)
    progressive_hints: bool = True
    seconds: tuple = (("planted", 45), ("no_error", 25), ("own", 40), ("example", 35), ("tutor", 40), ("why", 30))


@dataclasses.dataclass
class RuleState:
    k: float
    habit: float
    detect: float
    h: float
    last: float = 0.0
    raju: str = "unknown"


def recall(s: RuleState, day: float, p: Params) -> float:
    decay = 2 ** (-(max(0.0, day - s.last)) / s.h)
    return max(0.0, min(1.0, s.k * decay - p.habit_weight * s.habit * (1 - s.k)))


def profiles(n: int, rules: int, seed: int) -> list[list[tuple]]:
    """Matched initial learner profiles: the same list is used for every condition."""
    rng = random.Random(f"profiles:{seed}")
    return [[(rng.betavariate(2, 5), rng.uniform(0.3, 0.8), rng.betavariate(2, 4)) for _ in range(rules)]
            for _ in range(n)]


def _learn(s: RuleState, gain: float, day: float, success: bool, p: Params):
    s.k = min(1.0, s.k + gain * (1 - s.k))
    if success and day > s.last:
        s.h *= 1 + p.spacing
    s.last = day


def simulate_learner(profile, condition: str, p: Params, seed: int) -> dict:
    rng = random.Random(f"run:{seed}:{profile[0][0]:.6f}")  # common random numbers across conditions
    plan_rng = random.Random(f"plan:{seed}:{profile[0][0]:.6f}")  # identical plans across conditions
    st = [RuleState(k, hb, d, p.half_life0) for k, hb, d in profile]
    m = {"hints": 0, "wrong_corrections": 0, "false_alarms": 0, "no_error_turns": 0, "corrections": 0,
         "own": 0, "time_s": 0, "model_calls_expected": 0, "tests": {}}
    secs = dict(p.seconds)
    fixes = 0
    for day in DAYS_PRACTICE:
        if p.forgetting:
            for s in st:
                if s.raju == "taught" and recall(s, day, p) < 0.5:
                    s.raju = "forgotten"
        views = [planner.RuleView(f"R{i}", "L4", True, s.raju, True) for i, s in enumerate(st)]
        cfg = planner.Config(correction_exchanges=p.correction_exchanges, own_sentences_min=p.own_sentences_min,
                             no_error_share=p.no_error_share, classmate_start_min_rules=1)
        plan = planner.plan_session(rules=views, learner_band="L4", seed=plan_rng.randrange(2**31), config=cfg)
        for turn in plan.turns:
            idx = int(turn.rule_id[1:]) if turn.rule_id else plan_rng.randrange(len(st))
            s = st[idx]
            kind = turn.kind if condition == "A" else ("own" if turn.kind == "own" else
                                                      ("example" if condition == "B" else "tutor"))
            m["time_s"] += secs[kind]
            if kind == "own" or kind == "tutor":
                m["own"] += 1
                ok = rng.random() < recall(s, day, p)
                if not ok:
                    s.habit = max(0.0, s.habit - p.contrast)  # own error corrected next to the right form
                    m["hints"] += 1
                    ok2 = rng.random() < recall(s, day, p) if p.progressive_hints else False
                    _learn(s, (p.hint_gain if p.progressive_hints else p.restudy_gain), day, ok2, p)
                else:
                    _learn(s, p.retrieval_gain, day, True, p)
            elif kind == "example":
                s.habit = max(0.0, s.habit - p.contrast)
                _learn(s, p.restudy_gain, day, False, p)
            elif kind == "no_error":
                m["no_error_turns"] += 1
                m["model_calls_expected"] += 1
                if rng.random() < (1 - s.detect) * 0.5:  # assumed: half of the non-noticers flag a correct sentence
                    m["false_alarms"] += 1
            else:  # planted
                m["corrections"] += 1
                m["model_calls_expected"] += 1
                noticed = rng.random() < s.detect
                ok = noticed and rng.random() < recall(s, day, p)
                s.habit = max(0.0, s.habit - p.contrast)
                s.detect = min(1.0, s.detect + p.detect_gain * (1 - s.detect))
                if ok:
                    _learn(s, p.cued_gain, day, True, p)
                    s.raju, fixes = "taught", fixes + 1
                    if fixes % 3 == 0:
                        s.k = min(1.0, s.k + p.explain_gain * (1 - s.k))
                        m["time_s"] += secs["why"]
                else:
                    m["wrong_corrections"] += 1
                    m["hints"] += 1
                    m["model_calls_expected"] += 1  # coach hint
                    ok2 = rng.random() < recall(s, day, p) if p.progressive_hints else False
                    _learn(s, (p.hint_gain if p.progressive_hints else p.restudy_gain), day, ok2, p)
        if day in DAYS_TEST:
            m["tests"][day] = _test(st, day, p, rng)
    for day in DAYS_TEST:
        if day not in m["tests"]:
            m["tests"][day] = _test(st, day, p, rng)
    return m


def _test(st, day, p, rng) -> dict:
    """Cue-free recall of practised items, production for unseen meanings (transfer: the habit interferes more),
    and noticing planted errors in unseen sentences. Expected values (no sampling noise in the score itself)."""
    rec = [recall(s, day, p) for s in st]
    transfer = [max(0.0, r - 0.5 * p.habit_weight * s.habit) * 0.85 for r, s in zip(rec, st, strict=True)]
    detect = [s.detect * (0.5 + 0.5 * r) for r, s in zip(rec, st, strict=True)]
    return {"recall": statistics.mean(rec), "transfer": statistics.mean(transfer),
            "detection": statistics.mean(detect)}


def run(*, n: int = 20, seeds=(1, 2, 3, 4, 5), params: Params | None = None, conditions=CONDITIONS) -> dict:
    p = params or Params()
    out = {c: [] for c in conditions}
    for seed in seeds:
        for prof in profiles(n, p.rules, seed):
            for c in conditions:
                out[c].append(simulate_learner(prof, c, p, seed))
    return out


def summarise(results: dict) -> dict:
    """Per condition: mean, sd and 95% CI of each outcome; paired differences (same profiles) with 95% CI."""
    def stats(xs):
        mu, sd = statistics.mean(xs), statistics.stdev(xs) if len(xs) > 1 else 0.0
        half = 1.96 * sd / math.sqrt(len(xs))
        return {"n": len(xs), "mean": round(mu, 4), "sd": round(sd, 4), "ci95": [round(mu - half, 4), round(mu + half, 4)]}

    metrics = {f"{k}_day{d}": (lambda r, k=k, d=d: r["tests"][d][k]) for k in ("recall", "transfer", "detection")
               for d in DAYS_TEST}
    for k in ("hints", "wrong_corrections", "false_alarms", "time_s", "own", "model_calls_expected"):
        metrics[k] = (lambda r, k=k: r[k])
    table = {c: {name: stats([f(r) for r in rs]) for name, f in metrics.items()} for c, rs in results.items()}
    diffs = {}
    for a, b in (("A", "B"), ("A", "C"), ("B", "C")):
        if a in results and b in results:
            diffs[f"{a}-{b}"] = {}
            for name in ("recall_day7", "transfer_day7", "detection_day7", "recall_day0"):
                d = [metrics[name](x) - metrics[name](y) for x, y in zip(results[a], results[b], strict=True)]
                s = stats(d)
                s["cohens_dz"] = round(s["mean"] / s["sd"], 3) if s["sd"] else None
                diffs[f"{a}-{b}"][name] = s
    return {"conditions": table, "paired_differences": diffs}


ABLATIONS = {
    "main": {},
    "no_mechanism_bonus": {"explain_gain": 0.0, "detect_gain": 0.0},  # A's assumed extra effects switched off
    "raju_forgetting_off": {"forgetting": False},
    "direct_answers": {"progressive_hints": False},
    "no_error_share_0": {"no_error_share": 0.0},
    "no_error_share_0.4": {"no_error_share": 0.4},
    "own_sentences_0": {"own_sentences_min": 0},
    "sensitivity_half_life_4": {"half_life0": 4.0},  # same for every condition: checks the day-7 floor effect
}


def main(out_dir: str = "reports/simulation") -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    all_results = {"version": VERSION, "planner": planner.VERSION, "n_per_condition_per_seed": 20,
                   "seeds": [1, 2, 3, 4, 5], "params": dataclasses.asdict(Params()), "runs": {}}
    for name, change in ABLATIONS.items():
        p = dataclasses.replace(Params(), **change)
        all_results["runs"][name] = {"changed": change, **summarise(run(params=p))}
    path = out / "results.json"
    path.write_text(json.dumps(all_results, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    print(main())
