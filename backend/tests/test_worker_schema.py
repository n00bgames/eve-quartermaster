from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.db.wait_for_schema import required_heads, wait_for_schema


def test_worker_waits_for_upgrade_before_accepting_jobs():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)"))
        conn.execute(text("INSERT INTO alembic_version VALUES ('0110_structure_timers')"))
    sleeps = []
    def migrate(seconds):
        sleeps.append(seconds)
        with engine.begin() as conn:
            conn.execute(text("UPDATE alembic_version SET version_num='0111_local_universe'"))
    wait_for_schema(engine, required_heads(), clock=lambda: 0, sleep=migrate)
    assert sleeps == [2]
    assert required_heads() == {"0111_local_universe"}
    engine.dispose()


@pytest.mark.parametrize("revision", [None, "0110_structure_timers", "future_schema"])
def test_worker_fails_closed_for_missing_old_or_mismatched_schema(revision):
    engine = create_engine("sqlite://")
    if revision:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)"))
            conn.execute(text("INSERT INTO alembic_version VALUES (:revision)"), {"revision": revision})
    with pytest.raises(SystemExit, match="worker not started"):
        wait_for_schema(engine, required_heads(), timeout=0)
    engine.dispose()


def test_compose_worker_waits_and_backend_owns_migration():
    import yaml
    root = Path(__file__).parents[2]
    if not (root / "docker-compose.yml").exists():
        pytest.skip("Compose source contract is checked from the repository checkout")
    services = yaml.safe_load((root / "docker-compose.yml").read_text())["services"]
    command = services["worker"]["command"][2]
    assert command.index("wait_for_schema &&") < command.index("exec rq worker")
    assert "alembic upgrade head && exec uvicorn" in (root / "backend/Dockerfile").read_text()
