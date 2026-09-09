from __future__ import annotations

import asyncio
import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.pi_planner import PlanningRequest
from app.services.pi_catalog import command_capacity, make_catalog, pin_catalog
from app.services.pi_market import _CACHE, fetch_book, fill, quote
from app.services.pi_planner import evaluate, expand, operation_slots, recipe_report, run_planner, validate_plan
from app.services.pi_planning_context import restore_snapshot
from app.services.pi_templates import generate_template, inspect_template

SCHEMATICS = json.loads((Path(__file__).parent / "fixtures/pi-planner-catalog.v1.json").read_text())


def context():
    return {"catalog": make_catalog(SCHEMATICS), "pins": pin_catalog(), "pilots": [{"character_id": 1, "name": "Pilot", "ccu": 5, "ic": 5, "cce": 5, "colonies": []}], "baseline": {"colonies": 0}}


def request(**changes):
    planets = [{"key": str(i), "name": f"Planet {i}", "planet_type": "Storm", "security": 0, "customs_percent": 0, "npc_tax_percent": 0, "yields": [{"type_id": 2268, "units_per_head_hour": 10000}, {"type_id": 2309, "units_per_head_hour": 10000}]} for i in range(6)]
    value = {"products": [{"type_id": 3645, "quantity": 1000}], "planets": planets, "pilots": [{"character_id": 1, "planet_keys": [str(i) for i in range(6)]}], "sourcing": "extract", "costs": {"sales_tax_percent": 0, "setup_amortization_weeks": 520}, "search_seconds": 2}
    value.update(changes)
    return PlanningRequest.model_validate(value)


def market():
    now = datetime.now(timezone.utc)
    return {"hub": "jita", "fetched_at": now.isoformat(), "errors": {}, "books": {t: {"complete": True, "fetched_at": now.isoformat(), "expires_at": (now+timedelta(hours=1)).isoformat(), "bids": [{"price": [2, 600, 14000, 150000, 3000000][i["tier"]], "volume": 1000000000, "minimum": 1, "order_id": t}], "asks": [{"price": [3, 700, 16000, 170000, 3300000][i["tier"]], "volume": 1000000000, "minimum": 1, "order_id": t+100000}]} for t, i in context()["catalog"].items()}}


def test_catalog_ccp_data_and_capacities():
    c = context()
    assert len(c["catalog"]) == 83
    assert c["catalog"][3645]["tier"] == 1
    assert c["catalog"][2867]["tier"] == 4
    assert command_capacity(c["pins"], 5) == (25415, 19000)
    assert command_capacity(c["pins"], 0) == (1675, 6000)


def test_shared_recipe_demand_merges_before_rounding_and_uses_inventory_once():
    c = context()["catalog"]
    p = expand(c, {3645: 21, 9832: 5}, set(), -1, {3645: 20})  # Coolant also consumes Water.
    assert p["nodes"][3645]["batches"] == 3
    assert p["raw"][2268] == 9000
    assert p["inventory_used"][3645] == 20
    assert p["surplus"][3645] == 19


def test_recipe_inventory_does_not_report_free_recurring_production():
    c = context()["catalog"]
    p = recipe_report(c, {3645: 40}, {2268: 3000}, set())
    assert p["shopping"][2268] == 3000
    assert {"type_id": 3645, "quantity": 20} in p["buildable_direct"]


def test_cycle_rejected():
    broken = copy.deepcopy(SCHEMATICS[:1])
    broken[0]["inputs"] = [broken[0]["output"]]
    with pytest.raises(ValueError, match="Cyclic"):
        make_catalog(broken)


@pytest.mark.parametrize("volume", [None, 0, -1])
def test_incomplete_sde_volume_rejected(volume):
    broken=copy.deepcopy(SCHEMATICS)
    broken[0]["output"]["volume"]=volume
    with pytest.raises(ValueError,match="missing SDE volume"):
        make_catalog(broken)


