"""Scoped PostgreSQL housekeeping. CLI defaults to a read-only dry run.

Normal idle pool sessions are healthy and are never targeted. Only tagged EQM
API connections in this database, owned by this login, can be acted upon.
"""
import argparse
import asyncio
import logging

from sqlalchemy.engine import make_url
from app.core.config import get_settings
from app.db.session import env_int

log = logging.getLogger(__name__)
_task: asyncio.Task | None = None

# Eligibility is rechecked in the action statement, not just the sampling query.
ELIGIBLE = """
 datname = current_database() AND usename = current_user
 AND backend_type = 'client backend' AND application_name = 'eqm-api'
 AND pid <> pg_backend_pid()
 AND ((state IN ('idle in transaction', 'idle in transaction (aborted)')
       AND state_change < clock_timestamp() - make_interval(secs => %(idle)s))
   OR (state = 'active' AND query_start < clock_timestamp() - make_interval(secs => %(active)s)
       AND query ~* '^\\s*SELECT\\s' AND query !~* '(pg_sleep|pg_advisory|FOR[[:space:]]+UPDATE|FOR[[:space:]]+SHARE)'))
"""


def scan(*, apply: bool = False) -> list[dict]:
    url = make_url(get_settings().database_url)
    if url.get_backend_name() != "postgresql":
        return []
    import psycopg
    from psycopg.rows import dict_row
    params = {"idle": env_int("DB_WATCHDOG_IDLE_SECONDS", 300),
              "active": env_int("DB_WATCHDOG_QUERY_SECONDS", 180)}
    # Direct connection still works when SQLAlchemy's application pool is full.
    with psycopg.connect(host=url.host, port=url.port or 5432, dbname=url.database,
                         user=url.username, password=url.password,
                         application_name="eqm-watchdog", connect_timeout=5,
                         options="-c statement_timeout=5000 -c lock_timeout=1000",
                         autocommit=True, row_factory=dict_row) as conn:
        if not conn.execute("SELECT pg_try_advisory_lock(188674, 1) AS acquired").fetchone()["acquired"]:
            return []
        rows = conn.execute("SELECT pid, state FROM pg_stat_activity WHERE " + ELIGIBLE, params).fetchall()
        for row in rows:
            row["action"] = "cancel" if row["state"] == "active" else "terminate"
            if apply:
                fn = "pg_cancel_backend" if row["action"] == "cancel" else "pg_terminate_backend"
                result = conn.execute(f"SELECT {fn}(pid) AS acted FROM pg_stat_activity WHERE pid = %(pid)s AND " + ELIGIBLE,
                                      {**params, "pid": row["pid"]}).fetchone()
                row["acted"] = bool(result and result["acted"])
                log.warning("EQM database watchdog pid=%s action=%s acted=%s", row["pid"], row["action"], row["acted"])
        return rows


async def _run() -> None:
    while True:
        await asyncio.sleep(env_int("DB_WATCHDOG_INTERVAL_SECONDS", 60))
        try:
            await asyncio.to_thread(scan, apply=True)
        except Exception:
            # Do not log credentials or SQL text, including via driver exceptions.
            log.warning("EQM database watchdog check failed; will retry")


def start_watchdog() -> None:
    global _task
    if not get_settings().db_watchdog_enabled:
        return
    if make_url(get_settings().database_url).get_backend_name() == "postgresql" and _task is None:
        _task = asyncio.create_task(_run())


async def stop_watchdog() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Act on eligible sessions; default only reports")
    args = parser.parse_args()
    for item in scan(apply=args.apply):
        print(item)
