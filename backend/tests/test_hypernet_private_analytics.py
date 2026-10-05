from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
import importlib.util

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api import hypernet_analytics as analytics
from app.api.hypernet import require_hypernet
from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import Base, EveCharacter, EveType, EveGroup, EveCategory, HyperNetAnalyticsPreference, HyperNetOffer, HyperNetParticipation, User


@pytest.fixture
def data():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[model.__table__ for model in (
        User, EveCharacter, EveCategory, EveGroup, EveType, HyperNetOffer, HyperNetParticipation, HyperNetAnalyticsPreference,
    )])
    db = Session(engine, expire_on_commit=False)
    db.add_all([EveCharacter(id=i, character_id=9000+i, name=f"Pilot {i}", owner_user_id=1 if i != 3 else 2) for i in range(1, 5)])
    db.add_all([EveCategory(category_id=6, name="Ships"), EveCategory(category_id=7, name="Modules"),
                EveGroup(group_id=1, category_id=6, name="Battleships"), EveGroup(group_id=2, category_id=7, name="Modules"),
                EveType(type_id=10, group_id=1, name="Barghest"), EveType(type_id=11, group_id=2, name="Cloak")])
    now = datetime.now(timezone.utc)
    for char, owner in [(1, 1), (2, 1), (3, 2)]:
        for outcome, amount, item in [("won", 10, 10), ("lost", 20, 10), ("pending", 30, 11), ("expired", 40, 11)]:
            db.add(HyperNetParticipation(user_id=owner, character_id=char, item_type_id=item,
                seller_name="Seller", total_nodes=8, nodes_purchased=1, node_price=amount,
                total_spent=amount, outcome=outcome, item_value_at_completion=100 if outcome == "won" else None,
                profit_loss=90 if outcome == "won" else -20 if outcome == "lost" else 0,
                created_at=now-timedelta(days=5000), completed_at=now if outcome != "pending" else None))
        db.add(HyperNetOffer(owner_user_id=owner, seller_character_id=char, type_id=10,
            quantity=3, status="completed", winner="seller", total_offer_price=200,
            expires_at=now, total_nodes=16, seller_owned_nodes=4, nodes_sold=16, final_profit=Decimal("35.25"),
            completed_at=now, created_offer_at=now-timedelta(days=5000)))
        db.add(HyperNetOffer(owner_user_id=owner, seller_character_id=char, type_id=11,
            quantity=2, status="completed", winner="external", total_offer_price=100,
            expires_at=now, total_nodes=16, seller_owned_nodes=4, nodes_sold=16, final_profit=-10,
            completed_at=now, created_offer_at=now))
        db.add(HyperNetOffer(owner_user_id=owner, seller_character_id=char, type_id=11,
            status="draft", expires_at=now, total_offer_price=999, total_nodes=16, created_offer_at=now))
    db.commit()
    user = SimpleNamespace(id=1, role="admin")
    app = FastAPI()
    app.include_router(analytics.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_hypernet] = lambda: user
    with TestClient(app) as client:
        yield client, db, user
    db.close()
    engine.dispose()


def enable(client, char=None, enabled=True):
    return client.patch("/hypernet/analytics/preferences", json={"enabled": enabled, **({"character_id": char} if char else {})})


def test_default_opt_out_and_independent_character_consent(data):
    client, db, user = data
    preferences = client.get("/hypernet/analytics/preferences")
    assert all(not row["enabled"] for row in preferences.json()["characters"])
    assert len(preferences.json()["characters"]) == 3
    assert client.get("/hypernet/analytics").json() is None
    assert "no-store" in preferences.headers["cache-control"]
    assert enable(client, 1).status_code == 200
    assert db.get(HyperNetAnalyticsPreference, (1, 1)).enabled
    result = client.get("/hypernet/analytics?days=0").json()
    assert [row["id"] for row in result["characters"]] == [1]
    assert result["buying"]["wins"] == result["buying"]["losses"] == 1
    assert result["buying"]["resolved_spend"] == 30
    assert result["buying"]["refunded_spend"] == 40
    assert result["buying"]["pending_spend"] == 30
    assert result["buying"]["recorded_result"] == 70
    assert result["buying"]["roi"] == pytest.approx(70/30*100)
    assert result["buying"]["expected_wins"] == .25
    assert result["selling"]["retained"] == 3
    assert result["selling"]["lost"] == 2
    assert result["selling"]["recorded_result"] == 25.25
    assert result["selling"]["seeded_spend"] == 75
    assert result["selling"]["records"] == 2  # draft excluded
    assert result["items"][0]["is_ship"] is True
    assert result["items"][1]["is_ship"] is False
    assert len(result["monthly_results"]) == 1
    assert client.get("/hypernet/analytics?days=0&character_id=2").json() is None
    enable(client, 1, False)
    assert client.get("/hypernet/analytics?days=0").json() is None


