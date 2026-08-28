from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from app.services.fitting_simulator import (
    SLOT_CAPACITY_ATTRS,
    effective_ship_attrs_with_subsystems,
    fitted_items_within_slot_capacity,
    item_resource_usage,
    module_quantity,
    normalize_attr,
    ship_resource_capacity,
    slot_prefix,
)


def normalized_attrs(attrs: dict[str, float]) -> dict[str, float]:
    return {normalize_attr(name): float(value) for name, value in attrs.items()}


def evaluate_resource_fixture(payload: dict) -> dict:
    items = [
        SimpleNamespace(
            id=item["id"],
            type_id=item["type_id"],
            flag=item["flag"],
            quantity=item["quantity"],
            simulation_state=item["simulation_state"],
            charge_type_id=None,
            item_type=SimpleNamespace(name=item["name"]),
        )
        for item in payload["items"]
    ]
    source_by_id = {item["id"]: item for item in payload["items"]}
    dogma = {
        item["type_id"]: normalized_attrs(item["attrs"])
        for item in payload["items"]
    }
    skill_levels = {int(type_id): level for type_id, level in payload["skill_levels"].items()}
    ship_attrs = effective_ship_attrs_with_subsystems(
        normalized_attrs(payload["ship_attrs"]), items, dogma
    )
    resources = ship_resource_capacity(ship_attrs, skill_levels)
    slot_usage = {prefix: 0 for prefix in SLOT_CAPACITY_ATTRS}
    item_rows = []
    for item in items:
        slot = slot_prefix(item.flag)
        if slot in slot_usage:
            slot_usage[slot] += module_quantity(item)
        source = source_by_id[item.id]
        usage = item_resource_usage(
            item,
            dogma[item.type_id],
            source["group_name"],
            skill_levels,
            ship_attrs,
        )
        for resource, amount in usage.items():
            resources[resource]["used"] += amount
        item_rows.append({"id": item.id, **usage})

    slots = []
    for prefix, (attr_name, _) in SLOT_CAPACITY_ATTRS.items():
        capacity_value = ship_attrs.get(normalize_attr(attr_name))
        capacity = int(capacity_value) if capacity_value is not None else None
        used = slot_usage[prefix]
        slots.append({
            "key": prefix,
            "used": used,
            "capacity": capacity,
            "ok": capacity is None or used <= capacity,
        })
    for row in resources.values():
        row["ok"] = row["capacity"] is None or row["used"] <= float(row["capacity"] or 0)
        row["percent"] = min(999.0, row["used"] / float(row["capacity"]) * 100) if row["capacity"] else None

    selected_attrs = {
        name: ship_attrs.get(normalize_attr(name))
        for name in (
            "cpuOutput",
            "powerOutput",
            "hiSlots",
            "subsystemMHTFittingReduction",
            "subsystemMMissileFittingReduction",
        )
    }
    return {
        "schema_version": "eqm.fitting-resources-output.v1",
        "effective_ship_attrs": selected_attrs,
        "resources": resources,
        "slots": slots,
        "item_usage": item_rows,
        "stats_item_ids": [
            item.id for item in fitted_items_within_slot_capacity(items, ship_attrs)
        ],
    }


def test_shared_fitting_resource_fixture_matches_python_reference() -> None:
    fixtures = Path(__file__).parent / "fixtures"
    payload = json.loads((fixtures / "fitting-resources-input.v1.json").read_text())
    expected = json.loads((fixtures / "fitting-resources-output.v1.json").read_text())
    assert evaluate_resource_fixture(payload) == expected