def test_fractional_inventory_units_and_invalid_resource_yields_rejected():
    with pytest.raises(ValidationError):
        request(products=[{"type_id":3645,"quantity":.5}])
    r=request()
    r.planets[0].yields[0].type_id=3645
    with pytest.raises(ValueError,match="raw resource"):
        run_planner(r,context(),market())


def test_thin_book_never_extrapolates():
    assert fill([{"price": 1000, "volume": 1}], 44144, buying=False)["value"] == 1000
    assert fill([{"price": 1000, "volume": 1}], 44144, buying=False)["unfilled"] == 44143


def test_minimum_volume_and_remaining_minimum():
    orders = [{"price": 10, "volume": 100, "minimum": 50}]
    assert fill(orders, 49, buying=False)["filled"] == 0
    assert fill([{**orders[0], "volume": 20}], 20, buying=False)["value"] == 200


def test_patient_is_an_estimate_not_a_confirmed_fill():
    q = quote(market()["books"][3645], 1000000001, buying=False, patient=True)
    assert q["filled"] == 0 and q["status"] == "patient_estimate"
    assert q["unfilled"] == 1000000001


def test_pure_evaluate_conserves_materials():
    c, r, m = context(), request(), market()
    p = evaluate(r, c, m, {3645: 20000}, -1)
    assert p["feasible"], p["reason"]
    assert validate_plan(c["catalog"], r, c, p) == []
    p["colonies"][0]["extraction"] = {}
    assert "Operation has an unfunded material deficit" in validate_plan(c["catalog"], r, c, p)


def test_locked_colonies_reserve_all_slots():
    c, r = context(), request()
    c["pilots"][0]["colonies"] = [{"id": i+1, "planet_id": 100+i, "upgrade_level": 5} for i in range(6)]
    assert not evaluate(r,c,market(),{3645:20},-1)["feasible"]
    r.pilots[0].release_colony_ids = [1]
    assert evaluate(r,c,market(),{3645:20},-1)["feasible"]


def test_other_pilot_colony_cannot_be_released():
    r = request()
    r.pilots[0].release_colony_ids = [999]
    with pytest.raises(ValueError, match="does not belong"):
        operation_slots(r,context())


def test_unknown_skills_not_assumed_five():
    c = context()
    c["pilots"][0]["ccu"] = None
    r = request()
    assert not evaluate(r,c,market(),{3645:20},-1)["feasible"]
    r.pilots[0].planned_ccu = 5
    assert evaluate(r,c,market(),{3645:20},-1)["feasible"]


def test_duplicate_real_planet_not_allocated_twice():
    c, r = context(), request()
    for p in r.planets:
        p.planet_id = 123
    plan = evaluate(r,c,market(),{3645:100000},-1)
    assert not plan["feasible"]


def test_storage_and_haul_limits_are_enforced():
    r = request()
    r.schedule.haul_capacity_m3 = 1
    r.schedule.max_trips_per_visit = 1
    p = evaluate(r,context(),market(),{3645:20000},-1)
    assert not p["feasible"] and "Hauling" in p["reason"]


def test_setup_budget_enforced():
    r = request()
    r.costs.setup_budget = 1
    assert "Setup" in evaluate(r,context(),market(),{3645:20},-1)["reason"]


def test_missing_input_quote_is_infeasible_not_zero_cost():
    c, r, m = context(), request(sourcing="buy_raw"), market()
    m["books"].pop(2268)
    p = evaluate(r,c,m,{3645:20},0)
    assert not p["feasible"] and "input units" in p["reason"]


def test_input_depth_is_shared_across_mixed_products():
    c, r, m = context(), request(), market()
    # Water and Industrial Fibers use different raw; Water + Coolant share Water.
    p = evaluate(r,c,m,{3645:21,9832:5},1)
    assert p["feasible"], p["reason"]
    assert p["purchases"].get(3645,0) == 0  # Requested product is made, including intermediate demand.
    assert validate_plan(c["catalog"],r,c,p) == []


