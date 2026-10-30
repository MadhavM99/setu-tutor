# PRD — Setu: a Hindi-first Telugu tutor with a reverse-learning classmate

Status: draft for approval (Phase 0). Each statement is tagged **[P]** paper, **[X]** prompt extension, or **[E]** engineering recommendation. Source IDs refer to [`../specs/source-traceability-matrix.md`](../specs/source-traceability-matrix.md).

## 1. Problem

- Adult Hindi speakers in Hyderabad need everyday Telugu (auto stands, messes, landlords, offices), yet most cannot read the script. No tutor teaches Telugu *through* Hindi with checked feedback. [P §1, P8b-08]
- No Hindi↔Telugu learner-error corpus exists. Contrastive predictions are hypotheses, not facts. [P §1, P-TYP]
- LLM "students" prompted to be weak leak correct forms and absorb wrong teaching (the competence paradox). [P §1–2]
- The current product (audit §5) feels like a game and does not reliably teach:
  - hints reveal answers;
  - mastery comes from a single answer;
  - the checker can be fooled;
  - unreviewed AI content and English text are shown to learners;
  - learner text goes to a commercial API.

## 2. Users

| User | Description | Primary? |
|---|---|---|
| Hindi-speaking adult learning Telugu | Literate in Devanagari; may speak some Telugu words; usually cannot read or type Telugu | **Yes** [X-PRIMARY] |
| Telugu-speaking adult learning Hindi | Mirror direction; the bank, contracts and tests are kept, but there is no production journey yet | Secondary [P §1, X-PRIMARY] |
| Telugu / Hindi teacher | Reviews rules, settles unsure answers, sees class errors, overrides feedback | Yes (console) [P, X-TCH] |
| Researcher / facilitator | Runs Stage A/A2/B, assigns conditions, exports blinded data | Yes (console) [P §8] |

## 3. Jobs to be done

- **J1.** "Help me read Telugu signs and words using the Hindi letters I already know." [X-LAD-L0/L1]
- **J2.** "Teach me the words and phrases I need this week (auto, mess, landlord) and make them stick." [X-LAD-L2/L3, X-BEG-04]
- **J3.** "Show me the mistakes Hindi speakers make in Telugu, and make sure I stop making them." [P core]
- **J4.** "Let me say my own Telugu sentences and tell me reliably whether they're right." [P-SESS-04]
- **J5.** "Don't waste my time on things I already know." [X-PERS-03]
- **J6.** (Teacher) "Let me trust what the app tells learners, and correct it when it's wrong." [X-TCH]
- **J7.** (Researcher) "Let me find out honestly whether teaching the AI classmate helps." [P §8, X-OBJ-01]

## 4. Product principles

1. **Learning first, measured.** Progress shown to a learner equals demonstrated skills (cue-free, multi-item), never time, clicks or lessons opened. [X-PERS-02]
2. **Models write, rules decide.** No model grades, schedules, changes mastery or classmate state, or approves content. [P-ARCH-01, X-RULES-06]
3. **Fail closed.** Unvalidated text is never shown as correct. The fallbacks are a bank item, a request for clarification, or a teacher. [X-RULES-07]
4. **Hindi only, in Devanagari.** Telugu appears in Telugu script. Romanisation is off by default; if approved, it is optional and fades. [X-NOENG]
5. **A calm tutor, not a game.** No streaks, points, badges, balloons, confetti or mascot celebrations. [X-CALM]
6. **The learner is always the tutor; the AI is always the tutee.** The classmate is a peer, never a teacher. [P §5]
7. **Every planted error ends shown corrected.** [R-13]
8. **Honesty in research.** Thresholds are fixed in advance. Failures and null results are reported. Simulation is never presented as human evidence. [X-RULES-05, X-GATE-02]
9. **Privacy by default.** Pseudonymous IDs, our own server, no commercial model API at runtime, adults only. [P-ETH-05, D3]
10. **Memory aids support encoding; they never count as learning.** Aids are approved, grounded, text-free (images), faded, and measured by delayed cue-free recall. [X-MEM-AID]
11. **राजू is only a weaker student.** He never acts as an assistant or teacher. [X-RAJU]

## 5. Scope (first release, Phases 1–5)

**In scope:**
- **Learner app (Hindi UI)** covering:
  - onboarding with consent;
  - a placement diagnostic;
  - the personal L0–L5 ladder;
  - sessions mixing review, new items, classmate correction, no-error turns and own sentences;
  - scenes for auto stand, mess, landlord and everyday;
  - FSRS review;
  - a ladder view;
  - Devanagari reading aid and typing;
  - an on-screen Telugu keyboard.
- **Knowledge-controlled classmate** (राजू) with:
  - explicit state;
  - a leak filter with TMR;
  - a tool loop;
  - forgetting tied to the learner's tracker.
