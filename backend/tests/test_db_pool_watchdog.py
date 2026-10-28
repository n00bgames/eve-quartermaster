import os
import unittest
from unittest.mock import patch, MagicMock
from app.db.session import engine_options
from app.db import watchdog, session
from fastapi import HTTPException
from sqlalchemy.exc import TimeoutError as PoolTimeout


class PoolWatchdogTests(unittest.TestCase):
    def test_bounded_postgres_pool_and_sqlite_compatibility(self):
        with patch.dict(os.environ, {}, clear=True):
            opts = engine_options("postgresql+psycopg://u:p@localhost/db")
        self.assertEqual(opts["pool_size"], 10)
        self.assertEqual(opts["max_overflow"], 20)
        self.assertEqual(opts["connect_args"]["application_name"], "eqm-api")
        self.assertEqual(engine_options("sqlite://"), {"pool_pre_ping": True})
        with patch.dict(os.environ, {"DB_MAX_OVERFLOW": "-1"}):
            with self.assertRaises(ValueError): engine_options("postgresql://u:p@localhost/db")

    def connection(self):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = {"acquired": True, "acted": True}
        conn.execute.return_value.fetchall.return_value = [{"pid": 100, "state": "idle in transaction"}, {"pid": 101, "state": "active"}]
        return conn

    def test_dry_run_never_signals_and_apply_rechecks_eligibility(self):
        for apply in (False, True):
            conn = self.connection()
            with patch.object(watchdog, "get_settings", return_value=MagicMock(database_url="postgresql://u:p@localhost/db")), patch("psycopg.connect") as connect:
                connect.return_value.__enter__.return_value = conn
                rows = watchdog.scan(apply=apply)
            calls = [str(c.args[0]) for c in conn.execute.call_args_list]
            signals = [q for q in calls if "pg_cancel_backend" in q or "pg_terminate_backend" in q]
            self.assertEqual(len(signals), 2 if apply else 0)
            for q in signals:
                self.assertIn("application_name = 'eqm-api'", q)
                self.assertIn("datname = current_database()", q)
                self.assertIn("usename = current_user", q)
                self.assertIn("pid <> pg_backend_pid()", q)
                self.assertIn("clock_timestamp()", q)
            self.assertEqual([r["action"] for r in rows], ["terminate", "cancel"])

    def test_another_watchdog_holds_lock(self):
        conn = self.connection(); conn.execute.return_value.fetchone.return_value = {"acquired": False}
        with patch.object(watchdog, "get_settings", return_value=MagicMock(database_url="postgresql://u:p@localhost/db")), patch("psycopg.connect") as connect:
            connect.return_value.__enter__.return_value = conn
            self.assertEqual(watchdog.scan(apply=True), [])
        self.assertEqual(conn.execute.call_count, 1)

    def test_pool_timeout_returns_retryable_503_and_closes_session(self):
        db = MagicMock()
        with patch.object(session, "SessionLocal", return_value=db):
            dependency = session.get_db()
            self.assertIs(next(dependency), db)
            with self.assertRaises(HTTPException) as failure:
                dependency.throw(PoolTimeout("pool exhausted"))
        self.assertEqual(failure.exception.status_code, 503)
        self.assertEqual(failure.exception.headers["Retry-After"], "5")
        db.rollback.assert_called_once()
        db.close.assert_called_once()
