"""Database access for the web layer: every transaction runs as `setu_app` (operational records only)."""
import os
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine


class AppDatabase:
    def __init__(self, engine: Engine | None = None):
        self._engine = engine

    @property
    def engine(self) -> Engine:
        if self._engine is None:  # created lazily so the app (and /healthz) starts without a database
            self._engine = create_engine(os.environ["SETU_APP_DATABASE_URL"])
        return self._engine

    @contextmanager
    def tx(self) -> Connection:
        with self.engine.execution_options(isolation_level="READ COMMITTED").begin() as c:
            c.execute(text("SET LOCAL ROLE setu_app"))
            yield c
