"""Alembic environment: online migrations only, against SETU_DATABASE_URL or the configured URL."""
import os

from alembic import context
from sqlalchemy import create_engine

from setu.store.models import Base

config = context.config
url = config.get_main_option("sqlalchemy.url") or os.environ["SETU_DATABASE_URL"]


def run() -> None:
    engine = create_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_server_default=False)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run()
