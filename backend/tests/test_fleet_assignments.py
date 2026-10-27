from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch
import importlib.util
import json
import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.api.auth import get_current_user
from app.api.fleet_assignments import router
from app.db.session import get_db
from app.domain.fleet_assignments import Principal, assignment_targets, may_view_assignment, parse_roster
from app.models import AuditEvent, Base, CharacterFitting, CharacterFittingItem, Doctrine, DoctrineFitting, EsiToken, EveCharacter, EveType, User, UserSectionPermission
from app.models.fleet_assignments import FleetAssignmentOperation, FleetAssignmentPilot

ROOT = "/fleet-assignments"

@pytest.fixture
def fleet():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = Session(engine, expire_on_commit=False)
    users = [User(email=f"user{i}@test.invalid", display_name=f"Account {i}", role=role)
             for i, role in enumerate(["host", "officer", "member", "member", "view_only", "applicant"])]
    db.add_all(users); db.flush()
    pilots = [EveCharacter(character_id=900001+i, name=name, owner_user_id=users[owner].id)
              for i, (name, owner) in enumerate([("Alpha Pilot", 2), ("Bravo Pilot", 3), ("Alt Pilot", 2), ("Host Pilot", 0)])]
    db.add_all(pilots); db.flush()
    for pilot in pilots:
        db.add(EsiToken(user_id=pilot.owner_user_id, character_id=pilot.id, scopes="esi-fittings.read_fittings.v1", encrypted_refresh_token="fixture"))
    db.add_all([EveType(type_id=100, name="Caracal"), EveType(type_id=101, name="Missile Launcher II")]); db.flush()
    fits = [CharacterFitting(character_id=pilots[3].id, name="Fleet Caracal", ship_type_id=100, is_shared=True),
            CharacterFitting(character_id=pilots[1].id, name="Private Bravo Fit", ship_type_id=100, is_shared=False)]
    db.add_all(fits); db.flush()
    db.add(CharacterFittingItem(fitting_id=fits[0].id, type_id=101, flag="HiSlot0", quantity=1))
    doctrine = Doctrine(name="Missile Wing", fitting_id=fits[0].id, created_by_user_id=users[0].id, is_shared=True)
    db.add(doctrine); db.commit()
    current = [users[0]]
    app = FastAPI(); app.include_router(router)
    def identity():
        if current[0] is None:
            raise HTTPException(401, "Authentication required")
        return current[0]
    def database():
        try:
            yield db
        finally:
            db.rollback()
    app.dependency_overrides[get_current_user] = identity
    app.dependency_overrides[get_db] = database
    with TestClient(app) as client:
        yield client, db, users, pilots, fits, doctrine, current
    db.close(); engine.dispose()


def create(client, name="Test Fleet", **kwargs):
    response = client.post(f"{ROOT}/operations", json={"name": name, **kwargs})
    assert response.status_code == 201, response.text
    return response.json()


def mutate(client, op, path, **payload):
    response = client.post(f"{ROOT}/operations/{op['id']}/{path}", json={"revision": op["revision"], **payload})
    assert response.status_code == 200, response.text
    return response.json()


def prepared(fleet):
    client, db, users, pilots, fits, doctrine, current = fleet
    op = create(client, briefing="Form up at 19:00 EVE")
    op = mutate(client, op, "slots", fitting_id=fits[0].id, doctrine_id=doctrine.id, role="Damage", target_count=2)
    op = mutate(client, op, "roster", text="Name\tShip\nAlpha Pilot\tCaracal\nBravo Pilot\tCaracal\nAlt Pilot\tCaracal")["operation"]
    return op


def publish(client, op):
    response = client.patch(f"{ROOT}/operations/{op['id']}", json={"revision": op["revision"], "status": "published"})
    assert response.status_code == 200, response.text
    return response.json()


def assigned(fleet):
    op = prepared(fleet)
    return mutate(fleet[0], op, "assign", pilot_ids=[pilot["id"] for pilot in op["pilots"]], slot_key=op["slots"][0]["key"])


def test_portable_rules_and_tab_roster():
    names, duplicates = parse_roster("Ship\tName\tRole\nCaracal\tAlpha Pilot\tDPS\nCaracal\t alpha   pilot \tDPS\n\n")
    assert names == ["Alpha Pilot"] and duplicates == ["alpha pilot"]
    assert assignment_targets([1, 1, 2], [1, 2]) == [1, 2]
    with pytest.raises(ValueError): assignment_targets([3], [1, 2])
    principal = Principal("host", frozenset({1}), True)
    assert may_view_assignment(principal, 1, True)
    assert not may_view_assignment(principal, 2, True)
    assert not may_view_assignment(principal, 1, False)
    with pytest.raises(ValueError): parse_roster("\n".join(f"Pilot {i}" for i in range(501)))


