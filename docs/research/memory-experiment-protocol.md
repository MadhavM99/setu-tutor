# Memory experiment protocol (Study M), separate from the reverse-learning study

Status: **Phase 0 amendment A1**, a draft for preregistration. Tags: [X-A1] amendment · [E] engineering recommendation. This study is **separate** from the reverse-learning study (experiment-protocol.md). There, memory support is held identical across A/B/C (memory-assistant.md §7).

## 1. Question

For adult Hindi speakers learning Telugu:
- Do verbal mnemonics, visual mnemonics with native audio, or an adaptive combination improve **delayed, unaided** recall and production, and transfer, compared with normal instruction plus retrieval practice?
- Do any of them create **incorrect associations**?

Seeing or liking an aid is **not** an outcome. [R10]

## 2. Conditions (labelled M-A to M-D to avoid confusion with reverse-learning A/B/C)

| Condition | Encoding support | Shared by all conditions |
|---|---|---|
| **M-A** Normal instruction + retrieval practice | Concept presented plainly (glyph + Devanagari twin, or word + gloss + approved example), then cue-free retrieval | Same concepts, same number of presentations, same retrieval opportunities, same time box, same feedback, same **one native pronunciation playback per item** (pronunciation is content, not a mnemonic), and the same fading to cue level 0 before tests |
| **M-B** Verbal mnemonics and stories | M-A plus an approved Hindi story or keyword association (or chunking text for akshara) | as above |
| **M-C** Visual mnemonics + native audio | M-A plus an approved text-free illustration with the app-rendered glyph, plus an audio association (articulation or minimal-pair contrast) | as above |
| **M-D** Adaptive combination | M-A plus the Memory Assistant policy (F-MEM-1) choosing among the M-B and M-C aids per learner and item, with exploration ε = 0 inside the study (it uses the learner's earlier-block history and population priors) | as above |

**Open decision (default stated).** The amendment bundles native audio into M-C. To avoid confounding pronunciation exposure with the mnemonic, **all conditions hear the same native pronunciation once per item**. M-C adds *association* audio: articulation cues and minimal pairs. If you want audio exclusive to M-C, the analysis must treat "visual + audio" as one package and cannot separate the two.

## 3. Materials

- Four matched **concept sets**, one per condition. Each set has:
  - 8 L0/L1 script items (letters and akshara);
  - 12 L2 lexemes, including 2 false friends.
- Sets are balanced on leveler band, frequency rank, Devanagari-twin similarity, cognate status and word length. The balance table is preregistered.
- **Every aid is approved** (G-MEM-ASSET).
- Transfer items are new words that use the learned letters or akshara, and new sentences that use the learned words. None are shown in practice.

## 4. Design

- **Within-learner**, 4 conditions × 4 concept sets, with a **4×4 balanced Latin square** (Williams design for first-order carryover) over condition order and set assignment.
- **Carryover risk:** learners may spontaneously reuse mnemonic strategies in M-A. This is measured with a post-block strategy questionnaire and reported.
- If carryover is large, the larger study switches to a **between-subjects** design (preregistered contingency).
- **Pilot:** n set by recruitment (target 8–12 adults, so the Williams square is complete at 8). It is descriptive.
- **Larger study:** sample size by power analysis on pilot variance; mixed-effects models with learners and concepts as random effects.
- **Time:** each block has a fixed time box (e.g. 12 minutes). Time on task is logged per condition. Equal practice opportunities are enforced by the session engine (the same number of retrieval prompts).

## 5. Outcomes

All tests run at cue level 0, with no aids, hints or reading aid.

| Outcome | When | Measure |
|---|---|---|
| Immediate recall | End of block | Cue-free recognition and recall (separately) |
| Retention | **1 day, 7 days, 30 days** | Cue-free recall; FSRS-independent fixed test items |
| Unaided production | 7 and 30 days | Type the Telugu for a Hindi prompt (script items: write the Telugu letter for a sound) |
| Transfer | 7 days | New examples (§3) |
| Time to mastery | During the study | Exposures and minutes until the unlock rule is met (learning-ladder.md §3) |
| Incorrect associations | All tests | Responses equal to an aid's declared lure (`aid_misassociation`), per condition; false-friend wrong-meaning rate |
| Experience (secondary) | End | Effort, preference. **Not** a learning outcome |

**Primary outcome:** 7-day cue-free production, M-B, M-C and M-D each vs M-A, reported as Hedges' g with 95% CI.

**Secondary outcomes:** 30-day retention; transfer; misassociation rate (safety threshold: no condition > M-A + 5 percentage points, preregistered); time to mastery.

## 6. Analysis and honesty

- Preregistered hypotheses: H-M1 (M-C > M-A at 7 days), H-M2 (M-B > M-A at 7 days), H-M3 (M-D ≥ max(M-B, M-C)), H-M4 (the misassociation safety threshold).
- Every condition and time point is reported, including attrition at 30 days.
- No significance claims are made from the pilot.
- Exploratory analyses are labelled as such.
- An aid type that helps immediately but not at 7 or 30 days is reported as *not* supported for retention.

## 7. Simulation (machinery only)

Simulator v1 gains aid-related parameters: encoding boost per technique, decay of that boost, misassociation probability, and fading behaviour. These test:
- scheduling;
- fading;
- logging (presented, selected, used, recalled);
- that mastery is never awarded for viewing;
- reproducibility with seeds.

**Simulated memory gains are assumptions fed into the simulator, so they are never reported as human evidence.** [X-A1]

## 8. Ethics and data

- Adults only, with informed consent covering the 30-day follow-up.
- No learner data is sent to any image service: assets are pre-generated and concept-level.
- Withdrawal deletes raw responses.

## 9. Acceptance tests for the study machinery (before G-MEM-EXP)

| Test | Checks |
|---|---|
| TS-MSTUDY-01 | The Williams square is balanced for 4 conditions and orders |
| TS-MSTUDY-02 | Equal retrieval opportunities and time box per block |
| TS-MSTUDY-03 | All conditions get exactly one pronunciation playback per item |
| TS-MSTUDY-04 | Tests are rendered at cue level 0 |
| TS-MSTUDY-05 | Test and transfer items never appear in practice |
| TS-MSTUDY-06 | Follow-up scheduler at 1/7/30 days, with reminders in Hindi |
| TS-MSTUDY-07 | Blinded export with no condition column |
| TS-MSTUDY-08 | Misassociation scoring against declared lures |
