from __future__ import annotations

import os
import time

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    timeout_seconds = int(os.getenv("WAIT_FOR_DB_TIMEOUT", "60"))
    deadline = time.time() + timeout_seconds
    engine = create_engine(settings.database_url, pool_pre_ping=True)

    while True:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            print("Database is ready")
            return
        except OperationalError as exc:
            if time.time() >= deadline:
                raise SystemExit(f"Database did not become ready within {timeout_seconds}s: {exc}") from exc
            print("Waiting for database...")
            time.sleep(2)


if __name__ == "__main__":
    main()
