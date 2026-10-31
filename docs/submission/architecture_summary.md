# Architecture summary

FastAPI + PostgreSQL (SQLAlchemy/Alembic, 14 migrations) + server-rendered Hindi pages (Jinja, no JavaScript needed).

```
learner text ──► normaliser ──► checker (correct | partial | wrong | unsure; no model) ──► OutcomeWriter ──► state
                                                     ▲                                        (only writer; DB role)
model (self-hosted, optional) ──► proposal ──► leak filter / approved-line check ──► shown, or bank fallback
```

| Layer | Modules | Guarantee |
|---|---|---|
| Domain (pure) | `setu/domain/` normaliser, tokenizer, checker, leak filter, leveler, planner, scheduler (FSRS + tracker), exchange ladder, placement, rule-review decisions | deterministic, seeded, versioned |
| Agents | `setu/agents/llm.py` (OpenAI-compatible client, local endpoints only), `classmate.py` (Raju), `coach.py`, `friend.py`, `tools.py` | produce text only; cannot import the writer (test) |
| Store | `outcome_writer.py` (verdicts, signed teacher resolutions, forget and placement decisions only), `content_review.py`, `rule_promotion.py`, grants | five Postgres roles; only `setu_writer` writes learning state; ledger hash-chained, append-only |
| Web | learner routes (letters → scenes), teacher console (review, unsure queue, rules) | Hindi-only catalog + CI lint (no Latin in learner text) |
| Research | Stage-A suite (663 cases, frozen held-out), scorecard, simulator, generation baselines, κ | thresholds frozen in `research/thresholds.yaml` |

**Agent boundaries (all tested):**
- **Raju** (`classmate.propose`): ≤ 3 drafts, each checked by `leakfilter.check_sentence` (exactly the planned
  error, no answer leak, no unseen words, no unknown-rule forms, student register). Failing all → bank sentence.
  Raju learns a rule only through the OutcomeWriter after a cue-free, checked correct fix; forgets only by the
  scheduler's decision at session start.
- **Coach** (`coach.hint`): one Hindi hint per exchange after a first miss; shown only if it passes
  `check_hint_has_no_answer` and is Hindi; else the approved/generic hint. Second miss → the approved answer to copy
  (not evidence). Unsure → teacher queue.
- **Native friend** (`friend.ModelPicker` + `choose_line`): the model may only pick a numbered approved line; any
  other output is rejected and the approved line shown. Scene replies are accepted only in approved forms/variants;
  anything else → fixed Hindi fallback + teacher queue.
- Every model call is logged in `model_call` (agent, model, prompt version, request hash, reply, latency, why
  rejected). Token usage is returned by the client; it is not yet stored in the database (column missing).
