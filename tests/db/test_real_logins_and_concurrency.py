"""Grants hold for real login users (not only SET ROLE from a superuser), and the ledger chain stays intact
under concurrent appends from separate connections (E-01, E-02)."""
import threading
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from .conftest import ADMIN_URL


@pytest.fixture
def login_as(db_url):
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    created = []

    def make(group):
        name = f"setu_t_{group.split('_')[1]}_{uuid.uuid4().hex[:6]}"
        password = uuid.uuid4().hex
        with admin.connect() as c:
            c.execute(text(f"CREATE ROLE {name} LOGIN PASSWORD '{password}' IN ROLE {group}"))
        created.append(name)
        base = db_url.split("://", 1)[1].split("@", 1)[1]
        return create_engine(f"postgresql+psycopg://{name}:{password}@{base}")

    yield make
    with admin.connect() as c:
        for name in created:
            c.execute(text(f"DROP OWNED BY {name}"))
            c.execute(text(f"DROP ROLE {name}"))
    admin.dispose()


def _denied(engine, sql):
    with engine.connect() as c:
        with pytest.raises(DBAPIError) as e:
            c.execute(text(sql))
        assert "permission denied" in str(e.value.orig)


def test_read_login_user_cannot_write_or_see_secrets(engine, login_as):
    reader = login_as("setu_read")
    _denied(reader, "INSERT INTO event_ledger (actor, event_type, payload) VALUES ('checker', 'x', '{}')")
    _denied(reader, "UPDATE classmate_rule_state SET state = 'taught'")
    _denied(reader, "SELECT passphrase_hash FROM learner")
    _denied(reader, "CREATE TABLE sneaky (x int)")
    _denied(reader, "SELECT title_hi FROM rule_version")  # drafts are invisible to the read role (0003)
    with reader.connect() as c:
        c.execute(text("SELECT title_hi FROM learner_rule_version"))
    reader.dispose()


def test_writer_login_user_appends_but_cannot_rewrite_history(engine, login_as):
    writer = login_as("setu_writer")
    with writer.begin() as c:
        c.execute(text("INSERT INTO event_ledger (actor, event_type, payload) VALUES ('checker', 'probe', '{}')"))
    _denied(writer, "UPDATE event_ledger SET payload = '{}'")
    _denied(writer, "DELETE FROM event_ledger")
    _denied(writer, "INSERT INTO rule (id, direction, contrast_area) VALUES ('HI-TE-099', 'HI->TE', 'x')")
    writer.dispose()


def test_concurrent_appends_keep_a_single_valid_chain(engine):
    errors = []

    def worker(k):
        try:
            with engine.begin() as c:
                for i in range(10):
                    c.execute(text("INSERT INTO event_ledger (actor, event_type, payload) VALUES "
                                   "('scheduler', 'load', CAST(:p AS jsonb))"), {"p": f'{{"w": {k}, "i": {i}}}'})
        except Exception as e:  # noqa: BLE001 - surface any failure in the main thread
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(k,)) for k in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM event_ledger WHERE event_type = 'load'")).scalar_one() == 60
        assert c.execute(text("SELECT setu_verify_ledger()")).scalar_one() is None
        dupes = c.execute(text("SELECT count(*) - count(DISTINCT prev_hash) FROM event_ledger")).scalar_one()
        assert dupes == 0  # no fork: every event has a unique predecessor


def test_appends_at_repeatable_read_are_refused(engine):
    with engine.connect() as c:
        c.execution_options(isolation_level="REPEATABLE READ")
        with pytest.raises(DBAPIError) as e, c.begin():
            c.execute(text("INSERT INTO event_ledger (actor, event_type, payload) VALUES ('checker', 'x', '{}')"))
        assert "READ COMMITTED" in str(e.value.orig)
