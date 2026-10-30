# Phase 0 summary: Hindi-first Setu Telugu tutor

**Status:** planning package, partially complete, for review. **No application code has been changed.** Branch `redesign/phase0-spec`; the baseline snapshot is commit `7b84c7e`.

## Decisions taken with the user

1. **Target repo:** `setu-tutor` is the product being rebuilt. The team research repo (LMA) is a source to reuse code and data from.
2. **Stack:** FastAPI + Postgres + Jinja/HTMX. Streamlit is retired.
3. **Models:** self-hosted only, through an OpenAI-compatible client or a mock. No Gemini at runtime.
4. **Capacity:** one developer plus Claude, working in sequenced vertical slices.

## Verdict on the current product

Details are in [audit/current-product-audit.md](audit/current-product-audit.md).

**The current app does not reliably teach.** The main failures:
- Hints show the answer, including in the scored "no hint" check. The check can never fail. Mastery comes from a single answer.
- The checker can be fooled. Verified probes: a single word or fragment counts as a full correct answer, and so does a sentence that still contains the planted error.
- Unreviewed AI tricks and pictures are shown to learners. The app uses balloons and a celebrating child persona, and English appears throughout the UI.
- Learners' questions are sent to a commercial API. There is no auth.

The LMA repo has the strongest pieces to reuse: the tool contract, the agent loop, the single-writer ledger, study conditions A/B/C and the simulator. Its study mode has validity defects (test items that are not unseen, unequal help across conditions, a fake Latin square), and the TE→HI direction is broken end to end.

## Proposal