def test_complete_persisted_workflow_and_personal_isolation(fleet):
    client, db, users, pilots, fits, doctrine, current = fleet
    op = assigned(fleet)
    current[0] = users[2]
    assert client.get(f"{ROOT}/my").json() == []
    current[0] = users[0]; op = publish(client, op)
    current[0] = users[2]
    response = client.get(f"{ROOT}/my/{op['id']}")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    data = response.json()[0]
    assert {row["name"] for row in data["assignments"]} == {"Alpha Pilot", "Alt Pilot"}
    assert "Bravo Pilot" not in response.text
    assert "slots" not in data and "pilots" not in data and "revision" not in data
    assert "Missile Launcher II" in data["assignments"][0]["fitting"]["eft"]
    assert db.scalar(select(FleetAssignmentPilot).where(FleetAssignmentPilot.name == "Alpha Pilot")).fitting_snapshot["name"] == "Fleet Caracal"
    current[0] = users[3]
    assert [row["name"] for row in client.get(f"{ROOT}/my").json()[0]["assignments"]] == ["Bravo Pilot"]
    current[0] = users[0]
    assert client.get(f"{ROOT}/my").json() == []  # Host has no assigned pilot.


@pytest.mark.parametrize("index", [2, 3, 4, 5])
def test_non_planners_cannot_read_or_mutate_board(fleet, index):
    client, db, users, pilots, fits, doctrine, current = fleet
    op = prepared(fleet); current[0] = users[index]
    for path in ["operations", f"operations/{op['id']}", "sources", "presets"]:
        assert client.get(f"{ROOT}/{path}").status_code == 403
    assert client.post(f"{ROOT}/operations", json={"name": "Intrusion"}).status_code == 403
    assert client.post(f"{ROOT}/operations/{op['id']}/assign", json={"revision": op["revision"], "pilot_ids": [op["pilots"][0]["id"]], "slot_key": op["slots"][0]["key"]}).status_code == 403


def test_anonymous_cannot_access_personal_or_manager_endpoints(fleet):
    client, _, _, _, _, _, current = fleet
    current[0] = None
    for path in ["my", "my/1", "meta", "operations", "sources", "presets"]:
        assert client.get(f"{ROOT}/{path}").status_code == 401


def test_unknown_operation_and_unrelated_fleet_do_not_disclose_metadata(fleet):
    client, _, users, _, _, _, current = fleet
    op = publish(client, assigned(fleet))
    current[0] = users[4]
    assert client.get(f"{ROOT}/my/{op['id']}").status_code == 404
    assert client.get(f"{ROOT}/my/999999").status_code == 404
    assert client.get(f"{ROOT}/my?user_id={users[2].id}&character_id=900001").json() == []


def test_revoke_and_transfer_remove_personal_access(fleet):
    client, db, users, pilots, _, _, current = fleet
    op = publish(client, assigned(fleet)); current[0] = users[2]
    token = db.scalar(select(EsiToken).where(EsiToken.character_id == pilots[0].id))
    token.revoked_at = datetime.now(timezone.utc)
    pilots[2].owner_user_id = users[3].id; db.commit()
    assert client.get(f"{ROOT}/my").json() == []
    # A new owner must have their own active SSO link; old token is insufficient.
    current[0] = users[3]
    assert {row["name"] for row in client.get(f"{ROOT}/my").json()[0]["assignments"]} == {"Bravo Pilot"}


def test_stale_revision_rejected_without_partial_changes(fleet):
    client, db, *_ = fleet
    op = prepared(fleet)
    saved = mutate(client, op, "assign", pilot_ids=[op["pilots"][0]["id"]], slot_key=op["slots"][0]["key"])
    response = client.post(f"{ROOT}/operations/{op['id']}/assign", json={"revision": op["revision"], "pilot_ids": [op["pilots"][1]["id"]], "slot_key": op["slots"][0]["key"]})
    assert response.status_code == 409
    fresh = client.get(f"{ROOT}/operations/{op['id']}").json()
    assert fresh["revision"] == saved["revision"]
    assert sum(pilot["slot_key"] is not None for pilot in fresh["pilots"]) == 1


def test_cross_operation_pilot_and_slot_rejected(fleet):
    client = fleet[0]
    first = prepared(fleet); second = prepared(fleet)
    response = client.post(f"{ROOT}/operations/{first['id']}/assign", json={"revision": first["revision"], "pilot_ids": [second["pilots"][0]["id"]], "slot_key": first["slots"][0]["key"]})
    assert response.status_code == 422
    response = client.post(f"{ROOT}/operations/{first['id']}/assign", json={"revision": first["revision"], "pilot_ids": [first["pilots"][0]["id"]], "slot_key": second["slots"][0]["key"]})
    assert response.status_code == 404
    assert client.delete(f"{ROOT}/operations/{first['id']}/pilots/{second['pilots'][0]['id']}?revision={first['revision']}").status_code == 404


