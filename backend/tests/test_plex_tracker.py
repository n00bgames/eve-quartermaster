import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api import plex
from app.db.session import get_db
from app.models import Base, User
from app.models.plex import PlexMarketCache, PlexTransaction
from app.schemas.plex import PlexTransactionInput
from app.services.plex import ledger, market_data, summarize_orders

NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)


def trade(id, kind, qty, price=None, fees=0):
    return SimpleNamespace(id=id, kind=kind, quantity=qty, unit_price=Decimal(str(price)) if price is not None else None,
                           fees=Decimal(str(fees)), occurred_at=NOW + timedelta(days=id), note="")


def test_fifo_fees_partial_sales_and_consumption():
    result = ledger([trade(1, "buy", 100, 4000000, 1000000), trade(2, "buy", 50, 5000000),
                     trade(3, "sell", 120, 6000000, 12000000), trade(4, "consume", 10)])
    assert result["quantity"] == 20
    assert result["cost_basis"] == 100000000
    assert result["realized_profit"] == 207000000  # 720m - 12m fees - 501m FIFO cost
    assert result["consumed_quantity"] == 10
    assert result["trade_cash_flow"] == 57000000


def test_unknown_cost_never_becomes_zero_and_clears_when_consumed():
    rows = [trade(1, "opening", 101), trade(2, "buy", 1099, 289300)]
    result = ledger(rows)
    assert result["cost_basis"] is None
    assert result["unknown_cost_quantity"] == 101
    assert result["known_cost_basis"] == 317940700
    result = ledger(rows + [trade(3, "sell", 101, 300000)])
    assert result["cost_basis"] == 317940700
    assert result["unknown_cost_sales"] == 1
    assert result["realized_profit"] is None
    assert result["transactions"][0]["cost_basis"] is None


def test_zero_basis_is_explicit_and_opening_is_not_new_cash_spend():
    result = ledger([trade(1, "opening", 10, 0), trade(2, "sell", 10, 500, 50)])
    assert result["realized_profit"] == 4950
    assert result["cost_basis"] == 0
    assert result["trade_cash_flow"] == 4950


def test_chronology_rejects_oversell_even_if_later_purchase_covers_it():
    with pytest.raises(ValueError, match="at that date"):
        ledger([trade(2, "buy", 100, 5), trade(1, "sell", 10, 6)])


@pytest.mark.parametrize("changes", [{"quantity": 1.5}, {"quantity": True}, {"quantity": 0}, {"unit_price": "NaN"},
                                   {"unit_price": None}, {"unit_price": 0}, {"fees": -1}, {"fees": "0.001"},
                                   {"occurred_at": datetime.now(timezone.utc) + timedelta(days=1)},
                                   {"occurred_at": "2025-01-01T12:00:00"}, {"kind": "consume", "unit_price": 1}])
def test_input_rejects_invalid_transactions(changes):
    with pytest.raises(ValidationError):
        PlexTransactionInput(**{"occurred_at": NOW, "kind": "buy", "quantity": 5, "unit_price": 4, **changes})


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[User.__table__, PlexTransaction.__table__, PlexMarketCache.__table__])
    with Session(engine) as session:
        session.add_all([User(id=1, email="one@example.test", display_name="One", role="member"),
                         User(id=2, email="two@example.test", display_name="Two", role="admin")])
        session.commit()
        yield session
    engine.dispose()


