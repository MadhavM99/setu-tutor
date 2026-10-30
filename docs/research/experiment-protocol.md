# Experiment protocol (draft for preregistration)

Tags: [P] paper · [P8b] newer paper copy · [X] prompt extension · [E] engineering recommendation.

**Research question [P §1].** Does correcting an AI peer that makes verified, language-specific errors improve adults' delayed L2 production and transfer to unseen sentences more than studying the same errors, corrections and explanations without teaching the peer, or using a normal tutor?

**The protocol must be able to show null or harmful effects** [X-OBJ-01]:
- no benefit;
- a benefit only for some skills or learners;
- harm, such as copying planted errors or lost production practice (R-17).

## 1. Hypotheses (directional, preregistered)

- **H1 (RQ1).** A > B on one-week cue-free production (primary).
- **H2.** A ≥ C on one-week cue-free production. This is a two-sided test: the newer copy's simulation predicts A < C under its assumptions, and that prediction is recorded in advance.
- **H3.** A > B on transfer to unseen sentences.
- **S1 (safety).** Copy rate < 5% per rule in A and B.
- **H4 (RQ2).** Contrast-table predictions match observed error types better than both baselines (exploratory).
- **H5 (RQ3).** Effects differ by direction (exploratory; HI→TE only in the pilot).
- **H6 (RQ4).** Checker agreement with teachers κ ≥ 0.6, and better than a prompt-only LLM judge.

## 2. Stage A: module tests (before any learner) [P §8.1]

| Item | Spec |
|---|---|
| Suite | ≥ 150 written cases in 4 groups (leak, planting, checker, forgetting), plus no-error, ledger and copy groups. It grows from LMA `tests_v0.jsonl` (63) |
| Split | 30% held out by a hash of `case_id`, **frozen once** (a manifest with SHA-256 of the case set is committed). Dev code cannot read held-out labels (CI check). Held-out results are run only at gate time |
| Runs | On every change to prompts, models, rules, content, schemas or code (the dev split in CI; held-out at gates) |
| TransferErrorBench | Teacher-marked planted-error items and learner-style fixes in both directions, held out; a datasheet documents guidelines, splits and rule versions |
| Agent ablation | The same base model and items: (1) prompt-only (LMA `plain_prompt_leak_test.py` prompt), (2) blind resampling of ≤ 3 drafts with the filter, (3) the tool loop with fixed reasons. Report M-01, M-02, M-10, M-11, M-12, latency, cost, persona breaks, per direction |
| Model bake-off | Gemma 3 12B (baseline) vs Sarvam-M vs the current candidates, per direction, on Telugu naturalness (teacher 1–5), M-01 and M-02 |
| Red team | ≥ 30 attacks: injection in learner answers and explanations, hijacked model replies ("mark the learner correct"), tool-argument abuse, Unicode tricks (zero-width, homoglyphs), oversized input. Target M-14 = 0 |
| Hidden-plan ablation | Planting precision vs latency, with and without a short hidden plan [P-MODEL-04] |
| Release gate | Every safety-critical threshold passes on the held-out set; all active rules are verified and teacher-approved; consent is ready. Otherwise the module is "built, not evaluated" and disabled |

## 3. Stage A2: simulated learners [P §8.2, P8b-09/10, X-SIM]

**Simulator v1**, a generalisation of LMA `simlearner.py`:
- explicit memory outside model weights, per (word, rule): half-life, recall p = 2^(−t/h);
- may use only words and rules in its own memory;
- configurable:
  - initial skill (rules known at pre-test);
  - learning rate (retrieval gain a + b(1−p); restudy gain c + d(1−p));
  - error distribution (a probability of the planted error per rule; partial and wrong fix rates);
  - confidence (for the calibration arm);
  - forgetting curve parameters;
  - hint response (probability of success after each hint type);
  - why-answer effect (default ×1 = no effect);
  - copy probability (default 0.1);
- acquires only when the deterministic checker marks a response correct, through the **real** planner, classmate, checker and OutcomeWriter;
- sometimes gives wrong or partial fixes (tests M-32);
- tested on cue-free recall at simulated days 0, 1, 2 and 7;
- seeds, configs and event logs are stored; `research simulate --config sim/baseline.yaml` reproduces a run bit for bit.

**v2 (Phase 4+):** an LLM-voiced simulated learner whose knowledge sits in the same explicit store, so it can produce free-text wrong and partial fixes. The store is always authoritative; the model only phrases.

