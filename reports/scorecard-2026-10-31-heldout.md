# Scorecard 2026-10-31 (heldout split, 185 cases)

> Module-test numbers come from cases the team generated from the same content the system uses, so they test the machinery and are optimistic. They are not evidence about learners or about any language model.

| Metric | Value | n | Target | Status | How |
|---|---|---|---|---|---|
| M-01 | — | — | max 0.02 | not measured | needs model drafts (Phase 4) and the prompt-only baseline |
| M-02 | — | — | min 0.8 | not measured | needs model drafts (Phase 4) and teacher verification |
| M-03 | — | — | max 0.05 | not measured | needs model drafts (Phase 4) |
| M-04 | — | — | min 0.95 | not measured | needs sessions over time (simulator, Phase 4) |
| M-05 | 1.000 | 14 | min 1.0 | pass | planting cases: no-error sentences pass with zero errors |
| M-06 | — | — | min 1.0 | not measured | guarded by database triggers and TS-CLS / TS-AUTH tests; a rate needs logged sessions |
| M-07 | 1.000 | 34 | min 0.9 | pass | checker cases expected wrong or not correct |
| M-08 | 0.000 | 32 | max 0.05 | pass | checker cases expected correct |
| M-09 | 0.182 | 66 | max 0.15 | **FAIL** | unsure on checker cases that have a known answer |
| M-12 | — | — | max 2.0 | not measured | needs the agent loop with a model (Phase 4) |
| M-13 | — | — | max 48 | not measured | needs the agent loop with a model (Phase 4) |
| M-14 | 0 | 25 | max 0 | pass | injection inputs judged correct |
| M-16 | — | — | min 0.6 | not measured | needs teacher labels (145-row sheet not yet labelled) |
| M-17 | — | — | max 0 | not measured | guarded by the OutcomeWriter and TS-CLS tests; a rate needs logged sessions |
| M-18 | — | — | max 0.02 | not measured | needs coach hints (Phase 3–4) |
| M-27 | — | — | max 10.0 | not measured | needs the running loop with a model (Phase 4–5) |
| M-54 | 0 | — | max 0 | pass | Hindi lint over catalog and templates |
| M-56 | — | — | max 0 | not measured | needs model drafts (Phase 4) |
| M-57 | — | — | max 0 | not measured | needs memory-aid drafts and the grounding validator (Phase 4) |

Failures: 0

Versions: checker checker-1, normaliser normaliser-1, tokenizer tokenizer-1, leveler leveler-v0, planner planner-1, tracker tracker-1, fsrs fsrs-6.3.2
Thresholds sha256: 407d69f8503d26af3ca2f2c808fbd5624564bcecdd2d20925a78863d5c9ef4b0
