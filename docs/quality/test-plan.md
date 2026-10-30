# Test plan

Every suite ID cited in the traceability matrix is defined here. Rules for all suites:
- **Mocks and fixtures come before live models.** CI never calls a real model or any external API. Model keys are unset in the CI environment, and an egress test fails if any non-allow-listed host is contacted.
- **A test is only reported as passing if it ran.** Results are quoted from the CI output.
- **Safety-critical suites (marked ★) block merge.**
- **Held-out Stage-A cases run only at gates** (E-17).

## 1. Layers

| Layer | Tooling | Runs |
|---|---|---|
| Unit (pure domain) | pytest, hypothesis for property tests | Every commit |
| Contract (schemas, tool contracts, HTTP API) | pytest + JSON Schema + FastAPI TestClient | Every commit |
| DB integrity (grants, triggers, constraints) | pytest against Postgres in Docker | Every commit |
| Adversarial / red team | pytest with attack fixtures | Every commit |
| Stage A dev split | pytest parametrised over `tests/stage_a/dev/*.jsonl` | Every commit |
| Stage A held-out | `research scorecard --split heldout` | Gates only |
| E2E | Playwright (Hindi assertions), mock model | Every PR |
| Golden files | Normaliser, script bridge, checker verdicts on frozen inputs | Every commit |
| Simulation | `research simulate` with seeded configs | Nightly and at gates |
| Live-model evaluation | Ablation and bake-off against the self-hosted server | Phase 4+, at gates |

## 2. Suites

### Authority and data integrity

| Suite | What it proves | ★ |
|---|---|---|
| TS-AUTH-01..05 | No path from model output, agent, tool or web layer writes learning state. The OutcomeWriter accepts only checker `Verdict` objects and signed `TeacherResolution` objects. Tools have no write capability. The `setu_read` role is denied INSERT/UPDATE on learning tables | ★ |
| TS-AUTHN-* | Login, roles, access to learner/teacher/researcher routes, rate limit, dev controls researcher-only | ★ |
| TS-DB-01..03 | Constraints (verified ⇒ ≥ 2 approvals; active ⇒ verified ∧ approved); the ledger rejects UPDATE/DELETE; hash chain verifies | ★ |
| TS-FLAG-01 | `built_not_evaluated` modules are invisible in learner routes | ★ |
| TS-LOG-01..03 | Every exchange and model call stores the model, prompt, rule, item, checker, tokenizer and leveler versions, plus copy-rate, time and effort fields | |
| TS-PRIV-01..06 | No session without consent. Runtime egress is allow-listed (no commercial API client exists). The classmate prompt never contains learner text. Uploads are PII-scrubbed. Withdrawing consent deletes raw text. Logs exclude names | ★ |

### Deterministic core

| Suite | What it proves | ★ |
|---|---|---|
| TS-NORM-01..10 | NFC; zero-width characters stripped; Devanagari→Telugu with forgiveness disclosed (ए/ओ→ఎ/ఒ, final म→ం); round-trip of all bank sentences; IndicXlit adapter (pinned); romanised input never treated as correct automatically; homoglyph handling | |
| TS-CHK-* | Four verdicts. Wrong patterns are checked before accept patterns. Fragments are not correct (fixtures: "అమ్మను", "ఇంటికి"). A planted error elsewhere in the sentence → wrong (fixture: "ఇది జో నేను చదివిన పుస్తకం"). Near-miss → partial. Another item's sentence → wrong. Unseen forms → unsure. Counter-examples for DQ-06 (correct noun negation and locatives are not flagged) | ★ |
| TS-CHK-VAR | Approved written/spoken/regional variants are accepted; proposed variants are not | |
| TS-CHK-ROB | IndicGEC robustness: false-accept and false-reject reported (M-55) | |
| TS-WHY-01..12 | Concept key: valid paraphrases accepted; keyword salad ("क्या आ", "है नहीं", "ki lo") is not correct; Latin input → unsure; the score never changes classmate state | ★ |
| TS-TMR-01..06, TS-LEV-01..06 | Exact TMR with a versioned tokenizer; leveler v0 band and reason per dimension; v0 kept as baseline | |
| TS-LEAK-* | Every filter reason: OOV, NOT_ONE_ERROR, WRONG_RULE_ERROR, UNKNOWN_RULE_CORRECT, ANSWER_LEAK (incl. Devanagari and Latin transliteration), EXPLANATION, persona break, post-fix replies may use only the taught form. TS-LEAK-NE: no-error turns contain zero errors | ★ |
| TS-CLS-01..15 | The epistemic-state spec (P8b-01) line by line: no learning from unsure, wrong or partial fixes, bare "that is wrong", a why-answer, or a model statement; forgetting at p < 0.5; pre-test-known rule teachable immediately; per-learner isolation; start threshold | ★ |
| TS-PLAN-01..08 | Seeded determinism; band b/b+1; no-error share 15–25% when eligible, with production substitution otherwise; interleaving (max run 2); only active rules in learner mode; error-weighted selection | ★ (07) |
| TS-SCHED-* | FSRS (pinned) scheduling; tracker posterior and decay; due → forgotten; re-plant days later, never in the same session; baselines (BKT, SM-2) computable | |
| TS-LAD-01..10, TS-PLACE-01..06 | Unlock rule; nothing counts from time, clicks or confidence; modality tracking; prerequisite revisit; placement test-out and confirmation | |
| TS-OKF-01..03 | The export equals DB values; read-only; regenerated after events | |

