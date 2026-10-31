"""Simulator v0.2 (exploratory): the A/B/C comparison with the validity problems of v0.1 addressed.

STILL A SOFTWARE SIMULATION, NOT EVIDENCE ABOUT HUMAN LEARNING. `sim-0.1` (`simulator.py`) and its results are kept
unchanged as the baseline; this version differs as follows (each change answers a review question):

| v0.1 problem | v0.2 |
|---|---|
| ad-hoc 1.5-day half-life, day-7 recall at the floor | memory is the project's own FSRS scheduler (py-fsrs defaults, `setu.domain.scheduler`), with the app's rating rules: cue-free correct = Good, correct with a visible cue = Hard (cue cap), wrong = Again |
| A-only effects (self-explanation, noticing practice) on by default | off in the main runs; switched on only in the `hypothesis_a_only_effects` run |
| matched number of exchanges, unequal time | two designs reported: `matched_exchanges` and `matched_time` (each session stops at the same seconds budget) |
| transition gains not independently justified | `no_testing_effect` sensitivity: retrieval gain = restudy gain (removes the retrieval-practice assumption) |
| no vocabulary measure | each rule has a vocabulary card, reviewed whenever the learner retrieves the sentence |

Learner per rule: `k` (has the form: acquisition), `habit` (Hindi-transfer pull), `detect` (notices such errors),
an FSRS card for the rule and one for its words. P(correct cue-free) = k × R_rule(t) × (1 − w·habit·(1−k)).
Treatments differ only in what the learner does per exchange (see `simulator.py`): A corrects Raju (cued
production), B types the visible correction after seeing error + correction + explanation (restudy, cued), C writes
the sentence for the Hindi meaning (cue-free production) and is corrected. Everything else is identical.
"""
import dataclasses
import datetime as dt
import json
import math
import random
import statistics
from pathlib import Path

from setu.domain import planner, scheduler

from .simulator import profiles

VERSION = "sim-0.2"
T0 = dt.datetime(2026, 11, 2, 9, tzinfo=dt.UTC)
DAYS_PRACTICE = (0, 1, 2)
DAYS_TEST = (0, 1, 2, 7)
SECONDS = {"planted": 45, "no_error": 25, "own": 40, "example": 35, "tutor": 40, "why": 30}


@dataclasses.dataclass(frozen=True)
class Params:
    rules: int = 6
    retrieval_gain: float = 0.15
    cued_gain: float = 0.11
    restudy_gain: float = 0.06
    hint_gain: float = 0.09
    contrast: float = 0.08
    explain_gain: float = 0.0  # A-only, off unless testing the hypothesis
    detect_gain: float = 0.0  # A-only, off unless testing the hypothesis
    habit_weight: float = 0.35
    no_error_share: float = 0.2
    own_sentences_min: int = 2
    correction_exchanges: int = 5
    forgetting: bool = True
    progressive_hints: bool = True
    design: str = "matched_exchanges"  # or matched_time
    session_seconds: int = 300
    stability_scale: float = 1.0  # memory sensitivity: multiplies FSRS stability


@dataclasses.dataclass
class Rule:
    k: float
    habit: float
    detect: float
    card: scheduler.CardState = dataclasses.field(default_factory=scheduler.new_card)
    vocab: scheduler.CardState = dataclasses.field(default_factory=scheduler.new_card)
    raju: str = "unknown"


def _r(card, at, p) -> float:
    if card.last_review is None:
        return 1.0  # never practised: only the initial k (no session gives a rule zero exposures in the main runs)
    if p.stability_scale != 1.0 and card.stability:
        card = dataclasses.replace(card, stability=card.stability * p.stability_scale)
    return scheduler.fsrs_recall(card, at=at)


def p_correct(s: Rule, at, p) -> float:
    return max(0.0, min(1.0, s.k * _r(s.card, at, p) * (1 - p.habit_weight * s.habit * (1 - s.k))))


def _review(s: Rule, at, *, outcome: str, cue: int, words: bool = True):
    rating = scheduler.fsrs_rating(outcome=outcome, cue_level=cue, kind="recall")
    s.card = scheduler.fsrs_review(s.card, rating=rating, at=at)
    if words:
        s.vocab = scheduler.fsrs_review(s.vocab, rating=rating, at=at)


