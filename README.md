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

## Speech flags (off by default)

Listen and say-it buttons are behind the two flags of `docs/specs/architecture.md` §7. With both off the pages carry no
speech control and send no speech script. Turn them on with environment variables, per process:

    SETU_TTS_SYNTHETIC=1   # "Listen" buttons and the slow-voice switch (browser voice, marked data-voice="synthetic")
    SETU_SPEECH_INPUT=1    # "Say it" button (browser speech recognition; in Chrome the audio goes to Google)

Speech never grades anything. Do not turn these on for real learners before the speech gate (M-25) and speaker review.

## Legacy app

    cd legacy
    python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt
    .venv/bin/python -m pytest -q
    .venv/bin/streamlit run app.py