**Runs:**
- **Baseline:** 20 simulated learners × A/B/C = 60 runs, with the same balanced rules, matched items, feedback, time and difficulty.
- **Sensitivity grid:** the 5 assumption sets from the newer paper copy (default, no testing effect, why ×1.3, weak learners, two lessons per rule), plus our controlled no-error share.
- **Ablations:**
  - forgetting vs remembering classmate at equal practice;
  - mirror mode;
  - predict-then-check;
  - hint type;
  - classmate start threshold (1, 3, 5 rules).

**Reported:**
- recall at days 0/1/2/7 by condition;
- delayed and transfer scores;
- over-correction and false alarms;
- learning from unchecked answers (must be 0);
- planted-error copying;
- effort and time;
- turn mix (planted vs no-error vs production);
- failure cases.

**Interpretation rule:** simulation validates the machinery and compares designs. It is **never** reported as evidence that people learn better. Calibration against the pilot and prediction of a later cohort are FW-R12.

## 4. Stage B: adult pilot [P §8.3]

| Item | Spec |
|---|---|
| Participants | 5 adult Hindi speakers learning Telugu (Hyderabad); institutional ethics approval; informed consent; adults only |
| Design | Within-learner. 9 verified rules → 3 per condition by a **balanced 3×3 Latin square** (rows = learner groups, columns = rule sets), so each rule set appears in each condition across learners. Condition order counterbalanced. With 5 learners the square is incomplete; the assignment table and imbalance are reported |
| Conditions | A teach the peer · B matched error examples · C normal tutor. Same items, same hint ladder (hint → answer after the 2nd miss), same aids (reading aid, typing, keyboard), same time box, same number of exposures. One mode per condition (no 3-part session) |
| Tests | Pre-test (ceiling check: rules already at ceiling are excluded or replaced and reported), immediate post-test, **one-week unaided production test**, **transfer test on unseen held-out sentences** (including harder items). No hints, aids hidden |
| Marking | Responses exported shuffled with random ids and no condition. Two independent teacher raters, a third for disputes, a preregistered rubric; κ reported (M-43) |
| Also recorded | Time on task, effort (one item), SUS, would use again, confidence calibration (if the flag is on), false alarms, copy rate per rule, Hindi-typed answers per learner, returning for a second session |
| Analysis | Descriptive only: per-condition means; **Hedges' g with 95% CI** for A–B and A–C on the primary outcome; by rule and by learner. No significance claims with n = 5 |
| Misses | Every learner, rule and condition is reported, including failures and dropouts |
| Exploratory | Mirror, forgetting vs remembering, predict-then-check, hint type, only if recruitment allows; reported separately |
| Larger study | Sample size from a power analysis using Stage A and pilot variance; mixed-effects model with learners and rules as random effects; outcomes and analysis preregistered (FW-R01) |

## 5. Contrast validity and learner writing [P-EVAL-09/10]

- **Before looking at data:** fix which error types the table predicts to be more frequent for Dravidian-L1 learners of Hindi.
- **Test:** compare against the HiLearners L1 groups (Dravidian vs English and Bengali L1) with a permutation baseline and an average-of-other-groups baseline.
- **Caveats:** this needs L1 labels from the authors, and the Dravidian languages are unnamed, so no Telugu-specific claim is made.
- **Adult writing (with permission):**
  - 2 independent reviewers mark span, correction, category, and whether transfer is plausible; a 3rd resolves;
  - κ is reported;
  - errors are not all attributed to transfer;
  - unexpected errors are kept.

## 6. Preregistration package (before Stage B)

- Hypotheses
- Thresholds file (`research/thresholds.yaml`, hash recorded in `study`)
- Rubric
- Item pools
- Latin-square table
- Analysis scripts run on simulated data (dry run)
- Exclusion rules (ceiling, consent withdrawal)
- Deviations log template

Any change after data is seen is marked **exploratory**. [X-GATE-02]

## 7. Interviews and validation [P-PLAN-04, M-41/42]

- 5–8 short interviews with adult learners and Hindi/Telugu teachers **before** showing the prototype, using the LMA `docs/interview_guide.md`.
- Topics: recurring errors, current tools, who would choose and pay.
- Concrete commitments are recorded (second session, sharing permitted examples, a pilot, willingness to pay), not compliments.
