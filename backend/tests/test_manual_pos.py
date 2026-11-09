"""Manual POS persistence, consent boundaries, validation and concurrent edits."""
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api import manual_pos, structures
from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import Base, User, UserSectionPermission
from app.models.manual_pos import ManualPos

BASE = "/api/structures/manual-pos"
AT = datetime(2026, 11, 8, 22, tzinfo=timezone.utc)


def reading(**changes):
    return {"id": str(uuid4()), "name": "Demo bridge tower", "tower_type": "Caldari Control Tower",
            "corporation_name": "Demo Logistics", "location": "Demo System V - Moon 14", "state": "online",
            "fuel_blocks": 22080, "fuel_per_hour": 40, "stront_units": 16666, "stront_per_hour": 400,
            "observed_at": "2026-11-08T22:00:00Z", "reinforced_until": None, "notes": "Private test note", **changes}


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setattr(manual_pos, "utcnow", lambda: AT)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = Session(engine, expire_on_commit=False)
    users = [User(email=f"manual{i}@invalid.test", display_name=f"Demo {role}", role=role)
             for i, role in enumerate(("officer", "admin", "member"))]
    db.add_all(users); db.commit()
    actor = [users[0]]
    def identity():
        if actor[0] is None:
            raise HTTPException(401, "Sign in required")
        return actor[0]
    def database():
        try:
            yield db
        finally:
            db.rollback()
    def no_esi(*args, **kwargs):
        raise AssertionError("Manual tracking must never request ESI")
    monkeypatch.setattr(structures, "EsiClient", no_esi)
    app = FastAPI(); app.include_router(structures.router, prefix="/api")
    app.dependency_overrides[get_current_user] = identity
    app.dependency_overrides[get_db] = database
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, db=db, users=users, actor=actor, app=app)
    db.close(); engine.dispose()


def test_persistence_without_character_or_token_and_retry(env):
    e = env; body = reading()
    created = e.client.post(BASE, json=body)
    assert created.status_code == 201, created.text
    data = created.json()
    assert created.headers["cache-control"] == "private, no-store"
    assert data["source"] == "manual" and data["version"] == 1
    assert "owner_user_id" not in data
    assert data["fuel_blocks"] == 22080 and data["stront_units"] == 16666
    e.db.expire_all()
    listed = e.client.get(BASE)
    assert listed.status_code == 200 and listed.json()["rows"] == [data]
    assert listed.headers["cache-control"] == "private, no-store"
    retry = e.client.post(BASE, json=body)
    assert retry.status_code == 200 and retry.json() == data
    assert len(list(e.db.scalars(select(ManualPos)))) == 1
    assert e.client.post(BASE, json={**body, "fuel_blocks": 100}).status_code == 409


def test_owner_only_including_other_admin(env):
    e = env; body = reading(); e.client.post(BASE, json=body)
    e.actor[0] = e.users[1]
    assert e.client.get(BASE).json()["rows"] == []
    update = {key: value for key, value in body.items() if key != "id"} | {"version": 1}
    assert e.client.put(BASE + "/" + body["id"], json=update).status_code == 404
    assert e.client.delete(BASE + "/" + body["id"] + "?version=1").status_code == 404
    assert e.client.post(BASE, json=body).status_code == 409
    e.actor[0] = e.users[0]
    assert e.client.get(BASE).json()["rows"][0]["notes"] == "Private test note"


def test_auth_and_section_permission_apply_to_all_operations(env):
    e = env; body = reading(); e.client.post(BASE, json=body)
    requests = [("get", BASE, None), ("post", BASE, reading()),
                ("put", BASE + "/" + body["id"], {k: v for k, v in body.items() if k != "id"} | {"version": 1}),
                ("delete", BASE + "/" + body["id"] + "?version=1", None)]
    for actor, status in ((None, 401), (e.users[2], 403)):
        e.actor[0] = actor
        for method, path, payload in requests:
            assert e.client.request(method, path, **({"json": payload} if payload else {})).status_code == status
    e.actor[0] = e.users[2]
    e.db.add(UserSectionPermission(user_id=e.users[2].id, section="structures", can_view=True)); e.db.commit()
    assert e.client.post(BASE, json=reading()).status_code == 201
    e.actor[0] = e.users[0]
    e.db.add(UserSectionPermission(user_id=e.users[0].id, section="structures", can_view=False)); e.db.commit()
    assert e.client.get(BASE).status_code == 403


