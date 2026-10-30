"""Planner v1 (P-ARCH-02, P-SESS-05/07, P8b-03, X-CLS-START, R-17; session-and-exchange.md §2).

Pure and seeded: the same inputs and seed give the same plan, and the seed is returned for the session record (E-12).
Version 1 plans the correction block and the own-sentence block; reviews and new items join with the scheduler
(slice 2.6).

- The classmate is active only once the learner knows at least `classmate_start_min_rules` rules.
- Planted turns: rules the learner is ready on (taught and right at least once), whose content is plantable
  (active, verified, approved items), and that the classmate does not currently know (unknown or forgotten). Rules at
  the learner's band or one above. Forgotten rules (due for re-teaching) come first; otherwise rules are drawn with
  weight (errors + 1) / (opportunities + 2), so rules the learner gets wrong come up more often.
- No-error turns: about `no_error_share` of correction turns, only on rules the classmate knows, and only while a
  rule can be planted. With nothing to plant, the turns become own-sentence production instead of a stream of
  no-error turns (R-17: the newer paper copy found 83% no-error turns).
- Interleaving: at most `interleave_max_run` consecutive correction turns on one rule.
"""
import dataclasses
import random

VERSION = "planner-1"
BANDS = ("L0", "L1", "L2", "L3", "L4", "L5")


@dataclasses.dataclass(frozen=True)
class Config:
    correction_exchanges: int = 5
    own_sentences_min: int = 2
    no_error_share: float = 0.2
    interleave_max_run: int = 2
    classmate_start_min_rules: int = 3

    def __post_init__(self):
        if not 0 <= self.no_error_share <= 0.5:
            raise ValueError("no_error_share must be between 0 and 0.5")
        if self.interleave_max_run < 1 or self.correction_exchanges < 0 or self.own_sentences_min < 0:
            raise ValueError("invalid planner config")


@dataclasses.dataclass(frozen=True)
class RuleView:
    rule_id: str
    band: str
    learner_ready: bool
    classmate_state: str  # unknown | taught | forgotten
    plantable_content: bool
    errors: int = 0
    opportunities: int = 0


@dataclasses.dataclass(frozen=True)
class Turn:
    kind: str  # planted | no_error | own
    rule_id: str | None = None


@dataclasses.dataclass(frozen=True)
class Plan:
    turns: tuple
    seed: int
    classmate_active: bool
    config: Config
    planner_version: str = VERSION


def _in_band(band: str, learner_band: str) -> bool:
    return BANDS.index(band) in (BANDS.index(learner_band), BANDS.index(learner_band) + 1)


def plan_session(*, rules, learner_band: str, seed: int, config: Config | None = None) -> Plan:
    config = config or Config()
    if learner_band not in BANDS:
        raise ValueError(f"learner_band must be one of {BANDS}")
    rng = random.Random(seed)
    ready = [r for r in rules if r.learner_ready and r.plantable_content]
    active = len(ready) >= config.classmate_start_min_rules
    eligible = [r for r in ready if _in_band(r.band, learner_band)]
    plantable = [r for r in eligible if r.classmate_state in ("unknown", "forgotten")]
    known = [r for r in eligible if r.classmate_state == "taught"]

    turns: list[Turn] = []
    if active:
        forgotten = sorted((r for r in plantable if r.classmate_state == "forgotten"), key=lambda r: r.rule_id)
        for _ in range(config.correction_exchanges):
            want_no_error = bool(known) and rng.random() < config.no_error_share
            if not plantable:
                # R-17: nothing to plant -> production practice, at most one no-error check
                if known and not any(t.kind == "no_error" for t in turns):
                    turns.append(Turn("no_error", _pick(rng, known, turns, config)))
                else:
                    turns.append(Turn("own"))
                continue
            if want_no_error:
                turns.append(Turn("no_error", _pick(rng, known, turns, config)))
                continue
            due = [r for r in forgotten if not any(t.rule_id == r.rule_id for t in turns)]
            choice = due[0] if due and not _breaks_run(due[0].rule_id, turns, config) else None
            turns.append(Turn("planted", choice.rule_id if choice else _pick(rng, plantable, turns, config)))
    else:
        turns += [Turn("own") for _ in range(config.correction_exchanges)]
    turns += [Turn("own") for _ in range(config.own_sentences_min)]
    return Plan(tuple(turns), seed, active, config)


def _breaks_run(rule_id, turns, config) -> bool:
    recent = [t.rule_id for t in turns if t.kind in ("planted", "no_error")][-config.interleave_max_run:]
    return len(recent) == config.interleave_max_run and all(r == rule_id for r in recent)


def _pick(rng, pool, turns, config) -> str:
    options = [r for r in pool if not _breaks_run(r.rule_id, turns, config)] or pool
    weights = [(r.errors + 1) / (r.opportunities + 2) for r in options]
    return rng.choices(options, weights=weights, k=1)[0].rule_id