def _gain(s: Rule, g: float):
    s.k = min(1.0, s.k + g * (1 - s.k))


def simulate(profile, condition, p: Params, seed) -> dict:
    rng = random.Random(f"run:{seed}:{profile[0][0]:.6f}")
    plan_rng = random.Random(f"plan:{seed}:{profile[0][0]:.6f}")
    st = [Rule(k, h, d) for k, h, d in profile]
    m = {"hints": 0, "wrong_corrections": 0, "false_alarms": 0, "no_error_turns": 0, "corrections": 0, "own": 0,
         "exchanges": 0, "time_s": 0, "model_calls_expected": 0, "tests": {}}
    fixes = 0
    for day in DAYS_PRACTICE:
        at = T0 + dt.timedelta(days=day)
        if p.forgetting:
            for s in st:
                if s.raju == "taught" and p_correct(s, at, p) < 0.5:
                    s.raju = "forgotten"
        spent, turns = 0, []
        while True:
            if not turns:
                views = [planner.RuleView(f"R{i}", "L4", True, s.raju, True) for i, s in enumerate(st)]
                cfg = planner.Config(correction_exchanges=p.correction_exchanges,
                                     own_sentences_min=p.own_sentences_min, no_error_share=p.no_error_share,
                                     classmate_start_min_rules=1)
                turns = list(planner.plan_session(rules=views, learner_band="L4", seed=plan_rng.randrange(2**31),
                                                  config=cfg).turns)
                if p.design == "matched_exchanges" and spent:
                    break
            turn = turns.pop(0)
            idx = int(turn.rule_id[1:]) if turn.rule_id else plan_rng.randrange(len(st))
            s = st[idx]
            kind = turn.kind if condition == "A" else ("own" if turn.kind == "own" else
                                                      ("example" if condition == "B" else "tutor"))
            cost = SECONDS[kind]
            if p.design == "matched_time" and spent + cost > p.session_seconds:
                break
            spent += cost
            m["exchanges"] += 1
            at_i = at + dt.timedelta(seconds=spent)
            if kind in ("own", "tutor"):
                m["own"] += 1
                if rng.random() < p_correct(s, at_i, p):
                    _review(s, at_i, outcome="correct", cue=0)
                    _gain(s, p.retrieval_gain)
                else:
                    m["hints"] += 1
                    s.habit = max(0.0, s.habit - p.contrast)
                    _review(s, at_i, outcome="wrong", cue=0)
                    _gain(s, p.hint_gain if p.progressive_hints else p.restudy_gain)
            elif kind == "example":
                s.habit = max(0.0, s.habit - p.contrast)
                # typed while the answer is visible: restudy. It leaves a memory trace, modelled as an FSRS review
                # capped at Hard (the app's cue cap). Not mastery evidence (that is a separate, app-side rule).
                _review(s, at_i, outcome="correct", cue=2)
                _gain(s, p.restudy_gain)
            elif kind == "no_error":
                m["no_error_turns"] += 1
                m["model_calls_expected"] += 1
                if rng.random() < (1 - s.detect) * 0.5:
                    m["false_alarms"] += 1
            else:  # planted
                m["corrections"] += 1
                m["model_calls_expected"] += 1
                s.habit = max(0.0, s.habit - p.contrast)
                s.detect = min(1.0, s.detect + p.detect_gain * (1 - s.detect))
                if rng.random() < s.detect and rng.random() < p_correct(s, at_i, p):
                    _review(s, at_i, outcome="correct", cue=1)  # the rest of the sentence is a cue
                    _gain(s, p.cued_gain)
                    s.raju, fixes = "taught", fixes + 1
                    if fixes % 3 == 0:
                        _gain(s, p.explain_gain)
                        spent += SECONDS["why"]
                else:
                    m["wrong_corrections"] += 1
                    m["hints"] += 1
                    m["model_calls_expected"] += 1
                    _review(s, at_i, outcome="wrong", cue=0)
                    _gain(s, p.hint_gain if p.progressive_hints else p.restudy_gain)
        m["time_s"] += spent
        if day in DAYS_TEST:
            m["tests"][day] = _test(st, at + dt.timedelta(hours=1), p)
    m["tests"][7] = _test(st, T0 + dt.timedelta(days=7), p)
    return m


