# Dataset register (mid-submission)

Status as recorded in `content/data_sources.yaml` and checked during the sprint. **No dataset size is reported unless
it was counted in this repository; licences marked "to check" have not been confirmed.**

| Dataset | Actual use in this project now | Size / statistics (counted here) | Preprocessing | Licence status |
|---|---|---|---|---|
| IndicCorp v2 (DS-05) | **Not used yet.** Planned: Telugu word frequencies for the L2 word order | none: only the dataset card is in the local Hugging Face cache (8 KB), the corpus is not downloaded | — | to check |
| IndicGEC Telugu (DS-07) | **Not used yet.** Planned: checker robustness (no false accepts/rejects) | not downloaded | — | to check |
| LTRC Hindi–Telugu parallel corpus (DS-08) | **Not used yet.** Planned: how contrasts appear in translation | not obtained | — | commercial use to be confirmed |
| Aksharantar / IndicXlit (DS-09) | Adapter interface only (romanised input is marked *unsure* without it) | model not wired in | — | to check |
| Cognates / false friends, Kanojia et al. 2020 (DS-06) | **Not used yet.** The 4 false friends and cognate flags in `lexicon.yaml` are team drafts | not obtained | — | to check |
| Tenepalukulu / Vennela textbooks (DS-04) | Not used; planned only for topic order; no sentences copied | — | — | government publication; no copying without permission |
| Team rule bank (DS-20) | Rules and items for the classmate and checker | 25 rules, 49 items (15 HI→TE + 10 TE→HI); all draft, all with open validation issues | converted from two repositories with provenance hashes (`content/CONVERSION.json`) | team-owned; Claude-drafted, unreviewed |
| Script and vocabulary content (DS-20) | L0–L3 practice | 48 letters, 489 aksharas, 28 words, 32 chunks, 5 scenes, 4 scene scripts with 12 lines | generated (`setu.content letters/aksharas`) or drafted; validated by `setu.content validate` | team-owned; unreviewed |
| Teacher-reviewed content (DS-01) | Review machinery built (slice 4.1/4.2) | **0 items reviewed by native speakers** | — | reviewer agreement form to check |
| Stage-A test cases (DS-19) | Module tests and scorecard | 663 generated cases, 30% held-out manifest frozen | generated from the content | team-owned |
| Teacher label sheet | Checker–teacher agreement (M-16) | 145 rows, **unlabelled** | — | team-owned |
| Synthetic learner profiles | Simulator | 20 profiles × 5 seeds per condition (Beta/uniform draws, `setu/research/simulator.py`) | none | generated |
| Demo database `setu_demo` | Browser demonstration only | all content approved by two accounts named `demo-reviewer-*` (not native review) + 3 synthetic demo rules | `scripts/demo_seed.py` | not a dataset; never used for results |