def test_profit_can_choose_a_smaller_operation():
    c,r,m=context(),request(),market()
    r.costs.per_colony_weekly = 1000000
    m["books"][3645]["bids"] = [{"price":1000,"volume":40000,"minimum":1,"order_id":1},{"price":1,"volume":10000000,"minimum":1,"order_id":2}]
    result=run_planner(r,c,m)
    best=result["plans"][0]
    assert not best.get("idle"), result
    larger=evaluate(r,c,m,{3645:120000},-1)
    assert larger["feasible"],larger["reason"]
    assert best["economics"]["net_after_setup_amortization"] > larger["economics"]["net_after_setup_amortization"]
    assert len(best["colonies"]) < len(larger["colonies"])


def test_profit_retains_idle_baseline():
    r=request();r.costs.weekly_overhead=1e12
    assert run_planner(r,context(),market())["plans"][0]["idle"]


def test_cancel_retains_completed_candidates():
    calls=[0]
    def cancelled():
        calls[0]+=1
        return calls[0]>30
    result=run_planner(request(),context(),market(),cancelled=cancelled)
    assert result["search"]["cancelled"]


def test_frozen_json_snapshot_replays_numeric_keys():
    value=json.loads(json.dumps({"context":context(),"market":market()}))
    c,m=restore_snapshot(value)
    first=evaluate(request(),context(),m,{3645:1000},-1)
    second=evaluate(request(),c,m,{3645:1000},-1)
    assert first==second


def test_template_native_roundtrip_and_dangling_routes():
    c=context();p=evaluate(request(),c,market(),{3645:20000},-1)
    template=generate_template(p["colonies"][0],c["catalog"],c["pins"])
    checked=inspect_template(json.dumps(template["template"]),c["catalog"],c["pins"])
    assert checked["template"] == template["template"]
    data=copy.deepcopy(template["template"])
    data["L"]=[]
    with pytest.raises(ValueError,match="missing link"):
        inspect_template(json.dumps(data),c["catalog"],c["pins"])


@pytest.mark.parametrize("patch", [{"search_seconds":float('nan')},{"products":[{"type_id":3645,"quantity":float('inf')}]},{"pilots":[{"character_id":1,"planned_ic":6}]},{"arbitrary_price":123}])
def test_request_bounds(patch):
    with pytest.raises(ValidationError):
        request(**patch)


class FakeEsi:
    def __init__(self,pages):self.pages=pages;self.calls=0
    async def get_with_headers(self,path,params):
        self.calls+=1
        return self.pages[params["page"]-1]


def order(i, location=60003760):
    return {"order_id":i,"location_id":location,"type_id":3645,"price":100,"volume_remain":20,"min_volume":1,"is_buy_order":True}


def test_esi_pages_scope_and_cache():
    _CACHE.clear()
    fake=FakeEsi([([order(1),order(2,123)],{"X-Pages":"2"}),([order(3)],{"X-Pages":"2"})])
    book=asyncio.run(fetch_book(fake,"jita",3645))
    assert len(book["bids"])==2 and fake.calls==2
    assert asyncio.run(fetch_book(fake,"jita",3645))==book and fake.calls==2


@pytest.mark.parametrize("pages", [[([order(1)],{"X-Pages":"2"}),([],{"X-Pages":"2"})],[([order(1)],{"X-Pages":"2"}),([order(2)],{"X-Pages":"3"})],[([order(1)],{"X-Pages":"2"}),([order(1)],{"X-Pages":"2"})]])
def test_incomplete_or_inconsistent_esi_pages_rejected(pages):
    _CACHE.clear()
    with pytest.raises(ValueError):
        asyncio.run(fetch_book(FakeEsi(pages),"jita",3645))
    assert not _CACHE
