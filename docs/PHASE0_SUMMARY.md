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
