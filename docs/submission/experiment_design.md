# Experiment design (mid-submission)

## 1. Main comparison: does reverse learning help? (exploratory simulation)

| Condition | What the simulated learner does | Matched on |
|---|---|---|
| **A — full SETU** | Corrects Raju's planted errors (real planner-1 plan: planted, no-error and ≥ 2 own-sentence turns), "why?" after every third correct fix | same 6 rules, same rule sequence, same number of exchanges (3 sessions × 7), same feedback after a miss, same forgetting |
| **B — SETU without reverse learning** | Sees the same erroneous sentence with its correction and explanation, then types the corrected sentence while it is visible; own-sentence turns as in A | as A |
| **C — conventional tutor** | Writes the sentence for the Hindi meaning; the tutor corrects the learner's own errors | as A |

- **Learners:** 20 matched simulated profiles per condition per seed × 5 seeds = **100 per condition** (the same
  profiles in every condition; common random numbers). Profiles: knowledge k ~ Beta(2, 5), Hindi-transfer habit
  ~ U(0.3, 0.8), error noticing ~ Beta(2, 4) per rule.
- **Schedule:** practice on days 0, 1, 2; tests on days 0, 1, 2 (after that day's practice) and 7 (virtual time).
- **Outcomes:** cue-free recall of practised rules; transfer (production for unseen meanings, with stronger habit
  interference); noticing errors in unseen sentences; hints; incorrect corrections; false alarms; own-sentence
  count; time on task (assumed seconds per exchange type); expected model calls.
- **Analysis:** mean, SD and 95% CI per condition; paired differences (same profiles) with 95% CI and Cohen's d_z.
- **Code:** `setu/research/simulator.py` (`sim-0.1`), `python -m setu.research.simulator`; results in
  `reports/simulation/results.json`; tests in `tests/unit/test_simulator.py` (reproducible; equal opportunities;
  with every learning effect switched off the conditions cannot differ).

### Assumptions (all in `Params`; none tuned after seeing results except adding the labelled sensitivity run)

| Effect | Value | Applies to |
|---|---|---|
| Cue-free production with feedback (testing effect) | 0.15 of the remaining gap | A own turns, B own turns, C every turn |
| Producing a correction with the rest of the sentence as a cue | 0.11 | A planted turns |
| Typing a visible answer (restudy) | 0.06 | B example turns, direct-answer ablation |
| Second attempt after a hint | 0.09 | all (after a miss) |
| Seeing an error next to its correction lowers the Hindi habit | 0.08 | A planted, B examples, C own errors |
| Self-explanation ("why?") | 0.04 | A only — **assumed** |
| Noticing practice | 0.08 | A only — **assumed** |
| Memory half-life / spacing gain | 1.5 days / ×1.6 per later-day success | all |

The two A-only effects are hypotheses of the paper, not established findings; ablation `no_mechanism_bonus`
switches them off.

## 2. Ablations (same simulator)

| Ablation | Hypothesis | Change |
|---|---|---|
| `raju_forgetting_off` | Re-planting forgotten rules adds spaced retrieval | Raju never forgets |
| `direct_answers` | Progressive hints beat showing the answer | answer shown after a miss |
| `no_error_share_0`, `_0.4` | No-error turns trade practice for detection | share 0 or 0.4 (default 0.2) |
| `own_sentences_0` | Own sentences carry most production practice (R-17) | `own_sentences_min` 0 |
| `no_mechanism_bonus` | How much of A's result comes from the assumed A-only effects | explain and noticing gains 0 |
| `sensitivity_half_life_4` | Day-7 floor effect | half-life 4 days for all |

## 3. Raju generation baselines (model)

Prompt-only, blind resampling (≤ 3) and tool-assisted generation (≤ 3, filter reasons fed back) on the same 29
HI→TE planting cases; metrics: valid rate, planting precision, leakage, vocabulary violations, fallback rate, calls,
latency, tokens. `python -m setu.research.generation_baselines` with a self-hosted endpoint. **Not yet run** (no
endpoint was running during the sprint; see results).

## 4. Planned human study (Phase 6, not started)

Five adults, balanced Latin square over A/B/C, pre / post / one-week delayed / unseen transfer tests, blind
marking, preregistration — as in `docs/research/experiment-protocol.md`.
