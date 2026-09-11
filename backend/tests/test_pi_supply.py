from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api import planetary_industry as api
from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.enums import OwnerKind, LocationKind
from app.services import pi_supply


def asset(id, *, parent=None, location=None, flag="Cargo", quantity=1, owner_id=1, type_id=3645):
    return NS(id=id, ownership_entity=NS(id=owner_id, owner_kind=OwnerKind.CORPORATION, corporation_id=owner_id, display_name=f"Corp {owner_id}"),
              ownership_entity_id=owner_id, parent_asset_id=parent, location=location, location_flag=flag,
              quantity=quantity, type_id=type_id, last_synced_at=datetime(2026, 9, 11, tzinfo=timezone.utc))


def test_hangars_include_nested_containers_once_and_separate_owners_and_divisions():
    station = NS(id=7, name="Station", location_kind=LocationKind.STATION)
    structure = NS(id=8, name="Upwell", location_kind=LocationKind.STRUCTURE)
    rows = [asset(1, location=station, flag="CorpSAG1", type_id=999),
            asset(2, parent=1, quantity=40), asset(3, parent=2, quantity=10),
            asset(4, location=station, flag="CorpSAG2", quantity=20),
            asset(5, location=structure, flag="CorpSAG1", quantity=30),
            asset(6, location=station, flag="CorpSAG1", owner_id=2, quantity=50),
            asset(7, parent=999, quantity=1000), asset(8, parent=9), asset(9, parent=8)]
    groups={h["id"]:h for h in pi_supply.group_hangars(rows,{(1,"CorpSAG1"):"PI stock"})["hangars"]}
    assert len(groups)==21
    assert groups["1:7:CorpSAG1"]["items"]["3645"]==50
    assert groups["1:7:CorpSAG2"]["items"]["3645"]==20
    assert groups["1:8:CorpSAG1"]["items"]["3645"]==30
    assert groups["2:7:CorpSAG1"]["items"]["3645"]==50
    assert groups["1:7:CorpSAG7"]["items"]=={}
    assert groups["1:7:CorpSAG1"]["name"].endswith("PI stock")


def test_asset_permission_denial_never_reads_inventory(monkeypatch):
    monkeypatch.setattr(pi_supply,"can_view_section",lambda *a:False)
    monkeypatch.setattr(pi_supply,"visible_asset_rows",lambda *a:pytest.fail("Assets read without permission"))
    assert pi_supply.hangar_snapshot(NS(),NS())["hangars"]==[]


@pytest.fixture
def client(monkeypatch):
    app=FastAPI();app.include_router(api.router)
    recipe=NS(cycle_time=3600,output_quantity=5,inputs=[NS(type_id=1,quantity=40),NS(type_id=2,quantity=40)])
    app.dependency_overrides[get_current_user]=lambda:NS(id=1)
    app.dependency_overrides[get_db]=lambda:NS(get=lambda *a:recipe)
    monkeypatch.setattr(api,"require_planetary_view",lambda *a:None)
    binary=Path(__file__).parents[2]/"rust/eqm-core/target/release"/("eqm-core.exe" if __import__('os').name=='nt' else "eqm-core")
    if not binary.exists():pytest.skip("Build eqm-core --release for native API tests")
    monkeypatch.setattr(pi_supply,"get_settings",lambda:NS(eqm_core_binary=str(binary),eqm_core_timeout_seconds=5))
    with TestClient(app) as c:yield c


def test_calculator_uses_rust_and_validates_inputs(client):
    result=client.post("/planetary-industry/production-calculator",json={"schematic_id":1,"factories":3,"inventory":{"1":200,"2":300}})
    assert result.status_code==200,result.text
    assert result.json()["engine_used"]=="rust"
    assert result.json()["duration_seconds"]==7200
    assert result.json()["output_quantity"]==25
    for change in ({"factories":0},{"inventory":{"1":-1}},{"inventory":{"1":1.5}}):
        assert client.post("/planetary-industry/production-calculator",json={"schematic_id":1,**change}).status_code==422


