"""Real-Postgres fixtures for slice 1.2.

Each test session creates a throwaway database, migrates it to head, and drops it afterwards.
Each test runs inside a transaction that is rolled back, so tests never see each other's rows.

Set SETU_TEST_ADMIN_URL to point at a Postgres superuser connection (default: the compose `db`
service on port 5433). These tests fail, rather than skip, when Postgres is unreachable, unless
SETU_SKIP_DB_TESTS=1 is set explicitly.
"""
import os
import uuid

import pytest
from sqlalchemy import create_engine, text

ADMIN_URL = os.environ.get(
    "SETU_TEST_ADMIN_URL", "postgresql+psycopg://setu_migrate:setu-dev-only@localhost:5433/postgres"
)


def pytest_collection_modifyitems(config, items):
    if os.environ.get("SETU_SKIP_DB_TESTS") == "1":
        skip = pytest.mark.skip(reason="SETU_SKIP_DB_TESTS=1")
        for item in items:
            if "tests/db/" in str(item.fspath):
                item.add_marker(skip)


@pytest.fixture(scope="session")
def db_url():
    name = f"setu_test_{uuid.uuid4().hex[:10]}"
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'CREATE DATABASE "{name}"'))
    url = ADMIN_URL.rsplit("/", 1)[0] + f"/{name}"
    try:
        yield url
    finally:
        with admin.connect() as c:
            c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture(scope="session")
def engine(db_url):
    from setu.store.migrate import upgrade

    upgrade(db_url)
    eng = create_engine(db_url)
    yield eng
    eng.dispose()


@pytest.fixture
def conn(engine):
    with engine.connect() as c:
        trans = c.begin()
        try:
            yield c
        finally:
            trans.rollback()
