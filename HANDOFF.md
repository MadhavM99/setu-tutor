# Handoff

## Madhav: coach RAG (tasks 9, 16) and fine-tuning Raju (tasks 10, 17)

Branch `madhav/rag-ft`, made from `kushal-dev`. Research code only: there are no UI or product changes, and the
shipped `coach.hint()` is unchanged. `tests/eval_sets/` and `tests/stage_a/heldout-manifest.json` were not touched.

### Done

| Task | What | Result file(s) |
|---|---|---|
| 9 | Retrieval over the 25 rule documents (`setu/agents/retrieval.py`); `coach.hint_with_mode` (blind / RAG / oracle, abstention, citation check) | tests: `tests/unit/test_coach_rag.py` |
| 16 | Retrieval-only evaluation: hit@1, hit@3, oracle, threshold sweep | `reports/rag_eval_retrieval.{json,md}` |
| 16 | Hint evaluation with gemini-3.5-flash, all 6 conditions (a, b, c, a′, d, e), 29 planted cases plus 40 negatives. 14 Nov: 325 calls, 325 replies, 0 errors, 82,340 tokens. Post-hoc: `b_fixed_posthoc` on the 29 planted cases, 29 calls, 12,461 tokens. Total 354 calls, 94,801 tokens | `reports/rag_eval.{json,md}`, `reports/rag_eval_rows.jsonl` |
| 17 | Prompted gemini-3.5-flash on the 29 frozen cases, paired with untuned Gemma. 29 calls, 0 errors, 4,041 tokens | `reports/ft_eval.{json,md}`, `reports/ft_eval_rows_gemini_prompted.jsonl` |
| 10.1 | Base model choice: Gemma-3-1B-it | `reports/ft_model_check.json`, `reports/ft_copy_check.json`, `docs/submission/drafts/ft_model_choice.md` |
| 10.2 | Training pairs, research validator, go/no-go: **no-go** | `reports/ft_data.json`, `data/ft/*.jsonl` |
| 10.3 | Seeded train/val split, checked for overlap with the frozen cases | `reports/ft_split.json`, `data/ft/train.jsonl`, `data/ft/val.jsonl` |
| 10.5 | No-go write-up | `docs/submission/ft_justification.md` |
| 17 | Pre-registration (13 Nov, 22:01 IST) | `docs/submission/drafts/ft_model_choice.md`, section 4 |
| 17 | Untuned Gemma-3-1B-it on the 29 frozen cases | `reports/ft_eval.{json,md}`, `reports/ft_eval_rows_gemma3_1b_base.jsonl` |
| Report and slides | Results paragraphs; slide content with speaker notes | `docs/submission/drafts/madhav_results.md`, `docs/submission/drafts/madhav_slides.md` |

Step 10.4, the notebook, was not built, because the go/no-go came out no-go.

### How to rerun

All commands run from the repo root. Keys come only from `.env`, which is gitignored:

```
SETU_LLM_URL=https://generativelanguage.googleapis.com/v1beta/openai/
SETU_LLM_MODEL=gemini-3.5-flash
SETU_LLM_API_KEY=...
SETU_LLM_ALLOW_HOSTED=1
SETU_LLM_REASONING=none
SETU_LLM_RETRIES=3
SETU_LLM_TIMEOUT=60
SETU_EVAL_INTERVAL=2      # 15 on the free tier
```

| What | Command | Needs |
|---|---|---|
| Unit tests | `.venv/bin/python -m pytest tests/unit -q` | nothing |
| Retrieval metrics | `.venv/bin/python -m setu.research.rag_eval --retrieval-only --tag retrieval` | nothing |
| Hint evaluation | `.venv/bin/python -m setu.research.rag_eval` (the 6 planned conditions); `--conditions b_fixed_posthoc` (the post-hoc fix) | key; 325 + 29 calls |
| Training pairs | `.venv/bin/python -m setu.research.ft_data` (rebuild) / `--gemini --calls 8` (generate) | key for `--gemini` |
| Split | `.venv/bin/python -m setu.research.ft_split` | nothing |
| Base model, local | `PYTHONPATH=. <venv with torch, transformers and project deps>/bin/python -m setu.research.ft_eval --local unsloth/gemma-3-1b-it --label gemma3_1b_base --device cpu` | about 10 minutes on CPU |
| Gemini, task 17 | `.venv/bin/python -m setu.research.ft_eval --gemini` | key; 29 calls |
| Task 17 report only | `.venv/bin/python -m setu.research.ft_eval` | nothing |
| Model checks | `PYTHONPATH=. <ml venv>/bin/python scripts/ft_tokenizer_check.py --device cpu`, `scripts/ft_copy_check.py --device cpu` | torch, transformers |

**Resuming.** Every model run can resume. Rows are appended to disk as each case finishes, a rerun only retries the
cases with no model reply, and every API error is logged and never counted as a result. `rag_eval` runs the
conditions in priority order (a, b, c, a′, d, e) and rewrites its report after each one. Any condition with fewer
answered cases than planned is marked **reduced-n**.

### Done on 14 Nov

- Both online runs are complete, on a paid-tier key, with `SETU_EVAL_INTERVAL=2`.
- The hint evaluation started with 18 free-tier rows (a and b, 9 cases each, run with `--limit 9`). The full run
  resumed from those rows and finished every condition, so the report status is `run`, not reduced-n.
- The Task 17 Gemini half ran all 29 cases.
- `madhav_results.md` and `madhav_slides.md` have the final numbers, including the compute table.

### Still open

1. **No native check.** Nobody native has read the 23 accepted training pairs or the model outputs, and 9 of the 15
   HI→TE rule explanations are still unreviewed drafts.
2. **The post-hoc coach fix is research-only.** 8 of the 20 RAG hints shown on the planted cases said "read rule N".
   - The fix is `coach.SYSTEM_RAG_FIXED` plus `coach.numbered_source_check`, enabled with
     `hint_with_mode(..., fixed=True)`.
   - Rerun as `b_fixed_posthoc` on the 29 planted cases: "shown and usable" 25/29, against 12/29 for (b). Blind
     was 10/29, and (b) vs blind gives p = 0.79.
   - "Shown hint cites planted": 21/29, against 17/29 for (b). "Model cites planted" is 24/29 in both.
   - The measure names are defined in `reports/rag_eval.md`, under "Measures".
   - It was designed after seeing these cases, so it is optimistic. Confirming it needs new cases.
   - The original (b) stays the primary result. The shipped `coach.hint()` is unchanged.
3. **Rotate the API key.** It was pasted into a chat.