- **Coach:** fixed teacher-approved hints first; LLM drafting behind a flag.
- **Memory Assistant (स्मृति सहायक)** [X-MEM-AID, amendment A1]:
  - technique policy by unit type;
  - grounded Hindi mnemonics;
  - text-free illustrations from an approved library, with app-rendered glyphs;
  - native audio and sound associations;
  - chunking and decomposition;
  - cue fading;
  - FSRS integration;
  - per-aid effect measurement;
  - non-generative fallbacks.
- **Native friend (रवि):** bank-only first; LLM behind a gate.
- **Deterministic core:** normaliser, checker (4 verdicts), planner, scheduler, OutcomeWriter, ledger, OKF export.
- **Teacher console (Hindi):**
  - rule review with two raters plus a third;
  - κ;
  - the unsure queue;
  - variants;
  - analytics per opportunity;
  - override;
  - exports.
- **Research console:**
  - study mode A/B/C;
  - a balanced Latin square;
  - pre-, post-, delayed and transfer tests;
  - blinded export;
  - the simulator;
  - the scorecard.
- **Speech:** ASR/TTS adapters behind flags; native audio for the top 100 items once consented.
- **TE→HI direction:** data, contracts and tests; mirror mode as an exploratory flag.

## 6. Non-goals (first release)

- Gamification of any kind. [X-CALM]
- Per-learner or runtime image generation; unreviewed aids shown to learners. Runtime verbal mnemonics stay off until G-MEM-RT. [ADR-0005]
- Free conversation with राजू. [ADR-0006]
- Any commercial model API at runtime. [D3]
- Fine-tuning, LoRA, DPO or activation steering. [P-MODEL-03, FW-P21/22]
- Per-sound pronunciation scoring. [X-SPEECH-04, FW-P20]
- Children or classroom deployment. [P-ETH-07]
- Claims that the leveler or ladder is validated before it passes κ ≥ 0.6. [X-LEV-03]
- Copying textbook sentences without permission. [P-DATA-02]
- Production TE→HI learner journey (exploratory only).

## 7. Success measures

**Release gates** (see [`../research/metrics-and-gates.md`](../research/metrics-and-gates.md)):

| Metric | Target |
|---|---|
| Leak rate | < 2% and below the prompt-only baseline |
| Planting precision | ≥ 0.8 |
| No-error correctness | 100% |
| State integrity | 100% |
| Wrong fixes caught | ≥ 0.9 |
| Right fixes rejected | < 5% |
| Unsure rate | < 15% |
| Injection attacks that change state | 0 |
| Hints that give the answer | < 2% |
| Latin-script strings in the learner UI | 0 |
| Active rules verified and teacher-approved | all |

**Learner outcomes** (pilot, descriptive):
- one-week cue-free production by condition (Hedges' g, 95% CI);
- transfer to unseen sentences;
- copy rate < 5% per rule;
- false alarms.

**Memory Assistant:** M-56..M-63 and M-68; Study M outcomes M-64..M-66 (memory-experiment-protocol.md).

**Product signals:**
- returning for a second session;
- SUS;
- would use again;
- concrete commitments from 5–8 interviews.

## 8. Feature list

Each feature has a full template spec in the file named.

| Feature | Spec |
|---|---|
| F-ONB Onboarding, consent, profile | learner-journeys.md J-Beginner, data-model.md |
| F-PLACE Placement diagnostic | learning-ladder.md §5 |
| F-LAD Ladder and ladder view | learning-ladder.md |
| F-SESS Session composer | session-and-exchange.md §2 |
| F-EXCH Correction exchange | session-and-exchange.md §3 |
| F-OWN Own sentence | session-and-exchange.md §4 |
| F-REV Spaced review / re-teaching | learning-methodology.md §3, session-and-exchange.md §5 |
| F-SCENE Scenes and native friend | session-and-exchange.md §6 |
| F-SCRIPT Script bridge (reading aid, typing, keyboard) | session-and-exchange.md §7 |
| F-COACH Hints | session-and-exchange.md §3.5 |
| F-TCH Teacher console | teacher-console.md |
| F-RES Research console and study mode | experiment-protocol.md |
| F-OKF Record export | data-model.md §8 |
| F-SPEECH Speech adapters | architecture.md §7 |
| F-MEM Memory Assistant (F-MEM-1..8) | memory-assistant.md |
| F-RAJU Classmate output contract | classmate-output-contract.md |
## 9. Keyboard independence (R-INPUT, 31 Oct 2026)

No learner needs a physical Hindi or Telugu keyboard. Three ways to answer:
1. multiple choice for beginner recognition and guided practice;
2. an on-screen Telugu keyboard, akshara/letter tiles and word building;
3. independent typed or spoken answers for production and cue-free recall.

Switching is easy, controls are in Hindi, and every answer records how it was given and what help was on screen. Details: session-and-exchange.md §11.
