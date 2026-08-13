from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from app.services.fitting_simulator import compute_fitting_stats, normalize_attr


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "fittings"
SELECTOR_RE = re.compile(r"^(?P<name>[^\[]+)\[(?P<key>[^=]+)=(?P<value>[^\]]+)\]$")


def reference_fixture_paths() -> list[Path]:
    return sorted(FIXTURE_ROOT.glob("*.json"))


def load_reference_fixture(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise AssertionError(f"{path.name}: unsupported fitting reference schema")
    source = payload.get("source") or {}
    if not source.get("kind") or "externally_verified" not in source:
        raise AssertionError(f"{path.name}: source.kind and source.externally_verified are required")
    if not payload.get("expected"):
        raise AssertionError(f"{path.name}: at least one expected metric is required")
    return payload


def _item(row: dict[str, Any], names: dict[int, str]) -> SimpleNamespace:
    type_id = int(row["type_id"])
    return SimpleNamespace(
        id=int(row["id"]),
        type_id=type_id,
        flag=str(row["flag"]),
        quantity=max(1, int(row.get("quantity", 1))),
        simulation_state=str(row.get("simulation_state") or "online"),
        charge_type_id=int(row["charge_type_id"]) if row.get("charge_type_id") is not None else None,
        item_type=SimpleNamespace(name=names.get(type_id, f"Type {type_id}")),
    )


def compute_reference_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    ship = payload["ship"]
    type_rows = payload.get("types") or {}
    names = {int(type_id): str(row.get("name") or f"Type {type_id}") for type_id, row in type_rows.items()}
    names[int(ship["type_id"])] = str(ship["name"])
    dogma = {
        int(type_id): {normalize_attr(name): float(value) for name, value in (row.get("dogma") or {}).items()}
        for type_id, row in type_rows.items()
    }
    dogma[int(ship["type_id"])] = {
        normalize_attr(name): float(value) for name, value in (ship.get("dogma") or {}).items()
    }
    groups = {int(type_id): str(row.get("group") or "") for type_id, row in type_rows.items()}
    group_ids = {
        int(type_id): int(row["group_id"])
        for type_id, row in type_rows.items()
        if row.get("group_id") is not None
    }
    fitting = SimpleNamespace(
        ship_type_id=int(ship["type_id"]),
        items=[_item(row, names) for row in payload.get("items") or []],
    )
    character = payload.get("character") or {}
    return compute_fitting_stats(
        fitting,
        dogma,
        names,
        groups,
        {int(type_id): int(level) for type_id, level in (character.get("skills") or {}).items()},
        {str(name): int(level) for name, level in (character.get("skill_names") or {}).items()},
        {int(type_id): float(row.get("volume") or 0.0) for type_id, row in type_rows.items()},
        float(ship["capacity"]) if ship.get("capacity") is not None else None,
        ship_mass=float(ship["mass"]) if ship.get("mass") is not None else None,
        dogma_effects={int(type_id): rows for type_id, rows in (payload.get("dogma_effects") or {}).items()},
        implant_type_ids={int(type_id) for type_id in payload.get("implant_type_ids") or []},
        type_group_ids=group_ids,
        heat=bool(payload.get("heat", False)),
    )


def metric_at_path(payload: Any, path: str) -> Any:
    current = payload
    for component in path.split("."):
        selector = SELECTOR_RE.match(component)
        if selector:
            current = current[selector.group("name")]
            key = selector.group("key")
            expected = selector.group("value")
            current = next((row for row in current if str(row.get(key)) == expected), None)
            if current is None:
                raise AssertionError(f"No row matching {key}={expected} at {path}")
        else:
            current = current[component]
    return current
