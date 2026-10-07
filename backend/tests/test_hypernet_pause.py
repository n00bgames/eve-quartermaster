from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import importlib.util

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api import hypernet, hypernet_analytics
from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import Base, EsiToken, EveCharacter, EveType, EveGroup, EveCategory, Location, HyperNetSetting, HyperNetCharacterPause, HyperNetOffer, HyperNetOfferSnapshot, HyperNetParticipant, HyperNetParticipation, HyperNetAnalyticsPreference, User


@pytest.fixture
def data():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[row.__table__ for row in (
        User, EveCharacter, EsiToken, EveType, EveGroup, EveCategory, Location, HyperNetSetting, HyperNetCharacterPause,
        HyperNetOffer, HyperNetOfferSnapshot, HyperNetParticipant, HyperNetParticipation, HyperNetAnalyticsPreference,
    )])
    db = Session(engine, expire_on_commit=False)
    users = [User(id=i, email=f"pilot{i}@example.test", display_name=f"User {i}", role="admin" if i == 2 else "member") for i in (1, 2)]
    db.add_all(users)
    for cid, owner in [(1, 1), (2, 1), (3, 2)]:
        db.add(EveCharacter(id=cid, character_id=9000+cid, name=f"Pilot {cid}", owner_user_id=owner))
        db.add(EsiToken(user_id=owner, character_id=cid, encrypted_refresh_token="test", scopes=""))
    db.add(EveType(type_id=10, name="Barghest")); db.commit()
    app = FastAPI(); app.include_router(hypernet.router); app.include_router(hypernet_analytics.router)
    current = [users[0]]
    app.dependency_overrides[get_current_user] = lambda: current[0]
    app.dependency_overrides[get_db] = lambda: db
    # Keep this fixture independent from large relationship/market schemas.
    with patch.object(hypernet, "can_view_section", return_value=True) as access, \
         patch.object(hypernet, "offer_options", lambda: ()), \
         patch.object(hypernet, "participation_options", lambda: ()), \
         patch.object(hypernet, "record_audit_event"), \
         patch.object(hypernet, "serialize_participation", lambda row: {"id": row.id, "outcome": row.outcome}), \
         patch.object(hypernet, "serialize_offer", lambda row, **kw: {"id": row.id, "status": row.status}), \
         patch("app.services.hypernet_economics_engine._engine", return_value=("python", "", 1)), \
         TestClient(app) as client:
        yield SimpleNamespace(db=db, client=client, current=current, users=users, access=access)
    db.close(); engine.dispose()


def bid(cid=1):
    return {"character_id": cid, "item_type_id": 10, "seller_name": "Seller", "total_nodes": 16,
            "nodes_purchased": 2, "node_price": 312500000, "created_at": datetime.now(timezone.utc).isoformat()}


def offer(cid=1):
    now = datetime.now(timezone.utc)
    return {"seller_character_id": cid, "type_id": 10, "total_nodes": 16, "total_offer_price": 5000000000, "hypercores_required": 0,
            "created_offer_at": now.isoformat(), "expires_at": (now+timedelta(days=3)).isoformat()}


def set_pause(data, paused, cid=None):
    return data.client.patch("/hypernet/pause", json={"paused": paused, **({"character_id": cid} if cid else {})})


def test_defaults_enabled_and_state_private(data):
    result = data.client.get("/hypernet/pause")
    assert result.status_code == 200
    assert result.headers["cache-control"] == "private, no-store"
    state = result.json()
    assert state["account_paused"] is False
    assert [c["id"] for c in state["characters"]] == [1, 2]
    assert all(not c["paused"] and not c["effective_paused"] for c in state["characters"])


def test_character_pause_blocks_both_new_endpoints_but_not_other_character(data):
    assert set_pause(data, True, 1).status_code == 200
    assert data.client.post("/hypernet/participations", json=bid()).status_code == 403
    assert data.client.post("/hypernet/offers", json=offer()).status_code == 403
    assert data.db.scalars(select(HyperNetParticipation)).all() == []
    assert data.db.scalars(select(HyperNetOffer)).all() == []
    assert data.client.post("/hypernet/participations", json=bid(2)).status_code == 200
    assert data.client.post("/hypernet/offers", json=offer(2)).status_code == 200
    assert set_pause(data, False, 1).status_code == 200
    assert data.client.post("/hypernet/participations", json=bid()).status_code == 200