def test_invisible_hangar_rejected_before_colony_read(client,monkeypatch):
    monkeypatch.setattr(api,"hangar_snapshot",lambda *a:{"hangars":[]})
    monkeypatch.setattr(api,"list_planetary_industry",lambda *a:pytest.fail("Should reject invisible hangar first"))
    assert client.get("/planetary-industry/supply-report?hangar_id=hidden").status_code==404


def test_pi_permission_required(client,monkeypatch):
    def denied(*args):raise HTTPException(403,"Denied")
    monkeypatch.setattr(api,"require_planetary_view",denied)
    assert client.get("/planetary-industry/inventory-hangars").status_code==403
    assert client.get("/planetary-industry/supply-report").status_code==403
    assert client.post("/planetary-industry/production-calculator",json={"schematic_id":1}).status_code==403


def test_missing_worker_is_explicit(client,monkeypatch):
    monkeypatch.setattr(pi_supply,"get_settings",lambda:NS(eqm_core_binary="missing-eqm-binary",eqm_core_timeout_seconds=1))
    result=client.post("/planetary-industry/production-calculator",json={"schematic_id":1})
    assert result.status_code==503


def test_report_uses_native_stock_and_surplus(client, monkeypatch):
    import json
    fixture=json.loads((Path(__file__).parents[2]/"frontend/tests/fixtures/planetary-shortage-input.v1.json").read_text())
    monkeypatch.setattr(api,"list_planetary_industry",lambda *a:fixture)
    monkeypatch.setattr(api,"hangar_snapshot",lambda *a:{"hangars":[{"id":"test","name":"PI stock","items":{"9832":720}}]})
    result=client.get("/planetary-industry/supply-report?hangar_id=test&target_type_id=2870")
    assert result.status_code==200,result.text
    report=result.json()
    assert report["engine_used"]=="rust"
    coolant=next(r for r in report["commodities"] if r["type_id"]==9832)
    assert coolant["runway_days_at_net_shortfall"]==2.666667
    assert coolant["net_shortfall_per_day"]==360
    assert next(r for r in report["commodities"] if r["type_id"]==2870)["net_surplus_per_day"]==24


def test_p4_from_shared_p2_follows_server_recipes(client, monkeypatch):
    def recipe(id, output, quantity, inputs):
        return NS(schematic_id=id, output_type_id=output, output_quantity=quantity, cycle_time=3600,
                  inputs=[NS(type_id=t, quantity=q) for t, q in inputs])
    catalog = [recipe(1, 10, 20, [(1, 3000)]), recipe(2, 20, 5, [(10, 40)]),
               recipe(3, 30, 3, [(20, 10)]), recipe(4, 31, 3, [(20, 10)]),
               recipe(5, 40, 1, [(30, 4), (31, 4), (10, 2)])]
    client.app.dependency_overrides[get_db] = lambda: NS(get=lambda *a: catalog[-1], scalars=lambda *a: NS(all=lambda: catalog))
    response = client.post("/planetary-industry/production-calculator", json={
        "schematic_id": 5, "feed_tier": 2, "inventory": {"20": 65, "10": 10}, "stage_factories": {"3": 2, "4": 2}})
    assert response.status_code == 200, response.text
    r = response.json()
    assert r["mode"] == "chain" and r["engine_used"] == "rust"
    assert r["output_quantity"] == 2 and r["duration_seconds"] == 14400
    assert r["pipeline_duration_seconds"] == 10800
    assert r["timing_method"] == "overlapping_cycles"
    assert [(tier["tier"], tier["product_count"]) for tier in r["tiers"]] == [(3, 2), (4, 1)]
    assert {s["type_id"]: s["produced"] for s in r["stages"]} == {30: 9, 31: 9, 40: 2}
    assert {i["type_id"]: i["remaining"] for i in r["ingredients"]} == {20: 5, 10: 6}
    for change in ({"feed_tier": 4}, {"stage_factories": {"3": 0}}, {"stage_factories": {"3": 10001}}):
        assert client.post("/planetary-industry/production-calculator", json={"schematic_id": 5, **change}).status_code == 422