### Agents and tools

| Suite | What it proves | ★ |
|---|---|---|
| TS-TOOL-01..55 | Every argument class gets its exact error string; returns `{ok, reasons}`; re-check on submit; TE-HI script swap; `check_level`; `check_hint_has_no_answer`; lookups never return the planned answer to the classmate; envelope errors (malformed JSON, unknown tool, oversized) | ★ |
| TS-AGT-01..07 | ≤ 3 calls then bank fallback; harness re-validation; guided JSON names the rule and the words; only bank examples in prompts; calls per turn and per session logged | |
| TS-LLM-01 | Client: model id configurable, timeouts, no keys in URLs, mock parity | |
| TS-COACH-01..10 | Hint 1 never contains the answer (all scripts); answer after the 2nd miss; hint-type arm honoured; fixed fallback | ★ |
| TS-FRND-01..08 | `check_level`, Hindi share, fallback to approved scene lines | |
| TS-DISP-* | Every learner-visible model string passes display checks or is replaced | ★ |
| TS-RED-01..30 | ≥ 30 attacks across learner answers and explanations, hijacked model replies, tool abuse, Unicode tricks, uploads. Zero state changes (M-14) | ★ |

### Learner flows

| Suite | What it proves |
|---|---|
| TS-SESS-01..06 | Config snapshot; mix; production ≥ 2; new-item cap; mirror tagged |
| TS-EXCH-01..12 | The 7 steps; TS-EXCH-WHY (3rd fix asks why, no state change); TS-EXCH-NE (false alarm logged); TS-EXCH-END (planted error shown corrected) |
| TS-OWN-01..06 | Frames, copy events, unsure for unseen forms |
| TS-L0, TS-L1, TS-L2, TS-L3, TS-L4, TS-L5 | Content and task coverage per band (all letters incl. ఙ ఞ ఱ ః; signs ై ౌ; lexicon frequency ranks; chunks; rule families; scenes) |
| TS-CONT-01..04, TS-AUD-01..02 | Cognate and false-friend flags; scene review status; audio consent and speaker review |
| TS-UI-CUE-01..04 | No options, word banks, pre-filled boxes or answer-bearing hints on scored items ★ |
| TS-UI-CALM | No streak, points, badge, balloon or confetti components; no emoji in learner templates |
| TS-UI-FADE, TS-UI-LAD | Reading aid fades after 3 correct per rule; ladder view has no scores and no Latin |
| TS-L10N-01..05 | Catalog lint (no `[A-Za-z]`), template lint, E2E crawl with 0 Latin characters (M-54), reason codes rendered via catalog, teacher UI in Hindi ★ |
| TS-A11Y-* | axe-core on key pages; keyboard-only flow; `lang` attributes |
| TS-E2E-* | Beginner, returning, placed, review-due, exchange, teacher settlement, study participant |
| TS-API-*, TS-API-IDEMP, TS-API-LEAK | Schemas; idempotency; no `planted`, `turn_type` or answer in any response before the learner answers ★ |
| TS-DIR-* | Direction stored per learner; TE→HI bank imports; mirror items in Devanagari pass the tool |
| TS-PERF-01 | p95 exchange latency with a mock model (budget for the real model measured at G2) |

### Content and teacher

| Suite | What it proves |
|---|---|
| TS-BANK-01..14 | Schema; separate validity and evidence fields; immutable versions; lifecycle; LLM proposals stay `model_predicted`; TH-GEN-01 and TH-CLU-01 imported as uncertain; every family present; content counts dashboard; citations stored |
| TS-DSR-01..02 | Every source referenced by content has a register row; `to-check` sources are blocked from learner content |
| TS-TQ-01..06 | Queue settlement, single application, concurrency, variant needs a second approval |
| TS-TCH-REV, TS-TCH-KAPPA, TS-TCH-VAR, TS-TCH-UP, TS-TCH-AN-01..04, TS-TCH-OVR, TS-TCH-EXP | Console features F1–F8 (teacher-console.md) |

### Research