def test_edit_refuel_state_change_and_delete_conflicts(env):
    e = env; body = reading(); e.client.post(BASE, json=body)
    updated = {k: v for k, v in body.items() if k != "id"} | {
        "version": 1, "fuel_blocks": 30000, "state": "reinforced", "reinforced_until": "2026-11-10T10:00:00Z"}
    path = BASE + "/" + body["id"]
    result = e.client.put(path, json=updated)
    assert result.status_code == 200, result.text
    assert result.json()["version"] == 2 and result.json()["fuel_blocks"] == 30000
    assert e.client.put(path, json=updated).status_code == 409
    assert e.client.delete(path + "?version=1").status_code == 409
    assert e.client.get(BASE).json()["rows"][0]["state"] == "reinforced"
    result = e.client.delete(path + "?version=2")
    assert result.status_code == 200 and result.json()["removed"] is True
    assert result.headers["cache-control"] == "private, no-store"
    assert e.client.get(BASE).json()["rows"] == []
    assert e.client.put(path, json={**updated, "version": 2}).status_code == 404


@pytest.mark.parametrize("changes", [
    {"fuel_blocks": -1}, {"fuel_blocks": 1.1}, {"fuel_blocks": True}, {"fuel_blocks": "40"},
    {"stront_units": -1}, {"stront_units": 2_000_000_001}, {"fuel_per_hour": 0},
    {"fuel_per_hour": -5}, {"fuel_per_hour": 100_001}, {"stront_per_hour": 0.00001},
    {"state": "hacked"}, {"name": "  "}, {"name": "x" * 161}, {"notes": "x" * 4001},
    {"location": "x" * 241}, {"tower_type": ""}, {"observed_at": "2026-11-09T22:00:00Z"},
    {"observed_at": "2026-11-08T22:00:00"}, {"observed_at": "2000-01-01T00:00:00Z"},
    {"reinforced_until": "2026-11-09T22:00:00Z"},
    {"state": "reinforced", "reinforced_until": "2026-11-07T22:00:00Z"},
    {"owner_user_id": 2}, {"source": "esi"}, {"version": 3}, {"id": "invalid"},
])
def test_invalid_readings_rejected_without_write(env, changes):
    r = env.client.post(BASE, json=reading(**changes))
    assert r.status_code == 422, r.text
    assert env.client.get(BASE).json()["rows"] == []


@pytest.mark.parametrize("state", ["online", "offline", "reinforced", "unknown"])
@pytest.mark.parametrize("quantity", [None, 0])
def test_unknown_empty_and_states_remain_distinct(env, state, quantity):
    result = env.client.post(BASE, json=reading(state=state, fuel_blocks=quantity, stront_units=quantity))
    assert result.status_code == 201, result.text
    assert result.json()["fuel_blocks"] is quantity and result.json()["stront_units"] is quantity
    assert result.json()["state"] == state and result.json()["reinforced_until"] is None


def test_utc_normalization_and_plain_text(env):
    body = reading(name="  Demo <script>  ", observed_at="2026-11-08T23:00:00+02:00", state="reinforced",
                   reinforced_until="2026-11-10T12:00:00+02:00", notes=" <img src=x onerror=alert(1)> ")
    result = env.client.post(BASE, json=body)
    assert result.status_code == 201
    assert result.json()["observed_at"] == "2026-11-08T21:00:00+00:00"
    assert result.json()["reinforced_until"] == "2026-11-10T10:00:00+00:00"
    assert result.json()["name"] == "Demo <script>"  # React renders these as text.
    assert env.client.post(BASE, json=body).status_code == 200


def test_migration_upgrade_roundtrip_and_nonempty_downgrade_guard():
    path = Path(__file__).parents[1] / "alembic/versions/0107_manual_pos.py"
    spec = importlib.util.spec_from_file_location("manual_pos_migration", path)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        assert "manual_pos" in inspect(connection).get_table_names()
        values = reading(); values.pop("id")
        values["observed_at"] = AT
        connection.execute(ManualPos.__table__.insert().values(id=str(uuid4()), owner_user_id=1,
            **values, version=1, created_at=AT, updated_at=AT))
        with pytest.raises(RuntimeError, match="Export"):
            migration.downgrade()
        assert "manual_pos" in inspect(connection).get_table_names()
        connection.execute(ManualPos.__table__.delete())
        migration.downgrade()
        assert "manual_pos" not in inspect(connection).get_table_names()
        migration.upgrade()
        assert "manual_pos" in inspect(connection).get_table_names()
    engine.dispose()