def test_bulk_control_is_private_and_future_characters_start_disabled(data):
    client, db, user = data
    enable(client)
    assert client.get("/hypernet/analytics?days=0").json()["buying"]["wins"] == 2
    db.add(EveCharacter(id=5, character_id=9005, name="New pilot", owner_user_id=1))
    db.commit()
    assert next(row for row in client.get("/hypernet/analytics/preferences").json()["characters"] if row["id"] == 5)["enabled"] is False
    assert enable(client, 3).status_code == 404
    assert client.get("/hypernet/analytics?character_id=3").json() is None
    user.id = 2  # staff role does not confer access to account 1's data or settings
    assert client.get("/hypernet/analytics?days=0").json() is None
    assert client.get("/hypernet/analytics/preferences").json()["characters"] == [{"id": 3, "name": "Pilot 3", "enabled": False}]
    enable(client, 3)
    assert client.get("/hypernet/analytics?days=0").json()["buying"]["wins"] == 1
    user.id = 1
    enable(client, enabled=False)
    assert client.get("/hypernet/analytics?days=0").json() is None
    assert db.get(HyperNetAnalyticsPreference, (2, 3)).enabled is True


def test_empty_character_and_periods_do_not_produce_datasets(data):
    client, db, user = data
    enable(client, 4)
    assert client.get("/hypernet/analytics?days=0").json() is None
    enable(client, 1)
    recent = client.get("/hypernet/analytics?days=7").json()
    assert recent["buying"]["wins"] == 1  # resolution date, not entry date
    assert recent["buying"]["pending"] == 0
    assert client.get("/hypernet/analytics?days=0").json()["buying"]["pending"] == 1
    assert [row["id"] for row in recent["characters"]] == [1]  # no blank pilot 4
    assert client.get("/hypernet/analytics?days=-1").status_code == 422
    assert client.get("/hypernet/analytics?days=3661").status_code == 422
    assert client.patch("/hypernet/analytics/preferences", json={"enabled": "false"}).status_code == 422


def test_access_permission_and_authentication_are_required(data):
    client, db, user = data
    client.app.dependency_overrides.pop(require_hypernet)
    for path in ["/hypernet/analytics", "/hypernet/analytics/preferences"]:
        assert client.get(path).status_code == 401
    client.app.dependency_overrides[get_current_user] = lambda: user
    with patch("app.api.hypernet.can_view_section", return_value=False):
        assert client.get("/hypernet/analytics").status_code == 403
        assert client.get("/hypernet/analytics/preferences").status_code == 403
        assert enable(client, 1).status_code == 403


def test_reconciliation_changes_and_market_dispositions_are_not_double_counted(data):
    client, db, user = data
    enable(client, 1)
    offer = db.query(HyperNetOffer).filter_by(owner_user_id=1, seller_character_id=1, type_id=10, status="completed").one()
    offer.winner = "external"
    bid = db.query(HyperNetParticipation).filter_by(user_id=1, character_id=1, outcome="won").one()
    bid.outcome = "lost"
    bid.profit_loss = -bid.total_spent
    sale = HyperNetOffer(owner_user_id=1, seller_character_id=1, type_id=11, status="expired",
        expires_at=datetime.now(timezone.utc), created_offer_at=datetime.now(timezone.utc),
        total_offer_price=100, total_nodes=16, acquisition_cost=1, hypercores_required=2,
        hypercore_unit_cost=3, final_profit=9999,
        market_sale={"gross_proceeds": "100", "sales_tax": "5", "broker_fee": "2", "other_fees": "0",
                     "sold_at": datetime.now(timezone.utc).isoformat()})
    db.add(sale)
    db.commit()
    result = client.get("/hypernet/analytics?days=0").json()
    assert result["buying"]["wins"] == 0
    assert result["buying"]["losses"] == 2
    assert result["buying"]["recorded_result"] == -30
    assert result["selling"]["retained"] == 0
    assert result["selling"]["lost"] == 5
    assert result["selling"]["recorded_result"] == 25.25 + 86  # sale replaces the old result


def test_migration_preserves_history_and_defaults_disabled():
    path = Path(__file__).parents[1] / "alembic/versions/0086_hypernet_private_analytics.py"
    spec = importlib.util.spec_from_file_location("migration86", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE eve_characters (id INTEGER PRIMARY KEY)"))
        module.op = Operations(MigrationContext.configure(connection))
        module.upgrade()
        connection.execute(text("INSERT INTO hypernet_analytics_preferences (user_id,character_id) VALUES (1,1)"))
        assert connection.execute(text("SELECT enabled FROM hypernet_analytics_preferences")).scalar() == 0
        module.downgrade()
        assert "hypernet_analytics_preferences" not in inspect(connection).get_table_names()
    engine.dispose()