| Area | Proposal | Spec |
|---|---|---|
| Ladder | Personal L0–L5 skill graph (script → akshara → words → chunks → contrasts → scenes), tracked per modality; multi-item, multi-day, cue-free and production unlock rule; placement diagnostic | [specs/learning-ladder.md](specs/learning-ladder.md) |
| Session | Each session: reviews, ≤ 5 new items, correction exchanges with राजू (only after ≥ 3 verified rules), ~20% no-error turns (production substituted when nothing is plantable), ≥ 2 own sentences | [specs/session-and-exchange.md](specs/session-and-exchange.md) |
| Architecture | Models write and rules decide. OutcomeWriter is the only writer, enforced by Postgres grants. Every model output passes a validator before display, and the system fails closed | [specs/architecture.md](specs/architecture.md), [specs/data-model.md](specs/data-model.md), [specs/api-and-tool-contracts.md](specs/api-and-tool-contracts.md) |
| Content | Separate validity and learner-evidence fields; immutable versions; 16 data-quality issues logged; all current content enters as `uncertain` / `draft` | [specs/content-and-error-bank.md](specs/content-and-error-bank.md) |
| UI | Hindi-only catalog with a CI lint that fails on any Latin letter; calm persona | [specs/localisation-hindi-ui.md](specs/localisation-hindi-ui.md) |
| Teacher | Review with two raters plus a third, κ, unsure settlement, variants, per-opportunity analytics, override, exports | [specs/teacher-console.md](specs/teacher-console.md) |
| Research | Stage A (≥ 150 cases, frozen held-out split, 3-variant ablation, red team), A2 (60 seeded simulations), B (5 adults, Latin square, one-week and transfer tests, blind marking, Hedges' g) | [research/experiment-protocol.md](research/experiment-protocol.md), [research/metrics-and-gates.md](research/metrics-and-gates.md) |
| Traceability | About 300 rows: paper, newer copy, prompt, metrics, risks, the 29 future-work items, engineering recommendations | [specs/source-traceability-matrix.md](specs/source-traceability-matrix.md) |

## Biggest risks

- **R-17 (from the newer paper copy's simulation):** teaching राजू can reduce production practice, and condition A lost to C. The design answers this with mandatory own sentences and a controlled no-error share, and the risk is reported, not hidden.
- **R-18:** every piece of Telugu content is an unreviewed draft. Native review is the critical path to any learner exposure.
- **R-20:** a GPU is needed for Gemma 3 12B evaluations.

## Open decisions

Each has a conservative default; see the plan:
- classmate at the script stage;
- no-error turns when nothing is plantable;
- mastery thresholds;
- the Devanagari reading aid;
- persona tone;
- the paper version of record;
- Python 3.11;
- the pilot identity model.

## Package status

**Complete.** Phase 0 also includes:
- [quality/test-plan.md](quality/test-plan.md)
- [implementation/implementation-plan.md](implementation/implementation-plan.md), with slices, dependency graph and a legacy-migration table
- ADRs 0001–0004 in [adr/](adr/)

**Verification run (30 Oct 2026):**
- The matrix has 380 unique IDs with no duplicates. Every per-family minimum is met:
  - all 45 Table 9 metric items, plus the newer copy's metrics and the ladder metrics;
  - all 16 Table 10 risks, plus R-17 to R-21;
  - all 29 future-work items;
  - all 13 contrast families;
  - all 11 Table 7 sources;
  - prompt §0–§18.
- Every cited test-suite ID is defined in the test plan.
- Every feature spec has all mandatory template fields.
- Only `docs/` changed since the baseline.

**Next step:** user approval (gate G0). Implementation starts with Phase 1, slice 1.1, after approval.

## Amendment A1 (30 Oct 2026): Memory Assistant and student-only Raju

The package was approved with this amendment. It is still docs only.

| Change | Where |
|---|---|
| **Memory Assistant** (स्मृति सहायक), a first-class subsystem. It covers:<br>• a technique policy by unit type (letters, sounds, akshara, vocabulary, false friends, grammar, phrases);<br>• an AI-teacher recommendation limited to deterministic candidates;<br>• mnemonics grounded in verified facts only;<br>• text-free illustrations with app-rendered glyphs;<br>• an approved, versioned asset library with a non-generative fallback;<br>• accessibility;<br>• per-aid delayed-recall measurement;<br>• cue fading (3 → 0);<br>• FSRS integration, where aid-visible attempts are capped at Hard and never count toward mastery;<br>• cost controls, failure behaviour and gates. | [specs/memory-assistant.md](specs/memory-assistant.md), ADR-0005 |
| **Image and mnemonic generation is offline only.** Prompts are concept-level, checked by OCR and the grounding validator, then reviewed by a teacher. External image services are allowed only in the offline pipeline environment; the runtime app has none. | ADR-0005 (scopes ADR-0003) |
| **Study M**, separate from the reverse-learning study: M-A normal + retrieval, M-B verbal mnemonics, M-C visual + native audio, M-D adaptive. Williams 4×4 design; outcomes at 1, 7 and 30 days, production, transfer, time to mastery and incorrect associations. | [research/memory-experiment-protocol.md](research/memory-experiment-protocol.md) |
| **Reverse-learning A/B/C get identical memory support** (fixed mode, with a balance check, M-67). | research/experiment-protocol.md §4b |
| **Raju is a weaker student only.** Closed turn types; the model fills only the Telugu sentence slot; every Hindi line comes from fixed catalog templates; there is no free chat; a student-only filter rejects assistant, teacher, formatting, gloss, answer-leak and competence violations. Persona breaks shown to learners must be 0 (M-56, a G2 safety gate). | [specs/classmate-output-contract.md](specs/classmate-output-contract.md), ADR-0006 |
| **Integrated into:** PRD, journeys (J-11), architecture §10, data model, API (A5/A6, `/aid/*`, teacher `/aids`), content pipeline §7, teacher console F9, localisation §6, session §9, methodology rows 14–16, metrics M-56..M-68, gates G-MEM-*, matrix §23–24 plus new R/FW/E rows, test plan §5, implementation plan, data-source register, roadmap. | — |

**Open decision (default chosen).** The amendment bundles native audio into M-C. To keep pronunciation exposure from being confounded with the mnemonic, all four conditions hear the same native pronunciation once per item; M-C adds *association* audio. Say if you want audio exclusive to M-C. The analysis would then treat visual + audio as one package.
