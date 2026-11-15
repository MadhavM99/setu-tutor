# Final audit: state found, changes made (15 Nov 2026, evening)

Record of the session that continued the final audit. Raw result files in `reports/` were not edited; every changed
file is listed below.

## 1. State found

| Item | Found |
|---|---|
| Branch | The audit branch `research/final-audit` was not on GitHub; its work was pushed as `500c991 final` on `redesign/phase0-spec`. Continued on a local branch of that commit. |
| Generation ablation | Finished: 522/522 rows (29 cases × 6 conditions × 3 repeats), no duplicates, 1 provider error in 900 calls, 250,401 tokens. Nothing to resume. |
| Simulator sensitivity | Finished (`reports/simulation_sensitivity.json`), including the app-faithful copy-step option. |
| Figures | Six paper figures and two poster figures present. |
| Paper builder | `scripts/build_final_paper_v2.py` present, never run on this machine; runs. |
| Poster builder | `scripts/build_poster.py` present, never run; runs. Needs `python-pptx`, which no install extra listed. |
| README, walkthrough | Present. The walkthrough links `01_research_audit.md`, which was never pushed. |
| Tests | 1,300 passed, 0 failed, 0 skipped, before any change. |

## 2. The generation metric

- **Prompt:** every Raju prompt contains the item's wrong sentence ("राजू ने पिछली बार ऐसा लिखा था: …",
  `classmate._prompt`).
- **Metric:** `valid` = a model sentence passed `leakfilter.check_sentence`. On a planted turn this requires the
  sentence to equal `wrong_form` or fully match a `wrong_pattern`; 43 of 49 items have no pattern.
- **So:** valid mostly measures reproducing a sentence already in the prompt. It supports "the filtered loop produces
  a usable sentence", not "the model generates new planted errors".
- **Independent measure used:** the ablation's no-example conditions (the sentence is removed from the prompt; scored
  against the same bank sentence). One draft: 0.66 pooled. Reported beside the original measure, never merged with it.
  A lower bound, because a correct paraphrase counts as a failure.
- **Paraphrases:** 19 distinct rejected drafts that keep a wrong-only word are exported to
  `reports/generation_paraphrase_candidates.csv` (`generation_ablation --report-only`) for native review. An approved
  draft would be added to the item's `wrong_patterns`, which the filter already honours.

## 3. Live-model problems

| Problem | Cause | Decision |
|---|---|---|
| Retries returned the same draft | `method="tool"` resends the task and reason codes but not the rejected draft (2 of 3 retried cases repeated one draft) | **Fixed.** `tool_history` moved verbatim from the ablation into `classmate.py`; the app uses it. `tool` kept for reproducibility. |
| Plausible paraphrases rejected | The filter can verify only approved forms; some paraphrases contain two errors (`అతను ఆమె డాక్టరు`) | **Not changed.** Loosening it would let unverified Telugu reach learners. Export for native review instead. |

Regression tests: `tests/unit/test_agents.py` (memory in the retry, old method unchanged, four unsafe drafts fall back,
a failed call adds no empty turn), `tests/db/test_agents_app.py` (the app's second request carries the first draft),
`tests/unit/test_generation_ablation.py` (export never accepts). The ablation report rebuilds byte-identical after the move.

Live smoke check (`gemini-3.5-flash`, `tool_history`, 6 of the hardest cases, one run; not a reported result): no
retry repeated a draft; 4 passed, 2 fell back to the bank; 0 provider errors.

## 4. Other fixes

- `rag_eval --retrieval-only` overwrote the model results in `reports/rag_eval.json`. It now writes
  `rag_eval_retrieval.*` unless `--tag` is given. (Found while checking the README; the overwritten file was
  restored from git.)
- `pyproject.toml`: `python-pptx` added to the `figures` extra.
- Figures 2, 3 and the poster generation chart regenerated: labels said the app used the no-memory loop.
- Paper v2 and poster: describe the switch, the independent measure and the candidates file; test count; reference
  for the BHASHA 2025 IndicGEC findings (cited in the text but missing from the list); fuller author list for Yuan et
  al. 2026; Table 4 labels. Lint (`ruff check .`) passes again.
- README: Postgres without Docker, test time, paper and poster commands, `--report-only`, the new app loop.

## 5. References checked

All 21 references exist with the stated authors, year and venue. Checked online this session: Yuan et al. 2026
(arXiv:2601.05473), Alemdag et al. 2025 (Rev. Educ. Res., doi:10.3102/00346543251390901; 42 papers, g = 0.136),
Thurston et al. 2021 (Educ. Sci. 11(3) 97), Bhattacharyya et al. 2025 (BHASHA, 127–134). The others are standard,
well-known papers whose details match.

## 6. Final verification

- Tests: **1,309 passed, 0 failed, 0 skipped** (240 database tests, 1,069 unit and frozen-case tests), against
  PostgreSQL 16.2, no model configured, 1 min 51 s.
- App: demo database seeded; app started; `/healthz` ok; learner pages (`/`, `/learn/letters`, `/learn/rules`,
  `/learn/match`, `/learn/scenes`, `/ladder`, `/review`) and teacher pages (`/teacher`, `/teacher/queue`) return 200.
- Model-free reproduction: held-out scorecard reproduces every number; ablation report reproduces byte-identical.
