"""Run Alembic migrations programmatically (used by tests and deployment scripts)."""
import os
from pathlib import Path

from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[2]


def config(url: str | None = None) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    url = url or os.environ["SETU_DATABASE_URL"]
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def upgrade(url: str | None = None, revision: str = "head") -> None:
    command.upgrade(config(url), revision)


def downgrade(url: str | None = None, revision: str = "base") -> None:
    command.downgrade(config(url), revision)
