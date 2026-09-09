"""Independent EQM operation planner. Pure calculation over frozen input snapshots.

Searches production scale and sourcing cuts. Colony packing is deliberately bounded
and reports best-found results, not a proof of global optimality or an in-game layout.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from collections import Counter
from typing import Callable

from app.schemas.pi_planner import PlanningRequest
from app.services.pi_catalog import CC_UPGRADE_COST, command_capacity, facility
from app.services.pi_market import quote

WEEK_HOURS = 168


def batches(quantity: float, size: float) -> int:
    return max(0, math.ceil(quantity / size - 1e-9))


def expand(catalog: dict, targets: dict[int, float], buy: set[int], cut: int, inventory: dict | None = None) -> dict:
    """Topological expansion merges shared ingredients before rounding whole batches."""
    demand = Counter(targets)
    stock = Counter(inventory or {})
    nodes, purchases, raw, surplus, used = {}, {}, {}, {}, {}
    for type_id in sorted(catalog, key=lambda t: (-catalog[t]["tier"], t)):
        need = demand[type_id]
        if need <= 0:
            continue
        consumed = min(need, stock[type_id])
        need -= consumed
        used[type_id] = consumed
        item = catalog[type_id]
        if need <= 0:
            continue
        if type_id not in targets and (type_id in buy or item["tier"] <= cut):
            purchases[type_id] = need
        elif not item["recipe"]:
            raw[type_id] = need
        else:
            recipe = item["recipe"]
            runs = batches(need, recipe["output"]["quantity"])
            made = runs * recipe["output"]["quantity"]
            nodes[type_id] = {"type_id": type_id, "batches": runs, "quantity": made, "required": need}
            surplus[type_id] = made - need
            for part in recipe["inputs"]:
                demand[part["type_id"]] += part["quantity"] * runs
    return {"nodes": nodes, "purchases": purchases, "raw": raw, "surplus": surplus, "inventory_used": used, "demand": dict(demand)}


def recipe_report(catalog: dict, targets: dict, inventory: dict, buy: set[int]) -> dict:
    if set(targets) - set(catalog) or set(inventory) - set(catalog) or buy - set(catalog):
        raise ValueError("Unknown PI commodity")
    plan = expand(catalog, targets, buy, -1, inventory)
    plan["shopping"] = {**plan["raw"], **plan["purchases"]}
    plan["inventory_remaining"] = {t: max(0, q - plan["inventory_used"].get(t, 0)) for t, q in inventory.items()}
    buildable = []
    for type_id, item in catalog.items():
        recipe = item["recipe"]
        if recipe:
            runs = min(int(inventory.get(i["type_id"], 0) // i["quantity"]) for i in recipe["inputs"])
            if runs:
                buildable.append({"type_id": type_id, "quantity": runs * recipe["output"]["quantity"]})
    plan["buildable_direct"] = buildable
    plan["buildable_note"] = "Each product is an alternative using the same inventory; quantities cannot be added together."
    return plan


def operation_slots(request: PlanningRequest, context: dict) -> tuple[list[dict], list[str]]:
    pilots = {p["character_id"]: p for p in context["pilots"]}
    planets = {p.key: p for p in request.planets}
    slots, notes = [], []
    for choice in request.pilots:
        if choice.character_id not in pilots:
            raise ValueError("A selected character is no longer visible")
        pilot = pilots[choice.character_id]
        owned = {c["id"]: c for c in pilot["colonies"]}
        if set(choice.release_colony_ids) - set(owned):
            raise ValueError("A replacement colony does not belong to its selected pilot")
        if not choice.enabled:
            continue
        ccu = choice.planned_ccu if choice.planned_ccu is not None else pilot["ccu"]
        ic = choice.planned_ic if choice.planned_ic is not None else pilot["ic"]
        if ccu is None or ic is None:
            notes.append(f"{pilot['name']}: synchronize skills or enter planned skill levels")
            continue
        if choice.planned_ccu is not None or choice.planned_ic is not None:
            notes.append(f"{pilot['name']}: planned skills override observed skills")
        kept = [c for c in pilot["colonies"] if c["id"] not in choice.release_colony_ids]
        available = max(0, 1 + ic - len(kept))
        cpu, power = command_capacity(context["pins"], ccu)
        eligible = [planets[k] for k in choice.planet_keys if not any(c["planet_id"] == planets[k].planet_id for c in kept) or planets[k].planet_id is None]
        released = {c["planet_id"]: c for c in owned.values() if c["id"] in choice.release_colony_ids}
        slots.append({"character_id": choice.character_id, "name": pilot["name"], "ccu": ccu, "cce": pilot.get("cce") or 0, "cpu": cpu, "power": power, "available": available, "used": set(), "planets": eligible, "released": released})
    return slots, notes


def layout(catalog: dict, pins: dict, item: dict, runs: int, processors: int, planet, pilot: dict, request: PlanningRequest, extraction: bool) -> dict | None:
    recipe = item["recipe"]
    kind = "basic" if item["tier"] == 1 else "hightech" if item["tier"] == 4 else "advanced"
    if kind == "hightech" and planet.planet_type not in ("Barren", "Temperate"):
        return None
    factory = facility(pins, kind, planet.planet_type)
    pad = facility(pins, "launchpad", planet.planet_type)
    storage = facility(pins, "storage", planet.planet_type)
    inputs = {i["type_id"]: i["quantity"] * runs for i in recipe["inputs"]}
    output = {item["type_id"]: recipe["output"]["quantity"] * runs}
    facilities = [{**factory, "count": processors, "schematic_id": recipe["id"], "product_type_id": item["type_id"]}, {**pad, "count": 1}]
    heads = 0
    raw_output = {}
    raw_cycle_buffer = 0
    if extraction:
        if len(inputs) != 1:
            return None
        raw_id, raw_need = next(iter(inputs.items()))
        estimate = next((e for e in planet.yields if e.type_id == raw_id), None)
        if not estimate or planet.planet_type not in catalog[raw_id]["planet_types"]:
            return None
        # A stated average yield is for the chosen program, not ESI qty_per_cycle.
        interval = WEEK_HOURS / request.schedule.visits_per_week
        uptime = min(request.schedule.program_hours, max(0, interval - request.schedule.restart_minutes / 60))
        weekly_per_head = estimate.units_per_head_hour * uptime * request.schedule.visits_per_week
        if weekly_per_head <= 0:
            return None
        heads = batches(raw_need, weekly_per_head)
        if heads > 10:
            return None
        ecu = facility(pins, "ecu", planet.planet_type)
        facilities.append({**ecu, "count": 1, "heads": heads, "product_type_id": raw_id, "yield_source": estimate.source})
        raw_output[raw_id] = raw_need
        raw_cycle_buffer = min(raw_need, estimate.units_per_head_hour * heads * 4) * (catalog[raw_id]["volume"] or 0)
    volumes = [catalog[t].get("volume") for t in {*inputs, *output}]
    if any(v is None or v <= 0 for v in volumes):
        raise ValueError("A PI commodity is missing SDE volume")
    external_inputs = {} if extraction else inputs
    incoming_m3 = sum(q * catalog[t]["volume"] for t, q in external_inputs.items())
    outgoing_m3 = sum(q * catalog[t]["volume"] for t, q in output.items())
    # Conservative shared buffer: full visit's inputs and outputs coexist.
    required_storage = (incoming_m3 + outgoing_m3) / request.schedule.visits_per_week + raw_cycle_buffer
    stores = batches(max(0, required_storage - pad["capacity"]), storage["capacity"])
    if stores > 30:
        return None
    if stores:
        facilities.append({**storage, "count": stores})
    # Budget each spoke at the selected length, including capacity upgrades.
    links = []
    per_factory_flow = (sum(q * catalog[t]["volume"] for t, q in inputs.items()) + outgoing_m3) / max(1, processors) / WEEK_HOURS
    for _ in range(processors):
        links.append(per_factory_flow)
    if heads:
        links.append(sum(q * catalog[t]["volume"] for t, q in raw_output.items()) / WEEK_HOURS * 2)
    links.extend([(incoming_m3 + outgoing_m3 + raw_cycle_buffer) / max(1, stores) / WEEK_HOURS] * stores)
    levels = [max(0, math.ceil(math.log2(max(1, flow / 1250)))) for flow in links]
    if any(level > 10 for level in levels):
        return None
    length = request.schedule.link_length_km
    link_cpu = sum((15 + .2 * length) * 1.4**level for level in levels)
    link_power = sum((10 + .15 * length) * 1.2**level for level in levels)
    cpu = sum(f["cpu"] * f["count"] + f.get("heads", 0) * f.get("head_cpu", 0) for f in facilities) + link_cpu
    power = sum(f["power"] * f["count"] + f.get("heads", 0) * f.get("head_power", 0) for f in facilities) + link_power
    if cpu > pilot["cpu"] or power > pilot["power"]:
        return None
    old = pilot["released"].get(planet.planet_id)
    command_price = 0 if old else facility(pins, "command", planet.planet_type)["price"] + CC_UPGRADE_COST[pilot["ccu"]]
    if old:
        command_price += max(0, CC_UPGRADE_COST[pilot["ccu"]] - CC_UPGRADE_COST[min(5, old["upgrade_level"])])
    setup = sum(f["price"] * f["count"] for f in facilities) + command_price + request.costs.additional_setup_per_colony
    customs_rate = planet.customs_percent / 100 + (planet.npc_tax_percent / 100 * (1 - .1 * pilot["cce"]) if planet.security >= .5 else 0)
    customs = customs_rate * (sum(q * catalog[t]["tax_base"] * .5 for t, q in external_inputs.items()) + sum(q * catalog[t]["tax_base"] for t, q in output.items()))
    return {"character_id": pilot["character_id"], "character_name": pilot["name"], "planet_key": planet.key, "planet": planet.model_dump(), "replaces_colony_id": old["id"] if old else None, "ccu": pilot["ccu"], "product_type_id": item["type_id"], "processors": processors, "batches": runs, "heads": heads, "facilities": facilities, "inputs": inputs, "external_inputs": external_inputs, "outputs": output, "extraction": raw_output, "cpu": cpu, "power": power, "cpu_limit": pilot["cpu"], "power_limit": pilot["power"], "storage_required_m3": required_storage, "storage_m3": pad["capacity"] + stores * storage["capacity"], "link_levels": levels, "link_length_km": length, "setup_isk": setup, "customs_isk": customs, "customs_rate": customs_rate, "haul_m3": incoming_m3 + outgoing_m3, "weekly_factory_utilization": runs * recipe["cycle_time"] / (processors * 604800)}


def allocate(request: PlanningRequest, context: dict, expansion: dict, cancelled: Callable | None = None) -> tuple[list[dict] | None, list[str]]:
    catalog = context["catalog"]
    slots, notes = operation_slots(request, context)
    colonies = []
    # Limited high-tech planet choices first, then resources with fewer eligible planets.
    nodes = sorted(expansion["nodes"].values(), key=lambda n: (-catalog[n["type_id"]]["tier"], n["type_id"]))
    for node in nodes:
        item = catalog[node["type_id"]]
        runs_left = node["batches"]
        runs_per_factory = int(604800 // item["recipe"]["cycle_time"])
        if runs_per_factory <= 0:
            return None, ["A schematic exceeds the weekly planning horizon"]
        extraction = item["tier"] == 1 and any(i["type_id"] in expansion["raw"] for i in item["recipe"]["inputs"])
        while runs_left > 0:
            if cancelled and cancelled():
                return None, ["Search cancelled"]
            candidates = []
            for pilot in slots:
                if pilot["available"] <= 0:
                    continue
                for planet in pilot["planets"]:
                    identity = planet.planet_id or planet.key
                    if identity in pilot["used"]:
                        continue
                    for processors in range(min(32, batches(runs_left, runs_per_factory)), 0, -1):
                        runs = min(runs_left, processors * runs_per_factory)
                        row = layout(catalog, context["pins"], item, runs, processors, planet, pilot, request, extraction)
                        if row:
                            candidates.append((runs, -row["customs_isk"], -row["setup_isk"], pilot, identity, row))
                            break
            if not candidates:
                return None, notes + [f"No remaining colony can fit {item['name']} with these skills, yields and visit/storage limits"]
            chosen = max(candidates, key=lambda c: c[:3])
            runs, _, _, pilot, identity, row = chosen
            pilot["used"].add(identity)
            pilot["available"] -= 1
            colonies.append(row)
            runs_left -= runs
    return colonies, notes


def validate_plan(catalog: dict, request: PlanningRequest, context: dict, plan: dict) -> list[str]:
    """Independent aggregate checks over the result; no geometric certification."""
    errors, occupied, counts = [], set(), Counter()
    slots, _ = operation_slots(request, context)
    limits = {p["character_id"]: p["available"] for p in slots}
    supply = Counter({int(t): q for t, q in plan["purchases"].items()})
    demand = Counter({int(t): q for t, q in plan["targets"].items()})
    for colony in plan["colonies"]:
        identity = (colony["character_id"], colony["planet"]["planet_id"] or colony["planet_key"])
        if identity in occupied:
            errors.append("A pilot was allocated the same planet twice")
        occupied.add(identity)
        counts[colony["character_id"]] += 1
        if colony["cpu"] > colony["cpu_limit"] + .001 or colony["power"] > colony["power_limit"] + .001:
            errors.append("Colony exceeds command-center capacity")
        if colony["storage_required_m3"] > colony["storage_m3"] + .001:
            errors.append("Storage cannot cover the visit interval")
        if colony["heads"] > 10 or colony["weekly_factory_utilization"] > 1.000001:
            errors.append("Extractor or factory capacity exceeded")
        for t, q in colony["outputs"].items():
            supply[int(t)] += q
        for t, q in colony["extraction"].items():
            supply[int(t)] += q
            if colony["planet"]["planet_type"] not in catalog[int(t)]["planet_types"]:
                errors.append("Resource cannot occur on selected planet type")
        for t, q in colony["inputs"].items():
            demand[int(t)] += q
    if any(n > limits.get(t, 0) for t, n in counts.items()):
        errors.append("Pilot colony limit exceeded")
    if any(supply[t] + 1e-7 < q for t, q in demand.items()):
        errors.append("Operation has an unfunded material deficit")
    return errors


def evaluate(request: PlanningRequest, context: dict, market: dict, targets: dict, cut: int, cancelled: Callable | None = None, allocator: Callable | None = None) -> dict:
    catalog = context["catalog"]
    expansion = expand(catalog, targets, set(request.buy_type_ids), cut)
    colonies, notes = (allocator or allocate)(request, context, expansion, cancelled)
    if colonies is None:
        return {"feasible": False, "targets": targets, "reason": notes[-1] if notes else "No allocation fits"}
    purchases, sales, missing = {}, {}, []
    for t, q in expansion["purchases"].items():
        row = quote(market["books"].get(t), q, buying=True)
        purchases[t] = {"type_id": t, "quantity": q, **row}
        if row["unfilled"]:
            missing.append(f"{catalog[t]['name']}: {row['unfilled']:,.0f} input units have no eligible ESI ask depth")
    for t, q in targets.items():
        # Round surplus is disclosed separately and is not optimistically sold.
        sales[t] = {"type_id": t, "quantity": q, **quote(market["books"].get(t), q, buying=False, patient=request.sale_mode == "patient")}
    raw_purchase = expansion["purchases"]
    setup = sum(c["setup_isk"] for c in colonies)
    customs = sum(c["customs_isk"] for c in colonies)
    haul = sum(c["haul_m3"] for c in colonies)
    # Two customs legs for intermediates are real; hauling counts each leg too.
    visits = request.schedule.visits_per_week
    trips = batches(haul / visits, request.schedule.haul_capacity_m3)
    if setup > request.costs.setup_budget:
        missing.append("Setup cost exceeds the scenario budget")
    if trips > request.schedule.max_trips_per_visit:
        missing.append("Hauling exceeds the allowed trips per visit")
    revenue = sum(r["value"] for r in sales.values())
    inputs = sum(r["value"] for r in purchases.values())
    sales_tax = revenue * request.costs.sales_tax_percent / 100
    broker = revenue * request.costs.broker_fee_percent / 100 if request.sale_mode == "patient" else 0
    freight = haul * request.costs.freight_isk_m3
    overhead = request.costs.weekly_overhead + request.costs.per_colony_weekly * len(colonies)
    operating = revenue - inputs - customs - sales_tax - broker - freight - overhead
    net = operating - setup / request.costs.setup_amortization_weeks
    result = {"feasible": not missing, "capacity_feasible": setup <= request.costs.setup_budget and trips <= request.schedule.max_trips_per_visit, "reason": "; ".join(missing), "targets": targets, "sourcing_cut": cut, "colonies": colonies, "purchases": raw_purchase, "shopping": list(purchases.values()), "sales": list(sales.values()), "chain": list(expansion["nodes"].values()), "surplus": expansion["surplus"], "notes": notes, "economics": {"revenue": revenue, "inputs": inputs, "customs": customs, "sales_tax": sales_tax, "broker_fees": broker, "freight": freight, "overhead": overhead, "operating_net": operating, "net_after_setup_amortization": net, "setup": setup, "payback_weeks": setup / operating if operating > 0 else None, "first_week_cash": operating - setup, "isk_per_visit": operating / visits, "isk_per_active_hour": operating / (visits * request.schedule.minutes_per_visit / 60), "haul_m3": haul, "trips_per_visit": trips, "unfilled_sale_units": sum(s["unfilled"] for s in sales.values()), "patient_estimate": request.sale_mode == "patient"}, "schedule": {"visits_per_week": visits, "interval_hours": WEEK_HOURS / visits, "program_hours": request.schedule.program_hours, "extraction_uptime_fraction": min(request.schedule.program_hours, max(0, WEEK_HOURS / visits - request.schedule.restart_minutes / 60)) * visits / WEEK_HOURS, "actions": ["Refill purchased and inter-colony inputs", "Collect outputs and move intermediate products", "Restart extractors; recheck head positions and actual yield"]}}
    result["validation_errors"] = validate_plan(catalog, request, context, result)
    if result["validation_errors"]:
        result["feasible"] = False
        result["capacity_feasible"] = False
        result["reason"] = "; ".join(result["validation_errors"])
    return result


def run_planner(request: PlanningRequest, context: dict, market: dict, progress: Callable | None = None, cancelled: Callable | None = None) -> dict:
    from app.services.pi_allocation_engine import AllocationEngine

    with AllocationEngine(request, context) as engine:
        result = search_plans(request, context, market, progress, cancelled, engine.allocate)
        result["engine"] = engine.metadata()
        return result


def search_plans(request: PlanningRequest, context: dict, market: dict, progress: Callable | None = None, cancelled: Callable | None = None, allocator: Callable | None = None) -> dict:
    catalog = context["catalog"]
    if any(p.type_id not in catalog or not catalog[p.type_id]["recipe"] for p in request.products):
        raise ValueError("Select produced PI commodities from the current SDE catalog")
    if set(request.buy_type_ids) - set(catalog):
        raise ValueError("Unknown purchased commodity")
    for planet in request.planets:
        if any(y.type_id not in catalog or catalog[y.type_id]["tier"] != 0 or planet.planet_type not in catalog[y.type_id]["planet_types"] for y in planet.yields):
            raise ValueError(f"{planet.name}: a yield must describe a raw resource available on that planet type")
    operation_slots(request, context)  # Validate ownership even for an idle solution.
    start = time.monotonic()
    count, timed_out = 0, False
    best, failures = {}, []
    examined = set()
    cuts = [-1, 0, 1, 2, 3] if request.sourcing == "auto" else [{"extract": -1, "buy_raw": 0, "buy_p1": 1, "buy_p2": 2, "buy_p3": 3}[request.sourcing]]
    groups = [{p.type_id: p.quantity for p in request.products}] if request.objective == "mix" else [{p.type_id: p.quantity} for p in request.products]

    def stopped():
        return bool(cancelled and cancelled()) or time.monotonic() - start >= request.search_seconds

    def score(plan):
        if request.objective == "output":
            return (sum(plan["targets"].values()), plan["economics"]["net_after_setup_amortization"])
        return (plan["economics"]["net_after_setup_amortization"], -plan["economics"]["setup"])

    def attempt(targets, cut):
        nonlocal count
        if stopped():
            return None
        count += 1
        examined.update(targets)
        plan = evaluate(request, context, market, targets, cut, stopped, allocator)
        if plan["feasible"]:
            key = (tuple(sorted(plan["targets"])), plan["sourcing_cut"])
            if key not in best or score(plan) > score(best[key]):
                best[key] = plan
        elif len(failures) < 50:
            failures.append({"targets": targets, "cut": cut, "reason": plan["reason"]})
        if progress and count % 5 == 0:
            progress(count, min(.99, (time.monotonic() - start) / request.search_seconds))
        return plan

    # Give each product/sourcing pair a small preflight before expensive refinement.
    if request.objective not in ("quota", "mix"):
        for group in groups:
            for cut in cuts:
                t = next(iter(group))
                if cut < catalog[t]["tier"]:
                    attempt({t: catalog[t]["recipe"]["output"]["quantity"]}, cut)
    for cut in cuts:
        for group in groups:
            if stopped():
                timed_out = True
                break
            if cut >= min(catalog[t]["tier"] for t in group):
                continue
            if request.objective in ("quota", "mix"):
                attempt(group, cut)
                continue
            t = next(iter(group))
            size = catalog[t]["recipe"]["output"]["quantity"]
            # Quantity lattice includes small batches, demand, and visible order breakpoints.
            amounts = {size, max(size, math.ceil(group[t] / size) * size)}
            depth = 0
            for order in market["books"].get(t, {}).get("bids", []):
                depth += order["volume"]
                amounts.add(max(size, int(depth // size) * size))
                amounts.add(max(size, math.ceil(min(order.get("minimum", 1), order["volume"]) / size) * size))
                if len(amounts) >= 30:
                    break
            # Geometric scale + a binary capacity boundary: lower profitable scales survive.
            amount = size
            low, high = 0, None
            for _ in range(22):
                plan = attempt({t: amount}, cut)
                if plan is None:
                    break
                if not plan.get("capacity_feasible", False):
                    high = amount
                    break
                low = amount
                amount *= 2
                if amount > 1e9:
                    break
            if high and low:
                for _ in range(12):
                    midpoint = int((low + high) / 2 // size) * size
                    if midpoint <= low or stopped():
                        break
                    plan = attempt({t: midpoint}, cut)
                    if plan and plan.get("capacity_feasible", False):
                        low = midpoint
                    else:
                        high = midpoint
            for amount in sorted(amounts):
                if amount <= 1e9:
                    attempt({t: amount}, cut)
    # Retain at most one best-found alternative per product set and sourcing cut.
    ranked = sorted(best.values(), key=score, reverse=True)
    idle = {"feasible": True, "idle": True, "targets": {}, "colonies": [], "economics": {"operating_net": 0, "net_after_setup_amortization": 0, "setup": 0}, "reason": "Keep the existing operation; build no additional colonies"}
    if request.objective in ("profit", "compare") and (not ranked or score(ranked[0])[0] <= 0):
        ranked.insert(0, idle)
    encoded = json.dumps({"request": request.model_dump(), "context": context, "market": market}, sort_keys=True, default=str)
    return {"schema_version": "eqm.pi-planning-result.v1", "request": request.model_dump(), "input_sha256": hashlib.sha256(encoded.encode()).hexdigest(), "plans": ranked[:30], "failures": failures, "search": {"evaluated": count, "products_examined": len(examined), "products_requested": len(request.products), "unexamined_type_ids": sorted({p.type_id for p in request.products} - examined), "seconds": round(time.monotonic() - start, 3), "timed_out": timed_out or stopped() and not bool(cancelled and cancelled()), "cancelled": bool(cancelled and cancelled()), "method": "Bounded production-scale and sourcing search with greedy per-colony packing; no global optimum guarantee"}, "market": market, "baseline": context.get("baseline", {}), "assumptions": ["Existing colonies remain reserved unless explicitly selected for replacement. Their production is outside this incremental profit ledger.", "Extraction uses stated average yield for the selected program; depletion, interference and head placement require in-game checks.", "Factory output is steady-state weekly capacity. A new multi-stage chain needs startup materials or a ramp-up period.", "Each proposed colony produces one processed commodity. Links use the chosen length and estimated transport load; placement and burst throughput are not certified.", "Surplus has no assumed sale value. Missing purchase depth makes a plan infeasible. Immediate sales stop at visible station order depth.", "ESI is a snapshot, not a reservation. Patient sales assume the lowest station ask, with unknown fill time and relisting costs excluded."]}
