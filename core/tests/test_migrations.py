from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command
from nidavelir_core.settings import get_settings


def test_migrations_initialize_empty_database(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "nidavelir.db"
    database_url = f"sqlite+pysqlite:///{database_path}"
    monkeypatch.setenv("NIDAVELIR_DATABASE_URL", database_url)
    get_settings.cache_clear()

    try:
        config = Config("alembic.ini")
        command.upgrade(config, "head")

        engine = create_engine(database_url)
        tables = set(inspect(engine).get_table_names())
        engine.dispose()

        assert {"alembic_version", "tasks", "task_transitions"} <= tables
    finally:
        get_settings.cache_clear()