| Suite | What it proves |
|---|---|
| TS-SUITE-META, TS-SUITE-SPLIT, TS-SUITE-LEAK | ≥ 150 cases with group tags; held-out manifest hash unchanged; dev code never reads held-out labels; no overlap between test items and build data ★ |
| TS-TEB | TransferErrorBench datasheet and format |
| TS-ABL-01..02, TS-BAKE-01 | Ablation harnesses (prompt-only, resampling, tool loop); per-direction model bake-off |
| TS-EXP-PRED, TS-EXP-HINT, TS-EXP-FORGET, TS-EXP-CONF, TS-EXP-PLAN | Experiment flags: predict-then-check, hint-type arm, forgetting on/off, confidence rating, hidden plan; each is off by default and reported separately |
| TS-STUDY-01..09 | Balanced Latin square; identical aids, hints and time box across A/B/C; single mode per condition; test items from the held-out pool; blinded export (shuffled, random ids, no condition); pre-test ceiling check |
| TS-SIM-01..04, TS-SIM-REPRO | Config schema; acquisition only after a correct verdict (M-32 = 0); fault regressions (matched feedback; recognition ×1.2); reproduce v0 Table 9 with seeds |
| TS-SCORE-01 | The scorecard lists every metric with value, n, CI, target and status |
| TS-ANL-POW, TS-ANL-VAL, TS-ANL-* (one per RQ), TS-ANN-01, TS-ANA-01, TS-SPCH-*, TS-SPCH-WER | Analysis scripts dry-run on simulated data; annotation κ; analyser 50-sentence evaluation; speech adapters and WER vs Whisper |

## 3. Stage A suite composition (target ≥ 150)

| Group | Seed from LMA `tests_v0` | Target |
|---|---|---|
| Leak | 16 | 45 |
| Planting (incl. no-error) | 10 | 35 |
| Checker | 26 | 45 |
| Forgetting and ledger | 9 | 20 |
| Copy | 2 | 5 |
| **Total** | **63** | **≥ 150** |

The split is 30% held out by a SHA-256 hash of `case_id`, frozen once. Both directions are covered, with TE→HI reported separately.

## 4. Regression references from the legacy app

The 138 tests in the setu-tutor baseline are kept under `legacy/tests` and still run until each legacy feature is migrated or deliberately retired (implementation-plan.md §4). Tests that assert the defects are rewritten to assert the fix. For example, `test_raju.py:49` accepted "सही जवाब" in a hint.

## 5. Amendment A1 suites

| Suite | What it proves | ★ |
|---|---|---|
| TS-RAJU-01..20 | Closed turn types; Hindi lines equal catalog entries; reason codes `PERSONA_ASSISTANT`, `PERSONA_TEACHER`, `FORMAT`, `GLOSS`, `UNSAFE`, plus existing leak reasons; decoding-limit fallback; prompt has no assistant framing and no learner text; 200-draft mock sweep with injected assistant outputs → 0 shown | ★ |
| TS-MEM-SEL-01..08 | Policy table per unit type; ranking by posterior; exploration logged; teacher-model choice limited to candidates; harmful aids excluded | |
| TS-MEM-GRD-01..15 | Grounding validator: wrong pairs, ungrounded Telugu, Latin, grammar claims, missing contrast, answer reveal; held-out adversarial set (M-57 = 0) | ★ |
| TS-IMG-01..12 | OCR rejects text in any script; overlay rendered as DOM/SVG text; provider payload allow-list (concept-only); ≤ 3 candidates per concept; safety and contrast checks; no image client in the runtime app | ★ (01, 03) |
| TS-MEM-LIB-01..06 | Fallback for every active concept; cache hits serve the same approved asset; no runtime generation calls; immutable versions; retirement | ★ (01) |
| TS-MEM-A11Y-01..05 | Alt text and audio alternative present; contrast; no colour-only meaning; keyboard; captions | |
| TS-MEM-MEAS-01..08 | Viewing never changes mastery; cue-level logging; micro-randomisation is seeded and balanced; lure matching logs misassociations; effect estimator against a known fixture | ★ (01–03) |
| TS-MEM-FADE-01..08 | Cue ladder steps; lapse restores level 2 once; tests at level 0; no aid before due-review answers | ★ |
| TS-SCHED-MEM-01..04 | FSRS rating capped at Hard when cue > 0; such attempts are excluded from unlock | ★ |
| TS-MEM-REV-01..05 | Review-count rules per aid kind; approval blocked without alt text or with an OCR hit | |
| TS-MEM-COST-01..03 | Budget ceiling enforced; cost ledger rows; batch hard stop | |
| TS-PRIV-07 | Runtime egress allow-list contains no image or text generation provider; pipeline payloads contain no learner fields | ★ |
| TS-STUDY-10 | Aid exposures identical across reverse-learning A/B/C (M-67) | ★ |
| TS-MSTUDY-01..08 | Study M machinery (memory-experiment-protocol.md §9) | |
| TS-SIM-MEM-01..03 | Simulator aid parameters drive scheduling, fading and logging reproducibly; no mastery from viewing in simulation; reports labelled as machinery tests | |
