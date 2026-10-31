# SETU Tutor — mid-submission report (31 Oct 2026)

Hindi-first Telugu tutor in which the learner teaches a weaker AI classmate (Raju) by correcting his Hindi-transfer
errors. Specification: paper "Teaching the Machine in Your Mother Tongue" (v8) and the Phase 0 package in `docs/`.
Supporting files: [architecture](architecture_summary.md) · [datasets](dataset_register.md) ·
[experiment design](experiment_design.md) · [results](experiment_results.md) ·
[challenges](challenges_and_mitigation.md) · [timeline](final_submission_timeline.md) · [demo guide](demo_guide.md).

## 1. Progress

| Phase | Implementation | Evaluation |
|---|---|---|
| 0 Spec package (PRD, ladder, session/exchange, architecture, data model, metrics, ~230-row traceability matrix, ADRs) | complete | approved by the team |
| 1 Foundations (Postgres roles, OutcomeWriter, hash-chained ledger, auth, Hindi catalog + lint, content importer) | complete | contract tests pass |
| 2 Deterministic core (normaliser, checker with 4 verdicts, leak filter, planner, FSRS + mastery tracker, leveler v0, Stage-A suite + scorecard, OKF export) | complete | held-out scorecard: 5 metrics pass, **M-09 fails**, 13 not measurable yet |
| 3 Learner slices S1–S8 (letters, aksharas, words, chunks, correction exchange, re-teaching, placement + ladder, scenes) | complete | module tests only; no learner data |
| 4.1 Teacher console I (native review, unsure queue) | complete | tests |
| 4.2 Rule review/promotion, variants, κ | implemented, paused (commit `8f0bf24`, docs pending) | tests |
| Mid-submission sprint: self-hosted model client; Raju, coach, friend model integration; demo DB; simulator; generation-baseline harness | implemented | agents tested with a test mock only; simulator run; **no real-model run yet** |

Commits: one per slice on `redesign/phase0-spec` (`git log --oneline`, 30+ commits). Tests: see §10.

## 2. Datasets

See [dataset_register.md](dataset_register.md). In short: the only content in use is the team's own draft bank
(25 rules / 49 items; 48 letters, 489 aksharas, 28 words, 32 chunks, 4 scene scripts), all unreviewed. IndicCorp v2,
IndicGEC, the LTRC parallel corpus, Aksharantar/IndicXlit, the Kanojia cognate list and the textbooks are
**planned, not yet used**; their licences are still to be checked. Simulated learners are generated profiles.

## 3. Baselines

- **Learning conditions:** A full SETU (reverse learning), B the same content without correcting a classmate
  (matched error examples), C conventional tutor — [design](experiment_design.md) §1.
- **Generation baselines:** prompt-only vs blind resampling vs tool-assisted Raju, on 29 planting cases — harness
  `setu/research/generation_baselines.py`; **not run** (no endpoint during the sprint).

## 4. Ablations

Raju forgetting on/off; progressive hints vs direct answers; no-error share 0 / 0.2 / 0.4; own sentences 2 vs 0;
A-only assumed effects on/off; half-life sensitivity. All **ran in the simulator**; results in §5.

## 5. Results (simulation — not human evidence)

n = 100 simulated learners per condition (20 matched profiles × 5 seeds). Day-7 cue-free recall:

| | A full SETU | B no reverse learning | C conventional |
|---|---|---|---|
| Recall d7, mean ± SD | 0.046 ± 0.024 | 0.019 ± 0.011 | 0.051 ± 0.025 |
| Paired difference | A−B **+0.027** [+0.023, +0.032], d_z 1.23 | B−C −0.032 [−0.036, −0.028] | A−C **−0.005** [−0.009, −0.001], d_z −0.25 |

- A beats B on recall, transfer and detection; A is slightly **below** C on recall (equal on transfer) — the same
  pattern the newer paper's v0 simulation reported.
- A's detection advantage comes entirely from the assumed noticing effect (it vanishes when that is switched off);
  its recall advantage over B comes from cued production vs restudy.
- Own sentences matter most; direct answers instead of hints lower recall everywhere; Raju forgetting off lowers
  A's day-7 recall; the no-error share does not change recall in this model.
- Full tables, CIs and all ablations: [experiment_results.md](experiment_results.md); raw:
  `reports/simulation/results.json`. No graphs (no plotting library installed); tables only.

## 6. Challenges · 7. Mitigation

See [challenges_and_mitigation.md](challenges_and_mitigation.md): Telugu validation, native reviewers, model
hosting, hallucinated Telugu, answer leakage, checker uncertainty (M-09), simulator limits, integration.

## 8. Timeline

See [final_submission_timeline.md](final_submission_timeline.md). Phase 5 (speech, extended safety) and Phase 6
(human study) are **deferred, not started**.

## 9. Limitations

- **The simulation results are not evidence that SETU or reverse learning helps human learners.** The effects are
  assumptions; time on task is not matched; day-7 values sit near the floor.
- No Telugu content has native-speaker review; real learners see nothing outside the demo database.
- No real model output has been evaluated; the agents were tested with a scripted mock (labelled as such).
- The checker's unsure rate fails its gate (0.182 > 0.15).

## 10. Verification at submission time

See the final section of the sprint report (tests, lints, commit, push) — recorded in
`docs/implementation/implementation-plan.md` §7.
