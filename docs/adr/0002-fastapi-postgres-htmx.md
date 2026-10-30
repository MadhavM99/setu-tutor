# ADR-0002: FastAPI + PostgreSQL + Jinja/HTMX

**Status:** accepted (user decision D2)

## Context

The paper requires:
- a Postgres source of truth;
- a teacher console;
- multi-learner studies.

The prompt also requires a Hindi-only, accessible UI. Streamlit gives limited control over visible text, routing, auth and concurrency.

## Decision

- **Backend:** FastAPI, with SQLAlchemy 2 and Alembic for the database.
- **Pages:** server-rendered Jinja templates, with HTMX for interaction.
- **No JS build step.** A small vanilla JS file provides the on-screen Telugu keyboard.

## Consequences

- The Python engine is kept.
- E2E tests run in Playwright.
- The Streamlit app moves to `legacy/` until feature parity.