@pytest.fixture
def client(db):
    app = FastAPI()
    app.include_router(plex.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[plex.require_plex] = lambda: db.get(User, 1)
    with patch.object(plex, "record_audit_event"), TestClient(app) as test_client:
        yield test_client


def payload(kind="buy", quantity=100, day=1):
    return {"kind": kind, "quantity": quantity, "unit_price": "4000000", "fees": "1000", "occurred_at": (NOW + timedelta(days=day)).isoformat(), "note": "test"}


def test_api_create_edit_delete_and_reject_breaking_inventory(client):
    response = client.post("/plex/transactions", json=payload())
    assert response.status_code == 200
    id = response.json()["transactions"][0]["id"]
    response = client.post("/plex/transactions", json=payload("sell", 60, 2))
    assert response.status_code == 200
    assert response.json()["quantity"] == 40
    assert client.delete(f"/plex/transactions/{id}").status_code == 400
    assert client.put(f"/plex/transactions/{id}", json=payload(quantity=50)).status_code == 400
    assert client.get("/plex/ledger").json()["quantity"] == 40
    updated = client.put(f"/plex/transactions/{id}", json=payload(quantity=200))
    assert updated.json()["quantity"] == 140
    sale = updated.json()["transactions"][0]["id"]
    assert client.delete(f"/plex/transactions/{sale}").json()["quantity"] == 200
    assert client.delete(f"/plex/transactions/{id}").json()["quantity"] == 0


def test_owner_isolation_even_for_admin_records(client, db):
    foreign = PlexTransaction(owner_user_id=2, occurred_at=NOW, kind="buy", quantity=500, unit_price=4000000, fees=0, note="private")
    db.add(foreign); db.commit()
    assert client.get("/plex/ledger").json()["transactions"] == []
    assert client.put(f"/plex/transactions/{foreign.id}", json=payload()).status_code == 404
    assert client.delete(f"/plex/transactions/{foreign.id}").status_code == 404
    assert db.get(PlexTransaction, foreign.id).quantity == 500


def test_permission_denial(db):
    with patch.object(plex, "can_view_section", return_value=False), pytest.raises(HTTPException) as exc:
        plex.require_plex(db.get(User, 1), db)
    assert exc.value.status_code == 403


def test_market_correct_side_volume_and_empty_book():
    orders = [{"type_id": 44992, "is_buy_order": buy, "price": price, "volume_remain": qty}
              for buy, price, qty in [(True, 4, 5), (True, 4.5, 8), (False, 5, 4), (False, 6, 10), (False, 1, 0)]]
    summary = summarize_orders(orders)
    assert summary["best_bid"] == 4.5 and summary["best_ask"] == 5
    assert summary["spread"] == .5 and summary["best_bid_volume"] == 8
    assert summarize_orders([])["best_ask"] is None


def test_market_client_collects_all_pages_before_choosing_quote(db):
    from app.services.esi_client import EsiClient
    pages = [([{"type_id": 44992, "is_buy_order": False, "price": 6, "volume_remain": 10}], {"X-Pages": "2"}),
             ([{"type_id": 44992, "is_buy_order": False, "price": 5, "volume_remain": 20}], {"X-Pages": "2"})]
    with patch.object(EsiClient, "get_with_headers", new_callable=AsyncMock, side_effect=pages) as fetch:
        result = asyncio.run(market_data(db))
        assert result["best_ask"] == 5
        assert result["sell_volume"] == 30
        assert fetch.await_args_list[1].kwargs["params"]["page"] == 2


def test_large_valid_values_do_not_overflow_decimal_reporting():
    result = ledger([trade(1, "buy", 1_000_000_000, "999999999999999999.99")])
    assert result["cost_basis"] > 0


def test_global_market_cache_and_stale_fallback(db):
    with patch("app.services.plex.EsiClient") as cls:
        client = cls.return_value
        client.close = AsyncMock()
        client.get_public_market_orders = AsyncMock(return_value=[{"type_id": 44992, "is_buy_order": False, "price": 5, "volume_remain": 10}])
        result = asyncio.run(market_data(db))
        assert result["best_ask"] == 5 and not result["stale"]
        client.get_public_market_orders.assert_awaited_once_with(19000001, 44992)
        assert asyncio.run(market_data(db))["fetched_at"] == result["fetched_at"]
        assert client.get_public_market_orders.await_count == 1
        cached = db.get(PlexMarketCache, "orders")
        cached.fetched_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.commit()
        client.get_public_market_orders.side_effect = httpx.ConnectError("offline")
        stale = asyncio.run(market_data(db))
        assert stale["stale"] and stale["best_ask"] == 5
        assert stale["fetched_at"] != result["fetched_at"]


def test_market_failure_without_cache_is_unavailable(db):
    with patch("app.services.plex.EsiClient") as cls:
        cls.return_value.close = AsyncMock()
        cls.return_value.get_public_market_orders = AsyncMock(side_effect=HTTPException(429, "throttle"))
        with pytest.raises(HTTPException) as exc:
            asyncio.run(market_data(db))
        assert exc.value.status_code == 503


def test_history_uses_global_region_and_sorts(db):
    with patch("app.services.plex.EsiClient") as cls:
        cls.return_value.close = AsyncMock()
        cls.return_value.get = AsyncMock(return_value=[{"date": "2025-01-03", "average": 5}, {"date": "2025-01-01", "average": 4}])
        result = asyncio.run(market_data(db, "history"))
        assert result["history"][0]["date"] == "2025-01-01"
        cls.return_value.get.assert_awaited_once_with("/markets/19000001/history/", params={"type_id": 44992})


def test_migration_roundtrip():
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect
    path = Path(__file__).parents[1] / "alembic/versions/0083_plex_tracker.py"
    spec = importlib.util.spec_from_file_location("plex_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        User.__table__.create(connection)
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            assert {"plex_transactions", "plex_market_cache"}.issubset(inspect(connection).get_table_names())
            assert len(inspect(connection).get_indexes("plex_transactions")) == 2
            migration.downgrade()
            assert inspect(connection).get_table_names() == ["users"]
    engine.dispose()