def test_roster_deduplication_unresolved_and_exact_esi_matching(fleet):
    client = fleet[0]
    op = create(client)
    lookup = AsyncMock(return_value={"characters": [{"name": "External Pilot", "id": 999001}], "corporations": [{"name": "Fake Corp", "id": 999002}]})
    with patch("app.services.esi_client.EsiClient.post", lookup):
        result = mutate(client, op, "roster", text="Alpha Pilot\nalpha pilot\nExternal Pilot\nFake Corp")
    assert result["report"]["added"] == 3
    assert result["report"]["duplicates"] == ["alpha pilot"]
    assert result["report"]["unresolved"] == ["Fake Corp"]
    op = result["operation"]
    assert next(p for p in op["pilots"] if p["name"] == "External Pilot")["character_id"] == 999001
    with patch("app.services.esi_client.EsiClient.post", AsyncMock(return_value={"characters": []})):
        result = mutate(client, op, "roster", text="Alpha Pilot\nFake Corp")
    assert result["report"]["added"] == 0
    assert len(result["operation"]["pilots"]) == 3


def test_esi_failure_preserves_unresolved_rows_and_blocks_assignment(fleet):
    client, _, _, _, fits, _, _ = fleet
    op = create(client)
    with patch("app.services.esi_client.EsiClient.post", AsyncMock(side_effect=HTTPException(503, "Unavailable"))):
        result = mutate(client, op, "roster", text="Unresolved Pilot")
    assert result["report"]["warning"]
    op = mutate(client, result["operation"], "slots", fitting_id=fits[0].id)
    response = client.post(f"{ROOT}/operations/{op['id']}/assign", json={"revision": op["revision"], "pilot_ids": [op["pilots"][0]["id"]], "slot_key": op["slots"][0]["key"]})
    assert response.status_code == 422
    assert client.patch(f"{ROOT}/operations/{op['id']}", json={"revision": op["revision"], "status": "published"}).status_code == 422


def test_presets_snapshot_fittings_but_never_pilots_or_assignments(fleet):
    client, db, users, pilots, fits, _, _ = fleet
    op = assigned(fleet)
    response = client.post(f"{ROOT}/operations/{op['id']}/preset", json={"revision": op["revision"], "name": "Missile preset"})
    assert response.status_code == 201
    saved = response.json()
    fits[0].name = "Edited later"; db.commit()
    clone = create(client, name="Clone", preset_id=saved["id"])
    assert clone["pilots"] == [] and clone["status"] == "draft"
    assert clone["slots"][0]["fitting"]["name"] == "Fleet Caracal"
    assert clone["slots"][0]["key"] != op["slots"][0]["key"]
    assert clone["slots"][0]["target_count"] == 2
    assert client.delete(f"{ROOT}/presets/{saved['id']}").status_code == 200
    assert client.get(f"{ROOT}/operations/{clone['id']}").json()["slots"] == clone["slots"]


def test_private_sources_cannot_be_redistributed_by_staff(fleet):
    client, _, users, _, fits, doctrine, current = fleet
    sources = client.get(f"{ROOT}/sources").json()
    assert {fit["id"] for fit in sources["fittings"]} == {fits[0].id}
    op = create(client)
    response = client.post(f"{ROOT}/operations/{op['id']}/slots", json={"revision": op["revision"], "fitting_id": fits[1].id})
    assert response.status_code == 403
    current[0] = users[1]  # Officer may manage shared fits.
    assert client.post(f"{ROOT}/operations/{op['id']}/slots", json={"revision": op["revision"], "fitting_id": fits[0].id, "doctrine_id": doctrine.id}).status_code == 200


def test_archive_unpublish_and_clear_revoke_personal_view(fleet):
    client, _, users, _, _, _, current = fleet
    op = publish(client, assigned(fleet))
    op = client.patch(f"{ROOT}/operations/{op['id']}", json={"revision": op["revision"], "status": "archived"}).json()
    current[0] = users[2]
    assert client.get(f"{ROOT}/my").json() == []
    current[0] = users[0]
    assert client.post(f"{ROOT}/operations/{op['id']}/assign", json={"revision": op["revision"], "pilot_ids": [op["pilots"][0]["id"]]}).status_code == 409
    op = client.patch(f"{ROOT}/operations/{op['id']}", json={"revision": op["revision"], "status": "draft"}).json()
    op = publish(client, op)
    op = mutate(client, op, "assign", pilot_ids=[p["id"] for p in op["pilots"]], slot_key=None)
    current[0] = users[2]
    assert client.get(f"{ROOT}/my").json() == []


