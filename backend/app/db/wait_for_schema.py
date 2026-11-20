"""Keep queue workers idle until the API has applied this build's migrations."""
from __future__ import annotations

import os
from pathlib import Path
import time

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings


def required_heads() -> set[str]:
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[2] / "alembic"))
    return set(ScriptDirectory.from_config(config).get_heads())


def wait_for_schema(engine, expected: set[str], timeout: float = 240, *, clock=time.monotonic, sleep=time.sleep) -> None:
    deadline = clock() + timeout
    while True:
        try:
            with engine.connect() as connection:
                current = set(MigrationContext.configure(connection).get_current_heads())
            if current == expected:
                return
        except SQLAlchemyError:
            # A connection or version table can be unavailable during startup.
            # Do not log connection URLs or assume a schema is ready on error.
            pass
        if clock() >= deadline:
            raise SystemExit("Schema did not reach this build's migration head; worker not started. Check backend migration logs.")
        sleep(2)


def main() -> None:
    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        wait_for_schema(engine, required_heads(), float(os.getenv("WAIT_FOR_SCHEMA_TIMEOUT", "240")))
    finally:
        engine.dispose()
    print("Schema is ready for queue jobs")


if __name__ == "__main__":
    main()