def test_account_override_covers_future_characters_and_preserves_individual_flags(data):
    set_pause(data, True, 1)
    state = set_pause(data, True).json()
    assert state["account_paused"] and all(c["effective_paused"] for c in state["characters"])
    assert [c["paused"] for c in state["characters"]] == [True, False]
    data.db.add(EveCharacter(id=4, character_id=9004, name="New Pilot", owner_user_id=1))
    data.db.add(EsiToken(user_id=1, character_id=4, encrypted_refresh_token="test", scopes="")); data.db.commit()
    assert data.client.post("/hypernet/participations", json=bid(2)).status_code == 403
    assert data.client.post("/hypernet/participations", json=bid(4)).status_code == 403
    assert data.client.post("/hypernet/offers", json=offer(4)).status_code == 403
    data.db.expire_all()
    state = data.client.get("/hypernet/pause").json()
    assert next(c for c in state["characters"] if c["id"] == 4)["effective_paused"]
    state = set_pause(data, False).json()
    assert next(c for c in state["characters"] if c["id"] == 1)["effective_paused"]
    assert not next(c for c in state["characters"] if c["id"] == 2)["effective_paused"]
    assert not next(c for c in state["characters"] if c["id"] == 4)["effective_paused"]
    assert data.client.post("/hypernet/offers", json=offer(4)).status_code == 200


def test_owner_only_even_for_staff_and_section_permission_gate(data):
    assert set_pause(data, True, 3).status_code == 404
    assert set_pause(data, True, 999).status_code == 404
    set_pause(data, True)
    data.current[0] = data.users[1]  # Admin still only controls its own account.
    assert set_pause(data, False, 1).status_code == 404
    assert data.client.get("/hypernet/pause").json()["account_paused"] is False
    assert [c["id"] for c in data.client.get("/hypernet/pause").json()["characters"]] == [3]
    data.access.return_value = False
    assert data.client.get("/hypernet/pause").status_code == 403
    assert set_pause(data, True).status_code == 403


@pytest.mark.parametrize("payload", [{"paused": "false"}, {"paused": 1}, {"paused": None}, {}, {"paused": True, "character_id": 0}, {"paused": True, "user_id": 2}])
def test_strict_input_validation(data, payload):
    assert data.client.patch("/hypernet/pause", json=payload).status_code == 422
    assert data.client.get("/hypernet/pause").json()["account_paused"] is False


def test_history_edits_outcomes_and_consent_remain_available_while_paused(data):
    created_bid = data.client.post("/hypernet/participations", json=bid()).json()["id"]
    created_offer = data.client.post("/hypernet/offers", json=offer()).json()["id"]
    data.db.add(HyperNetAnalyticsPreference(user_id=1, character_id=1, enabled=True)); data.db.commit()
    set_pause(data, True)
    assert data.client.get("/hypernet/participations").status_code == 200
    assert data.client.get("/hypernet/offers").status_code == 200
    assert data.client.patch(f"/hypernet/participations/{created_bid}", json={"notes": "Historical correction"}).status_code == 200
    # SQLite strips offsets; production PostgreSQL returns timezone-aware dates.
    row = data.db.get(HyperNetParticipation, created_bid)
    row.created_at = row.created_at.replace(tzinfo=timezone.utc)
    resolved = data.client.post(f"/hypernet/participations/{created_bid}/resolve", json={"outcome": "lost", "completed_at": datetime.now(timezone.utc).isoformat()})
    assert resolved.status_code == 200 and resolved.json()["outcome"] == "lost"
    assert data.client.patch(f"/hypernet/offers/{created_offer}", json={"notes": "Historical correction"}).status_code == 200
    result = data.client.post(f"/hypernet/offers/{created_offer}/reconcile", json={"status": "expired", "reconciled_at": datetime.now(timezone.utc).isoformat()})
    assert result.status_code == 200 and result.json()["status"] == "expired"
    assert data.db.get(HyperNetAnalyticsPreference, (1, 1)).enabled
    assert data.db.get(HyperNetParticipation, created_bid).profit_loss == -625000000
    analytics = data.client.get("/hypernet/analytics?days=0")
    assert analytics.status_code == 200 and analytics.json()["buying"]["losses"] == 1


def test_pause_does_not_overwrite_other_hypernet_settings(data):
    data.db.add(HyperNetSetting(user_id=1, monthly_node_limit=10, monthly_spend_limit=100, preferred_market_hub="amarr")); data.db.commit()
    set_pause(data, True)
    setting = data.db.get(HyperNetSetting, 1)
    assert setting.monthly_node_limit == 10 and setting.monthly_spend_limit == 100 and setting.preferred_market_hub == "amarr"


def test_migration_upgrade_defaults_and_downgrade():
    path = Path(__file__).parents[1] / "alembic/versions/0087_hypernet_pause.py"
    spec = importlib.util.spec_from_file_location("pause_migration", path)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE eve_characters (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE hypernet_settings (user_id INTEGER PRIMARY KEY, monthly_node_limit INTEGER)"))
        connection.execute(text("INSERT INTO hypernet_settings VALUES (1, 10)"))
        migration.op = Operations(MigrationContext.configure(connection)); migration.upgrade()
        assert connection.execute(text("SELECT paused, monthly_node_limit FROM hypernet_settings")).one() == (0, 10)
        assert "hypernet_character_pauses" in inspect(connection).get_table_names()
        migration.downgrade()
        assert "hypernet_character_pauses" not in inspect(connection).get_table_names()
        assert "paused" not in {c["name"] for c in inspect(connection).get_columns("hypernet_settings")}
    engine.dispose()