def test_section_permission_is_enforced(fleet):
    client, db, users, _, _, _, current = fleet
    current[0] = users[2]
    db.add(UserSectionPermission(user_id=users[2].id, section="fleet_assignments", can_view=False)); db.commit()
    assert client.get(f"{ROOT}/my").status_code == 403


def test_role_edits_removals_and_assignment_history(fleet):
    client, db, *_ = fleet
    op = assigned(fleet); key = op["slots"][0]["key"]
    assert client.delete(f"{ROOT}/operations/{op['id']}/slots/{key}?revision={op['revision']}").status_code == 409
    op = mutate(client, op, "assign", pilot_ids=[p["id"] for p in op["pilots"]], slot_key=None)
    response = client.patch(f"{ROOT}/operations/{op['id']}/slots/{key}", json={"revision": op["revision"], "role": "Support", "target_count": 4})
    assert response.status_code == 200; op = response.json()
    assert op["slots"][0]["role"] == "Support"
    op = client.delete(f"{ROOT}/operations/{op['id']}/slots/{key}?revision={op['revision']}").json()
    assert op["slots"] == []
    events = list(db.scalars(select(AuditEvent).where(AuditEvent.event_kind == "fleet_assignments")).all())
    changes = [json.loads(event.body) for event in events if json.loads(event.body)["action"] == "assignments changed"]
    assert changes[-1]["changes"][0]["previous_fitting"]["name"] == "Fleet Caracal"


def test_validation_rejects_overposting_and_bad_counts(fleet):
    client = fleet[0]; op = create(client)
    for payload in [{"fitting_id": 1, "target_count": 0}, {"fitting_id": 1, "target_count": 501}, {"fitting_id": 1, "fitting": {"eft": "Injected"}}]:
        assert client.post(f"{ROOT}/operations/{op['id']}/slots", json={"revision": op["revision"], **payload}).status_code == 422
    assert client.post(f"{ROOT}/operations", json={"name": "   "}).status_code == 422
    assert client.post(f"{ROOT}/operations/{op['id']}/assign", json={"revision": op["revision"], "pilot_ids": []}).status_code == 422


def test_migration_round_trip_and_single_head():
    path = Path(__file__).parents[1] / "alembic/versions/0088_fleet_assignments.py"
    spec = importlib.util.spec_from_file_location("fleet_migration", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            assert "fleet_assignment_pilots" in inspect(connection).get_table_names()
            assert {column["name"] for column in inspect(connection).get_columns("fleet_assignment_operations")} == set(FleetAssignmentOperation.__table__.columns.keys())
            module.downgrade()
            assert inspect(connection).get_table_names() == ["users"]
            module.upgrade()
    config = Config()
    config.set_main_option("script_location", str(path.parents[1]))
    assert ScriptDirectory.from_config(config).get_heads() == ["0088_fleet_assignments"]


def test_real_authentication_and_elevated_claim_cannot_bypass_isolation(fleet):
    from app.core.security import create_access_token
    client, db, users, _, _, _, current = fleet
    op = publish(client, assigned(fleet))
    # Exercise the production bearer/cookie authenticator, not the fixture identity.
    del client.app.dependency_overrides[get_current_user]
    token = create_access_token(str(users[2].id), {"role": "host"})
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get(f"{ROOT}/my/{op['id']}", headers=headers)
    assert response.status_code == 200
    assert {pilot["name"] for pilot in response.json()[0]["assignments"]} == {"Alpha Pilot", "Alt Pilot"}
    assert client.get(f"{ROOT}/operations", headers=headers).status_code == 403
    assert client.get(f"{ROOT}/my").status_code == 401
    assert client.get(f"{ROOT}/my", headers={"Authorization": "Bearer invalid"}).status_code == 401


def test_retry_resolves_same_roster_row_without_duplicating(fleet):
    client = fleet[0]; op = create(client)
    with patch("app.services.esi_client.EsiClient.post", AsyncMock(return_value={"characters": []})):
        op = mutate(client, op, "roster", text="New Pilot")["operation"]
    original_id = op["pilots"][0]["id"]
    with patch("app.services.esi_client.EsiClient.post", AsyncMock(return_value={"characters": [{"name": "New Pilot", "id": 999001}]})):
        result = mutate(client, op, "roster", text="New Pilot")
    assert result["report"]["added"] == 0
    assert result["report"]["resolved"] == 1
    assert result["report"]["unresolved"] == []
    assert result["operation"]["pilots"][0]["id"] == original_id
    assert result["operation"]["pilots"][0]["character_id"] == 999001
