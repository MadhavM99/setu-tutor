# Team contribution: Faviana Noronha (Token Guessers)

Team: Madhav Malhotra, Kushal Karan, Faviana Noronha, Shaik Areesh.

## Faviana's contribution

| Area | What | Where |
|---|---|---|
| Learner interface | learning-path map, word pictures, match-the-pairs game, early Raju card and "what Raju learned" section, English under words, optional voice (off by default), larger touch targets | branch `faviana-noronha`: `setu/web/`, `setu/domain/matching.py`, `locale/hi.yaml` |
| Spec alignment | speech behind flags, picture-aid assistance recorded, accessibility contrast fix, fixed a crash on the progress page, regression tests | `tests/db/test_match.py`, `tests/unit/test_l10n.py`, `tests/unit/test_english_gloss.py` |
| Accessibility check | automated axe-core run on 8 pages at 2 widths, keyboard-only and reduced-motion checks | summarised in the report section A |
| Final report | results summary, six qualitative examples, failure analysis per capability, compute report, goals and problem statement | `docs/submission/drafts/faviana_*.md` |
| Earlier prototype | sentence-difficulty leveler (A1–B2) in her own repo, barely above the majority baseline (exact 0.694 vs 0.633, 49 items); not wired into the app | `FavianaNoronha/lma---reverse-learning-tutor` |

Not claimed: any learning gain from the interface features (not evaluated).

## Others (from the git history; each person should confirm and correct their own row)

| Person | What the history shows |
|---|---|
| Madhav Malhotra | the core system: normaliser, checker, leak filter, scheduler, planner, L0–L5 lessons, Raju, teacher review, simulators, coach RAG and the fine-tuning pipeline (no-go) |
| Kushal Karan (git author `codepley`) | tool-calling, stepwise reasoning, judge validation, single and multi-agent evaluation, results tables, the real-model runs for tasks 6, 13, 14, 15, 18 |
| Shaik Areesh | Batch A human-system agreement evaluation and annotation validation |

Git shows commit authorship only; it does not show who did the writing, labelling or review. Replace this table with each
member's own description before submitting.

## Process notes (for the honesty section)

- Claude (an AI assistant) was used for coding, testing and drafting on Faviana's branch, and its commits carry a
  co-author line. Every number in the drafts was copied from a file in `reports/` and should be checked by the person
  who owns that file.
