# SETU — a Hindi-first Telugu tutor in which the learner corrects an AI classmate

A Hindi speaker learns Telugu by climbing a ladder (letters → syllables → words → phrases → sentences → scenes) and, at
the sentence stage, by correcting **Raju (राजू)**, an AI classmate who makes the mistakes a Hindi speaker makes in Telugu.
Rule of the design: **models write, rules decide.** Raju's knowledge is stored as data, every model sentence passes a
deterministic filter, and only a rule-based checker (no model) changes what the system believes the learner knows.

Course project, *Language Models and Agents*, IIIT Hyderabad, team **Token Guessers** (Madhav Malhotra, Kushal Karan,
Faviana Noronha, Shaik Areesh). Final report: [`docs/submission/report/SETU_final_paper.pdf`](docs/submission/report/SETU_final_paper.pdf)
(mid-submission: [`SETU_mid_submission_report.pdf`](docs/submission/report/SETU_mid_submission_report.pdf)).

**Status.** Built and tested; **no real learner has used it** and no result here is evidence about learners. Every learner
result is a simulation, the Telugu content has had one non-independent review, and the interface additions (pictures,
match game, voice, English glosses) are built but not evaluated. Negative and failed results are reported in the paper.

## 1. Run the app

Requirements: Python 3.11+, Docker (for PostgreSQL 16).

    python3.11 -m venv .venv
    .venv/bin/pip install -e ".[dev]"
    scripts/run_demo.sh            # starts Postgres, seeds an isolated demo database, serves http://127.0.0.1:8000

The script prints a learner login and a teacher login (passphrase `डेमो पासवर्ड बारह`, development only). Without a model
configured, Raju, the coach and the friend use their approved fallbacks, and each Raju turn says which. See
[`docs/submission/demo_guide.md`](docs/submission/demo_guide.md) for a walkthrough and for the optional model setup.

Full stack in containers: `docker compose up --build`.

## 2. Check it (no model, no key needed)

    .venv/bin/pytest -q                    # 1,287 tests against PostgreSQL 16 (CI runs them with model keys removed)
    .venv/bin/ruff check .
    .venv/bin/python -m scripts.lint_hindi # fails if any English letter appears in learner-facing Hindi text

## 3. Reproduce the results

All numbers in the paper come from the JSON files in [`reports/`](reports/). The tables regenerate from those files:

    .venv/bin/python -m setu.research.results_tables          # rewrites reports/results_tables.md (identical to the committed copy)
    .venv/bin/python -m setu.research.evaluate_agreement      # checker vs human labels (Batch A, κ)
    .venv/bin/python -m setu.research.scorecard --split heldout   # held-out checker/filter scorecard
    .venv/bin/python -m setu.research.rag_eval --retrieval-only --tag check   # retrieval numbers, no model (writes reports/rag_eval_check.*)
    .venv/bin/python -c "from setu.research.simulator import main; main('/tmp/sim1')"      # simulator v0.1 (assumption-driven)
    .venv/bin/python -c "from setu.research.simulator_v2 import main; main('/tmp/sim2')"   # simulator v0.2 (FSRS memory; A ranks last)

(Run directly with `python -m`, the two simulators overwrite the committed `reports/simulation*/results.json`; pass an
output folder as above to compare instead.)

Runs that call a model need a key in `.env` (never commit it) and are not deterministic. All used `gemini-3.5-flash` with
reasoning off:

    SETU_LLM_URL=https://generativelanguage.googleapis.com/v1beta/openai/
    SETU_LLM_MODEL=gemini-3.5-flash
    SETU_LLM_API_KEY=...
    SETU_LLM_ALLOW_HOSTED=1  SETU_LLM_REASONING=none  SETU_LLM_RETRIES=3

| Task | Command (`set -a; source .env; set +a` first) | Output |
|---|---|---|
| 6 generation baselines | `python -m setu.research.generation_baselines` | `reports/generation_baselines.json` |
| 13 judge vs checker vs native labels | `python -m setu.research.judge_eval` | `reports/judge_eval.json` |
| 14 tool calling | `python -m setu.research.tool_eval` | `reports/tool_eval.json` |
| 15 stepwise reasoning | `python -m setu.research.reasoning_eval` | `reports/reasoning_eval.json` |
| 16 coach RAG (all conditions) | `python -m setu.research.rag_eval` | `reports/rag_eval.{json,md}` |
| 10 / 17 fine-tuning data and baselines | `python -m setu.research.ft_data`, `ft_eval --gemini --label gemini_prompted` | `reports/ft_data.json`, `ft_eval.*` |
| 18 multi-agent vs single agent | `python -m setu.research.agentic_eval` | `reports/agentic_eval.json` |

Caution: `rag_eval` without `--tag` overwrites `reports/rag_eval.*`. Run model-backed commands on a copy of the repository
if you want to keep the committed results. The Gemma-3-1B baseline needs a separate environment with `unsloth`
(`ft_eval --local unsloth/gemma-3-1b-it --label gemma3_1b_base`, about 145 s on CPU). Fine-tuning itself was not run: the
go/no-go in `reports/ft_data.json` is *no-go*.

Rebuild the reports:

    .venv/bin/python -m scripts.build_final_paper     # docs/submission/report/SETU_final_paper.{html,pdf}  (needs Playwright's Chromium)
    .venv/bin/python -m scripts.build_final_report    # longer companion report
    .venv/bin/python -m scripts.build_report          # mid-submission report (macOS Chrome path)

## 4. Interface additions (this branch)

Learning-path map, word pictures (inline SVG, Hindi alt text), a match-the-pairs game, an early "meet Raju" card,
English text under Telugu words, and optional browser voice. None of it grades anything.

    SETU_TTS_SYNTHETIC=1    # "Listen" buttons (browser voice, marked data-voice="synthetic"); off by default
    SETU_SPEECH_INPUT=1     # "Say it" button; in Chrome the audio goes to Google; off by default
    SETU_ENGLISH_GLOSS=0    # hide the English words (on by default)

Do not turn the speech flags on for real learners before the speech gate (M-25) and speaker review. Notes on how the
additions follow the specification: [`docs/submission/drafts/faviana_ui_notes.md`](docs/submission/drafts/faviana_ui_notes.md).

## 5. Layout

| Path | What |
|---|---|
| `setu/domain/` | normaliser, checker, leak filter, planner, scheduler (FSRS), mastery, matching |
| `setu/agents/` | Raju, coach, friend, read-only tools, model client |
| `setu/store/`, `migrations/` | PostgreSQL models, roles, triggers, append-only hash-chained ledger |
| `setu/web/`, `locale/hi.yaml` | server-rendered Hindi interface and catalog |
| `setu/research/` | every evaluation and simulator above |
| `content/`, `research/` | rule bank, words, chunks, scenes; label sheets and thresholds |
| `reports/` | saved results (the source of every number in the paper) |
| `docs/` | specification (`PHASE0_SUMMARY.md`), submission reports and drafts |
| `legacy/` | the pre-redesign Streamlit prototype |

## 6. Honest limits

No learner data; simulations disagree; Telugu content not independently reviewed; checker κ 0.15 against native labels
(target 0.6) and unsure rate 0.18 (ceiling 0.15); evaluation sets of 29–58 cases. Read the Limitations section of the paper
before citing any number.

## Legacy app

    cd legacy
    python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt
    .venv/bin/python -m pytest -q
    .venv/bin/streamlit run app.py