def _test(st, at, p) -> dict:
    rec = [p_correct(s, at, p) for s in st]
    return {"recall": statistics.mean(rec),
            "production": statistics.mean(r * (1 - 0.5 * p.habit_weight * s.habit) for r, s in zip(rec, st, strict=True)),
            "transfer": statistics.mean(r * 0.85 * (1 - p.habit_weight * s.habit) for r, s in zip(rec, st, strict=True)),
            "detection": statistics.mean(s.detect * (0.5 + 0.5 * r) for r, s in zip(rec, st, strict=True)),
            "vocabulary": statistics.mean(_r(s.vocab, at, p) if s.vocab.last_review else 0.0 for s in st)}


def run(p: Params, *, n=20, seeds=(1, 2, 3, 4, 5)) -> dict:
    out = {c: [] for c in "ABC"}
    for seed in seeds:
        for prof in profiles(n, p.rules, seed):
            for c in "ABC":
                out[c].append(simulate(prof, c, p, seed))
    return out


def _stats(xs):
    mu, sd = statistics.mean(xs), (statistics.stdev(xs) if len(xs) > 1 else 0.0)
    h = 1.96 * sd / math.sqrt(len(xs))
    return {"n": len(xs), "mean": round(mu, 4), "sd": round(sd, 4), "ci95": [round(mu - h, 4), round(mu + h, 4)]}


def summarise(res) -> dict:
    outcomes = [f"{k}_day{d}" for k in ("recall", "production", "transfer", "detection", "vocabulary") for d in DAYS_TEST]
    get = {o: (lambda r, o=o: r["tests"][int(o.rsplit("day", 1)[1])][o.split("_day")[0]]) for o in outcomes}
    for k in ("hints", "wrong_corrections", "false_alarms", "time_s", "own", "exchanges", "model_calls_expected"):
        get[k] = (lambda r, k=k: r[k])
    table = {c: {name: _stats([f(r) for r in rs]) for name, f in get.items()} for c, rs in res.items()}
    diffs = {}
    for a, b in (("A", "B"), ("A", "C"), ("B", "C")):
        diffs[f"{a}-{b}"] = {}
        for name in ("recall_day0", "recall_day7", "production_day7", "transfer_day7", "detection_day7",
                     "vocabulary_day7"):
            d = [get[name](x) - get[name](y) for x, y in zip(res[a], res[b], strict=True)]
            s = _stats(d)
            s["cohens_dz"] = round(s["mean"] / s["sd"], 3) if s["sd"] else None
            diffs[f"{a}-{b}"][name] = s
    return {"conditions": table, "paired_differences": diffs}


RUNS = {
    "main_matched_exchanges": {},
    "main_matched_time": {"design": "matched_time"},
    "hypothesis_a_only_effects": {"explain_gain": 0.04, "detect_gain": 0.08},
    "no_testing_effect": {"retrieval_gain": 0.06, "cued_gain": 0.06, "hint_gain": 0.06},
    "raju_forgetting_off": {"forgetting": False},
    "direct_answers": {"progressive_hints": False},
    "no_error_share_0": {"no_error_share": 0.0},
    "no_error_share_0.4": {"no_error_share": 0.4},
    "own_sentences_0": {"own_sentences_min": 0},
    "memory_stability_x0.5": {"stability_scale": 0.5},
    "memory_stability_x2": {"stability_scale": 2.0},
}


def main(out_dir="reports/simulation_v2") -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = {"version": VERSION, "baseline": "reports/simulation/results.json (sim-0.1, unchanged)",
              "fsrs": scheduler.FSRS_VERSION, "planner": planner.VERSION, "n_per_condition": 100,
              "profiles": "20 matched profiles x 5 seeds", "params": dataclasses.asdict(Params()), "runs": {}}
    for name, change in RUNS.items():
        p = dataclasses.replace(Params(), **change)
        report["runs"][name] = {"changed": change, **summarise(run(p))}
    path = out / "results.json"
    path.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    print(main())
