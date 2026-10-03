from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api import hypernet
from app.models import Base, EveType, EveCharacter, Location, HyperNetOffer, HyperNetParticipant, HyperNetOfferSnapshot, HyperNetParticipation
from app.schemas.hypernet import HyperNetMarketSaleInput, HyperNetReconcileRequest


@pytest.fixture
def fixture():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[r.__table__ for r in (EveType, EveCharacter, Location, HyperNetOffer, HyperNetParticipant, HyperNetOfferSnapshot, HyperNetParticipation)])
    db = Session(engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    offer = HyperNetOffer(owner_user_id=1, seller_character_id=1, type_id=1, status="expired",
        created_offer_at=now - timedelta(days=3), expires_at=now - timedelta(hours=1), reconciled_at=now - timedelta(hours=1),
        total_offer_price=1430000000, total_nodes=16, nodes_sold=8, seller_owned_nodes=8, unique_participants=1,
        acquisition_cost=Decimal("800000000"), hypercores_required=100, hypercore_unit_cost=Decimal("430000"),
        actual_hypercore_cost=Decimal("43000000"), final_profit=Decimal("-43000000"), item_outcome="retained")
    db.add(offer); db.commit()
    audit = Mock()
    with patch.object(hypernet, "offer_options", lambda: ()), patch.object(hypernet, "record_audit_event", audit):
        yield SimpleNamespace(db=db, offer=offer, now=now, user=SimpleNamespace(id=1), audit=audit)
    db.close(); engine.dispose()


def sale(f, **changes):
    return HyperNetMarketSaleInput(**{"sold_at": f.now - timedelta(minutes=30), "gross_proceeds": "856600000", "sales_tax": "64245000", **changes})


def save(f, **changes):
    return hypernet.record_hypernet_market_sale(f.offer.id, sale(f, **changes), f.user, f.db)


def summary(f, character_id=None, user=None):
    return hypernet.hypernet_summary(character_id=character_id, user=user or f.user, db=f.db)


def test_vindicator_sale_fees_and_costs_are_counted_once(fixture):
    f = fixture
    result = save(f)
    assert result["market_sale"]["net_proceeds"] == 792355000
    assert result["market_sale"]["lifecycle_profit"] == -50645000
    assert result["final_profit"] == -43000000
    assert result["status"] == "expired" and result["item_outcome"] == "market_sold"
    assert result["nodes_sold"] == result["seller_owned_nodes"] == 8
    assert f.offer.market_sale["gross_proceeds"] == "856600000"
    f.db.expire(f.offer, ["market_sale"])
    assert f.offer.market_sale["sales_tax"] == "64245000"
    stats = summary(f)
    assert stats["lifetime_profit"] == stats["combined_lifetime_result"] == -50645000
    assert stats["expired_offers"] == 1 and stats["completed_offers"] == 0
    assert stats["market_sold_items"] == 1
    assert f.audit.call_args.kwargs["event_kind"] == "hypernet_market_sale_saved"


def test_edit_replaces_sale_and_remove_restores_expired_result(fixture):
    f = fixture
    save(f)
    result = save(f, sales_tax=0, broker_fee=1000, other_fees=2000)
    assert result["market_sale"]["net_proceeds"] == 856597000
    assert summary(f)["market_sold_items"] == 1
    removed = hypernet.remove_hypernet_market_sale(f.offer.id, f.user, f.db)
    assert removed["market_sale"] is None and removed["item_outcome"] == "retained"
    assert summary(f)["lifetime_profit"] == -43000000
    assert summary(f)["market_sold_items"] == 0


def test_cost_corrections_recalculate_lifecycle_and_keep_sale(fixture):
    f = fixture
    save(f)
    payload = HyperNetReconcileRequest(status="expired", reconciled_at=f.offer.reconciled_at,
        acquisition_cost=750000000, actual_hypercore_cost=40000000, final_profit=0)
    result = hypernet.edit_hypernet_reconciliation(f.offer.id, payload, f.user, f.db)
    assert result["final_profit"] == 0
    assert result["market_sale"]["lifecycle_profit"] == 2355000
    assert result["item_outcome"] == "market_sold"
    assert summary(f)["lifetime_profit"] == 2355000


def test_dates_validate_before_mutation_and_preserve_existing_sale(fixture):
    f = fixture
    save(f)
    original = f.offer.market_sale.copy()
    for date in [f.now + timedelta(days=1), f.offer.reconciled_at - timedelta(seconds=1)]:
        with pytest.raises(HTTPException) as exc:
            save(f, sold_at=date, gross_proceeds=1)
        assert exc.value.status_code == 400
        assert f.offer.market_sale == original
    with pytest.raises(HTTPException) as exc:
        hypernet.edit_hypernet_reconciliation(f.offer.id,
            HyperNetReconcileRequest(status="expired", reconciled_at=f.now, acquisition_cost=1), f.user, f.db)
    assert exc.value.status_code == 400
    assert f.offer.acquisition_cost == 800000000


@pytest.mark.parametrize("status", ["active", "draft", "completed", "cancelled", "invalid", "awaiting_reconciliation"])
def test_only_expired_items_can_be_disposed(fixture, status):
    f = fixture; f.offer.status = status
    with pytest.raises(HTTPException) as exc:
        save(f)
    assert exc.value.status_code == 409
    with pytest.raises(HTTPException):
        hypernet.remove_hypernet_market_sale(f.offer.id, f.user, f.db)
    assert f.offer.market_sale is None
    f.audit.assert_not_called()


def test_owner_and_character_isolation(fixture):
    f = fixture
    for operation in [lambda: hypernet.record_hypernet_market_sale(f.offer.id, sale(f), SimpleNamespace(id=2), f.db),
                      lambda: hypernet.remove_hypernet_market_sale(f.offer.id, SimpleNamespace(id=2), f.db)]:
        with pytest.raises(HTTPException) as exc:
            operation()
        assert exc.value.status_code == 404
    save(f)
    assert summary(f, character_id=1)["market_sold_items"] == 1
    assert summary(f, character_id=2)["lifetime_profit"] == 0
    assert summary(f, user=SimpleNamespace(id=2))["market_sold_items"] == 0
    assert summary(f, user=SimpleNamespace(id=2))["combined_lifetime_result"] == 0


@pytest.mark.parametrize("changes", [{"gross_proceeds": -1}, {"sales_tax": -1}, {"broker_fee": -1},
    {"other_fees": -1}, {"gross_proceeds": "NaN"}, {"sales_tax": "1.001"}, {"sold_at": "2026-01-01T00:00:00"}, {"owner_user_id": 2}])
def test_invalid_inputs(changes):
    with pytest.raises(ValidationError):
        HyperNetMarketSaleInput(**{"sold_at": datetime.now(timezone.utc), "gross_proceeds": 1, **changes})


def test_zero_sale_and_high_fees_are_explicit_losses(fixture):
    result = save(fixture, gross_proceeds=0, sales_tax=0, broker_fee=10)
    assert result["market_sale"]["net_proceeds"] == -10
    assert result["market_sale"]["lifecycle_profit"] == -843000010


def test_migration_roundtrip_preserves_existing_offers():
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import text, inspect
    path = Path(__file__).parents[1] / "alembic/versions/0084_hypernet_market_sale.py"
    spec = importlib.util.spec_from_file_location("market_sale_migration", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE hypernet_offers (id INTEGER PRIMARY KEY, status TEXT)"))
        connection.execute(text("INSERT INTO hypernet_offers VALUES (1, 'expired')"))
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            assert connection.execute(text("SELECT market_sale FROM hypernet_offers")).scalar() is None
            module.downgrade()
            assert len(inspect(connection).get_columns("hypernet_offers")) == 2
            assert connection.execute(text("SELECT status FROM hypernet_offers")).scalar() == "expired"
    engine.dispose()
