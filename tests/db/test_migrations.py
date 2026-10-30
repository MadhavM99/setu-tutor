"""Migrations: the models and the migrated schema agree, and the migration can be undone and redone."""
from sqlalchemy import create_engine, text


def test_models_match_migrated_schema(engine):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from setu.store.models import Base

    with engine.connect() as c:
        diff = compare_metadata(MigrationContext.configure(c), Base.metadata)
    assert diff == []


def test_downgrade_and_upgrade_round_trip(db_url, engine):
    from setu.store.migrate import downgrade, upgrade

    engine.dispose()
    downgrade(db_url, "base")
    eng = create_engine(db_url)
    with eng.connect() as c:
        left = c.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public' "
                              "AND table_name <> 'alembic_version'")).scalar_one()
    eng.dispose()
    assert left == 0
    upgrade(db_url)


def test_roles_exist_and_cannot_log_in(engine):
    with engine.connect() as c:
        rows = dict(c.execute(text("SELECT rolname, rolcanlogin FROM pg_roles WHERE rolname IN "
                                   "('setu_read', 'setu_app', 'setu_writer', 'setu_content')")).all())
    assert set(rows) == {"setu_read", "setu_app", "setu_writer", "setu_content"}
    assert not any(rows.values())  # group roles only; deployments grant membership to login users
