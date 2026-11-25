"""Synthetic UTC drill-down coverage; never connects to an EVE account or live DB."""
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api import mining_ledger
from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import Base, EsiToken, EveCharacter, EveSystem, EveType, MiningLedgerEntry, MiningOperation, User

DAY = date(2026, 11, 24)


def record(**changes):
    values = dict(mined_date=DAY, mined_at=None, source="esi", quantity=100, residue_quantity=25,
                  volume=1000, residue_volume=250, estimated_price=2000, estimated_residue_price=500,
                  has_residue_data=True, character_id=1, character=SimpleNamespace(name="Demo Aurora"),
                  ore_type_id=1, ore_type_name="Demo Ore", solar_system_id=1, solar_system_name="Demo System")
    return SimpleNamespace(**(values | changes))


def test_hours_preserve_totals_and_measurement_without_inventing_esi_times():
    entries = [record(source="import", mined_at=datetime(2026, 11, 24, 3, 12)),
               record(source="import", mined_at=datetime(2026, 11, 24, 5, tzinfo=timezone(timedelta(hours=2)))),
               record(mined_at=datetime(2026, 11, 24, 6)),
               record(source="import"),
               record(source="import", mined_at=datetime(2026, 11, 24, 0, tzinfo=timezone(timedelta(hours=2)))),
               record(has_residue_data=False, residue_volume=0, residue_quantity=0)]
    result = mining_ledger.hourly_rollup(entries, DAY)
    assert len(result["by_hour"]) == 24
    assert result["timestamped_rows"] == 2
    assert result["untimed_rows"] == 4
    assert result["by_hour"][3]["volume"] == 2000
    assert result["by_hour"][3]["efficiency"] == 80
    assert result["by_hour"][0]["volume"] == 0
    assert result["by_hour"][0]["efficiency"] is None
    totals = mining_ledger.rollup(entries)["totals"]
    for metric in ("quantity", "volume", "residue_volume", "estimated_price", "gross_volume", "measured_volume"):
        assert sum(row[metric] for row in result["by_hour"]) + result["untimed"][metric] == totals[metric]
    assert result["untimed"]["efficiency"] == 80  # unmeasured ESI volume is excluded


def test_empty_day_does_not_leak_other_dates():
    result = mining_ledger.hourly_rollup([record(mined_date=DAY - timedelta(days=1))], DAY)
    assert result["timestamped_rows"] == result["untimed_rows"] == 0
    assert all(row["volume"] == 0 for row in result["by_hour"])
    assert result["untimed"]["volume"] == 0


def make_demo_engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([User(id=1, email="demo@example.invalid", display_name="Demo", role="member"),
                    User(id=2, email="other@example.invalid", display_name="Other", role="member")])
        for cid, name, owner, opt_out in [(1, "Demo Aurora", 1, False), (2, "Demo Borealis", 1, False),
                                          (3, "Private Other", 2, False), (4, "Opted Out", 1, True),
                                          (5, "Revoked", 1, False)]:
            db.add(EveCharacter(id=cid, character_id=90000000 + cid, name=name, owner_user_id=owner, sync_opt_out=opt_out))
            db.add(EsiToken(user_id=owner, character_id=cid, scopes=mining_ledger.MINING_SCOPE,
                            encrypted_refresh_token="synthetic-unused", revoked_at=datetime.now(timezone.utc) if cid == 5 else None))
        db.add_all([EveSystem(system_id=i, name=f"Demo System {i}") for i in [1, 2]])
        db.add_all([EveType(type_id=i, name=f"Demo Ore {i:03d}") for i in range(1, 106)])
        db.add(MiningOperation(id=1, name="Demo Expedition", created_by_user_id=1,
                               start_at=datetime(2026, 11, 23), end_at=datetime(2026, 11, 25)))
        db.flush()

        def add(cid, ore, day=DAY, system=1, operation=1, source="import", hour=8):
            db.add(MiningLedgerEntry(character_id=cid, ore_type_id=ore, mined_date=day,
                mined_at=datetime.combine(day, datetime.min.time()).replace(hour=hour) if source == "import" else None,
                solar_system_id=system, operation_id=operation, ore_type_name=f"Demo Ore {ore:03d}",
                solar_system_name=f"Demo System {system}", quantity=100, volume=1000, residue_quantity=25 if source == "import" else 0,
                residue_volume=250 if source == "import" else 0, estimated_price=2000,
                estimated_residue_price=500 if source == "import" else 0, has_residue_data=source == "import",
                source=source, last_synced_at=datetime.now(timezone.utc)))
        for ore in range(1, 106):
            add(1, ore, hour=8 if ore <= 55 else 15, source="esi" if ore > 100 else "import")
        add(1, 1, DAY - timedelta(days=1), hour=20)
        add(2, 1, hour=11)
        add(2, 2, DAY - timedelta(days=1), source="esi")
        add(1, 1, system=2, operation=None, hour=18)
        for cid in [3, 4, 5]:
            add(cid, 1)
        db.commit()
    return engine


def demo_app(engine):
    app = FastAPI()
    app.include_router(mining_ledger.router, prefix="/api")

    def database():
        with Session(engine) as db:
            yield db

    def identity():
        with Session(engine) as db:
            return db.get(User, 1)

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user] = identity
    return app


@pytest.fixture
def client():
    engine = make_demo_engine()
    with TestClient(demo_app(engine)) as client:
        yield client
    engine.dispose()


def test_day_endpoint_filters_all_analytics_before_pagination_and_keeps_access_rules(client):
    scope = dict(date_from=str(DAY), date_to=str(DAY), character_id=90000001, system_id=1, operation_id=1, page_size=100)
    response = client.get("/api/mining-ledger", params=scope)
    assert response.status_code == 200
    data = response.json()
    assert data["entry_count"] == 105
    assert len(data["entries"]) == 100
    analytics = data["analytics"]
    assert analytics["totals"]["volume"] == 105000
    assert analytics["hourly"]["by_hour"][8]["volume"] == 55000
    assert analytics["hourly"]["by_hour"][15]["volume"] == 45000
    assert analytics["hourly"]["untimed"]["volume"] == 5000
    assert len(analytics["by_day"]) == len(analytics["by_character"]) == len(analytics["by_system"]) == 1
    assert len(analytics["by_ore"]) == 105
    second = client.get("/api/mining-ledger", params=scope | {"page": 2}).json()
    assert len(second["entries"]) == 5
    assert second["analytics"] == analytics
    all_data = client.get("/api/mining-ledger").json()
    assert all_data["entry_count"] == 109  # foreign, opted-out and revoked are excluded
    assert "hourly" not in all_data["analytics"]
    assert {row["name"] for row in all_data["analytics"]["by_character"]} == {"Demo Aurora", "Demo Borealis"}
    assert client.get("/api/mining-ledger", params=scope | {"character_id": 90000003}).json()["entry_count"] == 0


def test_empty_single_day_keeps_24_zero_buckets(client):
    data = client.get("/api/mining-ledger?date_from=2026-11-01&date_to=2026-11-01").json()
    assert data["entry_count"] == 0
    assert len(data["analytics"]["hourly"]["by_hour"]) == 24
    assert data["analytics"]["totals"]["volume"] == 0
