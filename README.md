# Setu — a Hindi-first Telugu tutor

A Hindi speaker learns Telugu by building up a personal ladder (letters → words → phrases → sentences → scenes) and by correcting राजू, an AI classmate whose knowledge is held in the database and kept one step behind the learner. Models write; rules decide.

**Status:** redesign in progress (Phase 1). The plan, specs and research protocols are in [`docs/`](docs/PHASE0_SUMMARY.md). The pre-redesign Streamlit app is kept runnable in [`legacy/`](legacy/README.md) until its features are migrated.

## Develop

    python3.11 -m venv .venv
    .venv/bin/pip install -e ".[dev]"
    .venv/bin/pytest -q
    .venv/bin/ruff check .
    .venv/bin/uvicorn setu.web.app:app --reload     # http://localhost:8000/healthz

Full stack (app + Postgres 16):

    docker compose up --build

## Legacy app

    cd legacy
    python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt
    .venv/bin/python -m pytest -q
    .venv/bin/streamlit run app.py
