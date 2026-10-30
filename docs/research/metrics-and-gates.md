# Metrics and release gates

Thresholds are frozen in `research/thresholds.yaml` before any results are seen. Its hash is recorded for each study.

- System metrics are computed on the **held-out** Stage-A split and reported **per direction**.
- Learner metrics are reported for **every** condition, including misses.
- Targets are never relaxed quietly. A failed gate is reported, a revised threshold is preregistered for a later version, and post-hoc changes are labelled exploratory. [X-GATE-02]

IDs match the traceability matrix (§15).

## 1. Definitions

| ID | Metric | Definition (numerator / denominator) | Target | Gate |
|---|---|---|---|---|
| M-01 | Leak rate | Shown classmate sentences with an unseen word, an unknown rule applied correctly, or an answer/explanation leak, judged by the oracle labeller on held-out cases plus teacher spot-check / shown classmate sentences | < 2% **and** below prompt-only | G2 |
| M-02 | Planting precision | Planted turns with exactly one error of the planned rule (teacher-verified sample) / planted turns | ≥ 0.8 | G2 |
| M-03 | Persona breaks | Turns where the classmate acts as teacher, explains, or speaks out of role / turns | ≤ 5% | G2 |
| M-04 | Due rule planted again | Due rules re-planted within the next session / due rules | ≥ 0.95 | G2 |
| M-05 | No-error correctness | No-error turns with zero errors / no-error turns | 100% | G2 (safety) |
| M-06 | State integrity | Classmate state changes preceded by a checked correct fix or teacher resolution / all state changes | 100% | G2 (safety) |
| M-07 | Wrong fixes caught | Wrong fixes not marked correct / wrong fixes (held-out, teacher-labelled) | ≥ 0.9 | G2 (safety) |
| M-08 | Right fixes rejected | Right fixes marked wrong / right fixes | < 5% | G2 |
| M-09 | Unsure rate | Unsure / all checked answers | < 15% | G2 |
| M-10 | First-draft pass rate | First drafts passing the filter / turns, per variant | Reported | — |
| M-11 | Bank-fallback rate | Turns falling back to the bank / turns, per variant | Lowest with tools | G2 (report) |
| M-12 | Model calls per turn | Mean and max | ≈ 1–2 | G2 |
| M-13 | Model calls per 12-exchange session | Mean and max | ≤ 48 | G2 |
| M-14 | Successful attacks | Red-team cases that change a verdict, memory, mastery or classmate state | 0 | G2 (safety) |
| M-15 | Unsafe text shown | Count and examples | Reported | — |
| M-16 | Checker vs teacher | Cohen's κ on held-out labelled answers | ≥ 0.6 | G2b (before the pilot) |
| M-17 | Unsure changed mastery | Count | 0 | G2 (safety) |
| M-18 | Hints giving the answer | Hints failing the oracle no-answer check, teacher-verified sample / hints | < 2% | G2 |
| M-19 | Solved after one hint | Learners correct on the attempt right after hint 1 / hinted attempts | ≥ 50% | Pilot |
| M-20 | Hint quality | Mean teacher rating (1–5) | ≥ 4 | G2b |
| M-21 | Friend out-of-band words | OOV tokens in shown friend lines / tokens | < 5% | Friend gate |
| M-22 | Hindi share | Hindi tokens / tokens in the friend's lines per session | Reported | — |
| M-23 | Tracker prediction | AUC and log-loss of next-attempt correctness, vs BKT, on pilot or sim logs | Beats BKT | Before claiming |
| M-24 | FSRS prediction | Recall prediction log-loss vs SM-2 | Beats SM-2 | Before claiming |
| M-25 | ASR WER | On Hindi-accented Telugu, vs Whisper | Below Whisper | Speech gate |
| M-26 | Sound check vs teacher | κ | ≥ 0.6 (when evaluated) | FW-P20 |
| M-27 | Loop latency | p95 seconds per exchange | < 10 s | G2 |
| M-28 | Cost per session | GPU-seconds and calls | Reported | — |
| M-29 | Reviewer agreement | κ on error category (and band) | ≥ 0.6 | G3 |
| M-30 | Contrast validity | Precision and recall of predicted vs observed error types vs the permutation and average-of-others baselines | Beats both before any predictive claim | Roadmap |
| M-31 | Simulated recall | Cue-free recall at days 0, 1, 2, 7 by condition | Reported | Stage A2 |
| M-32 | Learning from unchecked answers | Simulated acquisitions without a correct verdict | 0 | Stage A2 (safety) |
| M-33 | Primary learner outcome | One-week cue-free production per rule by condition | Hedges' g + 95% CI | Pilot |
| M-34 | Immediate post-test | by condition | Reported | Pilot |
| M-35 | Transfer | Unseen sentences, by condition | Reported | Pilot |
| M-36 | False alarms | Edits on no-error turns / no-error turns | Reported by condition | — |
| M-37 | Copy rate | Planted-error patterns in the learner's later production / opportunities, per rule | < 5% per rule | Pilot safety |
| M-38–40 | SUS · time on task · would use again | — | Reported | — |
| M-41–42 | Interviews · commitments | Count, plus a list of commitments | 5–8 · reported | — |
| M-43 | Blind marking agreement | κ between raters | ≥ 0.6 | Pilot analysis |
| M-44 | Rule review form | Distributions | Reported | — |
| M-45 | Naturalness | Mean teacher rating of classmate and friend Telugu | ≥ 4/5 | G2b |
| M-46 | Selective flip score [P8b] | FT − ½(FM + FG): F = share of trials where the classmate comes to know the rule after targeted (correct fix), misaligned (another rule's correct sentence) or generic ("this is wrong") feedback | Reported (= 1 by construction; a regression guard) | — |
| M-47 | RMSE / controllability [P8b] | Per shown sentence: may the classmate know the rule (target) vs is the sentence correct | Reported | — |
| M-48 | Guidance responsiveness [P8b] | Correct fixes after which the classmate is right on that rule at its next turn / correct fixes | Reported | — |
| M-49 | Scorecard [P8b] | One command lists every metric vs its target, plus "failed" and "not measured" | Generated | Every gate |
| M-50 | Retention by skill [X] | Cue-free recall at delay per skill and modality | Reported | — |
| M-51 | Leveler agreement [X] | κ with teacher bands | ≥ 0.6 before "validated" | Roadmap |
| M-52 | Placement accuracy [X] | Placed skills confirmed at first review / placed skills | Reported | — |
| M-53 | Time to mastery; prerequisite revisit rate [X] | — | Reported | — |
| M-54 | Latin script in the learner UI [X] | Visible Latin characters in E2E crawls | 0 | G1 |
| M-55 | IndicGEC robustness [P-DATA-04] | False accept / false reject on native pairs | Reported | — |

**Labelling note.** On held-out cases, "leak" and "planting" are judged by a deterministic oracle plus a teacher-labelled sample. An LLM is never used to grade.

## 2. Gates

| Gate | Opens | Requires |
|---|---|---|
| **G0** | Implementation | User approval of this package |
| **G1** | Learner UI in internal testing | Schema and contract tests pass; M-54 = 0; OutcomeWriter-only writes (TS-AUTH) |
| **G2** | Internal dogfooding with the real model | Held-out: M-01, M-02, M-03, M-04, M-05 = 100%, M-06 = 100%, M-07, M-08, M-09, M-12, M-13, M-14 = 0, M-17 = 0, M-18, M-27 |
| **G2b** | Teacher-facing quality | M-16, M-20, M-45 with teacher labels |
| **G3** | Any learner exposure | Every active rule `verified` + teacher-approved (two speakers per language, κ M-29 reported); content counts meet the study's needs |
| **G4** | The pilot | Ethics approval, consent forms, facilitator script, preregistration, data-protection plan |
| **G-speech** | Speech features | M-25; speaker review of the voices |
| **G-friend** | LLM native friend | M-21, M-45 |

A module that misses its gate is labelled **built, not evaluated** and its feature flag is off for learners. [P-PLAN-03]

## 3. Reporting

`research scorecard --split heldout --direction HI->TE` writes `reports/scorecard-<date>.md` with:
- every metric's value, n, 95% CI where relevant, and target;
- pass / fail / not measured;
- the versions (model, prompt, rules, checker, tokenizer).

Every milestone report quotes the scorecard as it is.
