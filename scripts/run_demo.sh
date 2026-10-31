#!/usr/bin/env bash
# Start the SETU demo (development only): Postgres in Docker, the isolated demo database, the app on :8000.
# Optional self-hosted model: start LM Studio's server (`lms server start; lms load qwen/qwen3.5-9b`) and export
#   SETU_LLM_URL=http://localhost:1234/v1 SETU_LLM_MODEL=qwen/qwen3.5-9b
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose up -d db
[ "${SKIP_SEED:-0}" = "1" ] || .venv/bin/python -m scripts.demo_seed
export SETU_APP_DATABASE_URL="postgresql+psycopg://setu_migrate:setu-dev-only@localhost:5433/setu_demo"
export SETU_DEMO=1
export SETU_COOKIE_SECURE=0  # plain http on 127.0.0.1 only
export SETU_CLASSMATE_START_MIN_RULES="${SETU_CLASSMATE_START_MIN_RULES:-1}"  # demo: Raju appears after one ready rule (default 3)
export SETU_RESOLUTION_KEY="${SETU_RESOLUTION_KEY:-demo-only-resolution-key-$(hostname)-0123456789}"
exec .venv/bin/uvicorn setu.web.app:app --host 127.0.0.1 --port "${PORT:-8000}"
