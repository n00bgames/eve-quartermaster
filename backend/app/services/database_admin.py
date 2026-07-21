from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any
import zipfile

from sqlalchemy import inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.models import User

BACKUP_FORMAT = "eqm-postgresql-data-v1"
BACKUP_FILENAME = "database.dump"
MANIFEST_FILENAME = "manifest.json"
MAX_BACKUP_BYTES = 8 * 1024 * 1024 * 1024


class DatabaseAdminError(RuntimeError):
    pass


def _connection_args() -> tuple[list[str], dict[str, str]]:
    url = make_url(get_settings().database_url)
    if not url.drivername.startswith("postgresql"):
        raise DatabaseAdminError("Database maintenance currently requires PostgreSQL.")
    args = [
        "--host", url.host or "localhost",
        "--port", str(url.port or 5432),
        "--username", url.username or "postgres",
        "--dbname", url.database or "postgres",
    ]
    env = os.environ.copy()
    if url.password:
        env["PGPASSWORD"] = url.password
    return args, env


def _run(command: list[str], *, timeout: int = 3600, env: dict[str, str] | None = None) -> None:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DatabaseAdminError(f"Database utility failed: {exc}") from exc
    if result.returncode:
        detail = (result.stderr or result.stdout or "Unknown database utility error").strip()
        raise DatabaseAdminError(detail[-2000:])


def _remove_unsupported_session_settings(sql_path: Path) -> None:
    """Keep newer clients and pre-fix EQM backups compatible with restore."""
    lines = sql_path.read_text(encoding="utf-8").splitlines(keepends=True)
    sanitized: list[str] = []
    skip_alembic_data = False
    for line in lines:
        if line.startswith("COPY ") and "alembic_version" in line:
            skip_alembic_data = True
            continue
        if skip_alembic_data:
            if line.rstrip() == r"\.":
                skip_alembic_data = False
            continue
        if line.startswith("SET transaction_timeout ="):
            continue
        sanitized.append(line)
    sql_path.write_text("".join(sanitized), encoding="utf-8")


def current_revision(db: Session) -> str:
    return str(db.execute(text("SELECT version_num FROM alembic_version")).scalar_one())


def database_status(db: Session) -> dict[str, Any]:
    inspector = inspect(db.get_bind())
    size = db.execute(text("SELECT pg_database_size(current_database())")).scalar_one()
    return {
        "dialect": db.get_bind().dialect.name,
        "revision": current_revision(db),
        "size_bytes": int(size),
        "table_count": len([name for name in inspector.get_table_names() if name != "alembic_version"]),
    }


def create_backup(db: Session) -> tuple[Path, str]:
    args, env = _connection_args()
    work_dir = Path(tempfile.mkdtemp(prefix="eqm-backup-"))
    dump_path = work_dir / BACKUP_FILENAME
    archive_path = work_dir / f"eqm-database-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.eqmbackup"
    _run([
        "pg_dump", *args, "--format=custom", "--data-only", "--compress=6",
        "--no-owner", "--no-privileges", "--exclude-table-data=alembic_version",
        "--file", str(dump_path),
    ], timeout=3600, env=env)
    manifest = {
        "format": BACKUP_FORMAT,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "schema_revision": current_revision(db),
        "contains_host": bool(db.scalar(select(User.id).where(User.role == "host", User.deleted_at.is_(None)).limit(1))),
    }
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(MANIFEST_FILENAME, json.dumps(manifest, indent=2))
        archive.write(dump_path, BACKUP_FILENAME)
    dump_path.unlink(missing_ok=True)
    return archive_path, archive_path.name


def remove_backup(path: Path) -> None:
    shutil.rmtree(path.parent, ignore_errors=True)


def inspect_backup(archive_path: Path, expected_revision: str) -> tuple[dict[str, Any], Path]:
    work_dir = archive_path.parent
    try:
        with zipfile.ZipFile(archive_path) as archive:
            names = set(archive.namelist())
            if names != {MANIFEST_FILENAME, BACKUP_FILENAME}:
                raise DatabaseAdminError("This is not a recognized EQM database backup.")
            manifest = json.loads(archive.read(MANIFEST_FILENAME))
            if manifest.get("format") != BACKUP_FORMAT:
                raise DatabaseAdminError("Unsupported EQM backup format.")
            if manifest.get("schema_revision") != expected_revision:
                raise DatabaseAdminError(
                    f"Backup schema {manifest.get('schema_revision') or 'unknown'} does not match current schema {expected_revision}."
                )
            if not manifest.get("contains_host"):
                raise DatabaseAdminError("Backup does not contain a host account and cannot be restored safely.")
            archive.extract(BACKUP_FILENAME, work_dir)
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError) as exc:
        raise DatabaseAdminError("The selected file is not a valid EQM database backup.") from exc
    return manifest, work_dir / BACKUP_FILENAME


def restore_backup(archive_path: Path, expected_revision: str, host_fallback: dict[str, Any]) -> dict[str, Any]:
    manifest, dump_path = inspect_backup(archive_path, expected_revision)
    args, env = _connection_args()
    sql_path = archive_path.parent / "database.sql"
    truncate_path = archive_path.parent / "truncate.sql"

    _run([
        "pg_restore", "--data-only", "--disable-triggers", "--no-owner", "--no-privileges",
        "--file", str(sql_path), str(dump_path),
    ], timeout=3600)
    _remove_unsupported_session_settings(sql_path)

    inspector = inspect(engine)
    tables = [name for name in inspector.get_table_names() if name != "alembic_version"]
    quoted = ", ".join(engine.dialect.identifier_preparer.quote(name) for name in tables)
    truncate_path.write_text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE;\n", encoding="utf-8")

    engine.dispose()
    _run([
        "psql", *args, "--single-transaction", "--set=ON_ERROR_STOP=1",
        "--file", str(truncate_path), "--file", str(sql_path),
    ], timeout=7200, env=env)

    with SessionLocal() as verify_db:
        host = verify_db.scalar(select(User).where(User.role == "host", User.deleted_at.is_(None)).limit(1))
        if host is None:
            host = verify_db.scalar(select(User).where(User.email == host_fallback["email"]))
            if host is None:
                host = User(**host_fallback)
                verify_db.add(host)
            else:
                host.display_name = host_fallback["display_name"]
                host.password_hash = host_fallback["password_hash"]
                host.timezone = host_fallback["timezone"]
                host.deleted_at = None
            host.role = "host"
            verify_db.commit()

    return {"status": "restored", "created_at": manifest.get("created_at"), "revision": expected_revision}


def clear_database(db: Session, host_user_id: int) -> dict[str, Any]:
    inspector = inspect(db.get_bind())
    tables = [name for name in inspector.get_table_names() if name not in {"alembic_version", "users"}]
    quoted = ", ".join(db.get_bind().dialect.identifier_preparer.quote(name) for name in tables)
    if quoted:
        db.execute(text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))
    deleted_users = db.execute(text("DELETE FROM users WHERE id <> :host_id"), {"host_id": host_user_id}).rowcount or 0
    db.commit()
    return {"status": "cleared", "deleted_users": deleted_users, "retained_host_user_id": host_user_id}
