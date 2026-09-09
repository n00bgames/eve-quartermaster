"""PI game data from EQM's SDE; the bundled fallback contains CCP data, not SPI code."""
from __future__ import annotations

import json
import math
from pathlib import Path

PLANET_TYPES = {2014: "Oceanic", 2015: "Lava", 2016: "Barren", 2017: "Storm", 2063: "Plasma", 11: "Temperate", 12: "Ice", 13: "Gas"}
RESOURCE_PLANETS = {
    "Aqueous Liquids": ["Barren", "Gas", "Ice", "Oceanic", "Storm", "Temperate"],
    "Autotrophs": ["Temperate"], "Base Metals": ["Barren", "Gas", "Lava", "Plasma", "Storm"],
    "Carbon Compounds": ["Barren", "Oceanic", "Temperate"], "Complex Organisms": ["Oceanic", "Temperate"],
    "Felsic Magma": ["Lava"], "Heavy Metals": ["Ice", "Lava", "Plasma"], "Ionic Solutions": ["Gas", "Storm"],
    "Microorganisms": ["Barren", "Ice", "Oceanic", "Temperate"], "Noble Gas": ["Gas", "Ice", "Storm"],
    "Noble Metals": ["Barren", "Plasma"], "Non-CS Crystals": ["Lava", "Plasma"],
    "Planktic Colonies": ["Ice", "Oceanic"], "Reactive Gas": ["Gas"], "Suspended Plasma": ["Lava", "Plasma", "Storm"],
}
FALLBACK_PINS = json.loads((Path(__file__).parent.parent / "data/pi_planning_pins.json").read_text(encoding="utf-8"))["pins"]
# Installed command-center upgrade charges, cumulative, excluding the purchased center.
CC_UPGRADE_COST = [0, 580000, 1510000, 2710000, 4210000, 6310000]
TAX_BASE = [5, 400, 7200, 60000, 1200000]


def pin_catalog(overrides: dict | None = None) -> dict:
    result = {}
    for key, row in FALLBACK_PINS.items():
        attrs = {**row["dogma"], **(overrides or {}).get(int(key), {})}
        result[int(key)] = {**row, "dogma": attrs, "type_id": int(key)}
    return result


def facility(pins: dict, kind: str, planet_type: str) -> dict:
    suffix = {"basic": "Basic Industry Facility", "advanced": "Advanced Industry Facility", "hightech": "High-Tech Production Plant", "ecu": "Extractor Control Unit", "storage": "Storage Facility", "launchpad": "Launchpad", "command": "Command Center"}[kind]
    for row in pins.values():
        if row["name"] == f"{planet_type} {suffix}":
            attrs = row["dogma"]
            return {"kind": kind, "type_id": row["type_id"], "name": row["name"], "cpu": attrs.get("49", 0), "power": attrs.get("15", 0), "price": row["price"], "capacity": row["capacity"], "head_cpu": attrs.get("1690", 110), "head_power": attrs.get("1691", 550)}
    raise ValueError(f"No {kind} facility on {planet_type} in the PI catalog")


def command_capacity(pins: dict, level: int) -> tuple[float, float]:
    for row in pins.values():
        a = row["dogma"]
        if a.get("1632") == 2016 and "48" in a and int(a.get("633", 0)) == level:
            return a["48"], a["11"]
    raise ValueError(f"Command-center level {level} missing from SDE fallback")


def make_catalog(schematics: list[dict]) -> dict[int, dict]:
    items: dict[int, dict] = {}
    recipes = {}
    for recipe in schematics:
        output = recipe["output"]
        if output["type_id"] in recipes:
            raise ValueError("PI output has multiple schematics; refresh the SDE")
        recipes[output["type_id"]] = recipe
        for item in [output, *recipe["inputs"]]:
            volume = item.get("volume")
            if volume is None or not math.isfinite(volume) or volume <= 0:
                raise ValueError("A PI commodity is missing SDE volume; refresh the SDE before planning")
            items[item["type_id"]] = {"type_id": item["type_id"], "name": item["name"], "volume": item.get("volume"), "planet_types": RESOURCE_PLANETS.get(item["name"], [])}
    visiting = set()

    def tier(type_id: int) -> int:
        item = items[type_id]
        if "tier" in item:
            return item["tier"]
        if type_id in visiting:
            raise ValueError("Cyclic PI schematic catalog")
        visiting.add(type_id)
        recipe = recipes.get(type_id)
        if recipe and (recipe["cycle_time"] <= 0 or recipe["output"]["quantity"] <= 0 or not recipe["inputs"] or any(i["quantity"] <= 0 for i in recipe["inputs"])):
            raise ValueError("Invalid PI schematic quantities")
        item["tier"] = 1 + max(tier(i["type_id"]) for i in recipe["inputs"]) if recipe else 0
        if item["tier"] > 4:
            raise ValueError("Unsupported PI schematic depth")
        item["tax_base"] = TAX_BASE[item["tier"]]
        item["recipe"] = recipe
        visiting.remove(type_id)
        return item["tier"]

    for type_id in items:
        tier(type_id)
    return items
