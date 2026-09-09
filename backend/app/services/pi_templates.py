"""Original layouts serialized to EVE's publicly demonstrated clipboard schema.

No community layouts are bundled. File validation does not certify a live colony.
"""
from __future__ import annotations

import json
import math

from app.services.pi_catalog import PLANET_TYPES


def inspect_template(text: str, catalog: dict, pins: dict) -> dict:
    def reject_constant(value):
        raise ValueError(f"Non-finite JSON number: {value}")
    try:
        data = json.loads(text, parse_constant=reject_constant)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("Invalid template JSON") from exc
    if not isinstance(data, dict) or set(data) - {"CmdCtrLv", "Cmt", "Diam", "L", "P", "Pln", "R"}:
        raise ValueError("Unsupported EVE template fields")
    if not {"CmdCtrLv", "Diam", "L", "P", "Pln", "R"} <= set(data):
        raise ValueError("Missing EVE template fields")
    if type(data["CmdCtrLv"]) is not int or not 0 <= data["CmdCtrLv"] <= 5 or type(data["Pln"]) is not int or data["Pln"] not in PLANET_TYPES:
        raise ValueError("Invalid command-center level or planet type")
    if not isinstance(data["Diam"], (int, float)) or not 100 <= data["Diam"] <= 500000:
        raise ValueError("Invalid planet diameter")
    if not isinstance(data.get("Cmt", ""), str) or len(data.get("Cmt", "")) > 500:
        raise ValueError("Template comment is too long")
    for key, maximum in [("P", 120), ("L", 240), ("R", 600)]:
        if not isinstance(data[key], list) or len(data[key]) > maximum:
            raise ValueError(f"Invalid template {key} list")
    if not data["P"]:
        raise ValueError("Template has no facilities")
    for pin in data["P"]:
        if not isinstance(pin, dict) or set(pin) != {"H", "La", "Lo", "S", "T"}:
            raise ValueError("Unsupported facility fields")
        if type(pin["T"]) is not int or pin["T"] not in pins or pins[pin["T"]]["dogma"].get("1632") != data["Pln"]:
            raise ValueError("Facility is incompatible with planet type")
        if type(pin["H"]) is not int or not 0 <= pin["H"] <= 10:
            raise ValueError("Invalid extractor head count")
        if not isinstance(pin["La"], (int, float)) or not 0 <= pin["La"] <= math.pi or not isinstance(pin["Lo"], (int, float)) or not 0 <= pin["Lo"] <= math.tau:
            raise ValueError("Invalid facility coordinates")
        if pin["S"] is not None and (type(pin["S"]) is not int or pin["S"] not in catalog):
            raise ValueError("Unknown facility product")
        name = pins[pin["T"]]["name"]
        extractor = name.endswith("Extractor Control Unit")
        tier = catalog[pin["S"]]["tier"] if pin["S"] is not None else None
        if pin["H"] and not extractor:
            raise ValueError("Only extractors can have heads")
        if tier is not None:
            permitted = [0] if extractor else [1] if name.endswith("Basic Industry Facility") else [2, 3] if name.endswith("Advanced Industry Facility") else [4] if name.endswith("High-Tech Production Plant") else []
            if tier not in permitted or extractor and PLANET_TYPES[data["Pln"]] not in catalog[pin["S"]]["planet_types"]:
                raise ValueError("Product cannot be produced by this facility")
    def index(value):
        return type(value) is int and 1 <= value <= len(data["P"])
    edges = set()
    for link in data["L"]:
        if not isinstance(link, dict) or set(link) != {"S", "D", "Lv"} or not index(link["S"]) or not index(link["D"]) or link["S"] == link["D"] or type(link["Lv"]) is not int or not 0 <= link["Lv"] <= 10:
            raise ValueError("Invalid template link")
        edge = tuple(sorted((link["S"], link["D"])))
        if edge in edges:
            raise ValueError("Duplicate template link")
        edges.add(edge)
    for route in data["R"]:
        if not isinstance(route, dict) or set(route) != {"P", "Q", "T"}:
            raise ValueError("Unsupported route fields")
        path = route["P"]
        if not isinstance(path, list) or not 2 <= len(path) <= 7 or any(not index(i) for i in path) or len(set(path)) != len(path):
            raise ValueError("Invalid route path")
        if any(tuple(sorted(pair)) not in edges for pair in zip(path, path[1:])):
            raise ValueError("Route traverses a missing link")
        if type(route["Q"]) is not int or not 0 < route["Q"] <= 1e12 or type(route["T"]) is not int or route["T"] not in catalog:
            raise ValueError("Invalid route quantity or commodity")
        source, destination = data["P"][path[0] - 1], data["P"][path[-1] - 1]
        if source["S"] is not None and route["T"] != source["S"]:
            raise ValueError("Route commodity is not produced by its source")
        if destination["S"] is not None:
            recipe = catalog[destination["S"]]["recipe"]
            if not recipe or route["T"] not in {i["type_id"] for i in recipe["inputs"]}:
                raise ValueError("Route commodity is not consumed by its destination")
    return {"template": data, "summary": {"planet_type": PLANET_TYPES[data["Pln"]], "facilities": len(data["P"]), "links": len(data["L"]), "routes": len(data["R"])}, "validation": "Clipboard structure and route connectivity validated; in-game placement, capacity and import must be checked"}


def generate_template(colony: dict, catalog: dict, pins: dict) -> dict:
    type_id = colony["product_type_id"]
    recipe = catalog[type_id]["recipe"]
    planet = colony["planet"]
    diameter = planet["diameter_km"]
    planet_type = next(t for t, name in PLANET_TYPES.items() if name == planet["planet_type"])
    data = {"CmdCtrLv": colony["ccu"], "Cmt": f"EQM: {catalog[type_id]['name']} - verify placement and staging", "Diam": diameter, "L": [], "P": [], "Pln": planet_type, "R": []}
    buffers, factories, ecu = [], [], None
    def add(f, product=None, heads=0):
        i = len(data["P"])
        angle = i * 2.399963229728653
        # All pin pairs stay within the chosen spoke-length budget.
        radius = min(.1, colony["link_length_km"] / diameter) if i else 0
        data["P"].append({"H": heads, "La": round(math.pi / 2 + radius * math.sin(angle), 8), "Lo": round(math.pi + radius * math.cos(angle), 8), "S": product, "T": f["type_id"]})
        return i + 1
    for f in colony["facilities"]:
        if f["kind"] == "launchpad":
            buffers.append(add(f))
    for f in colony["facilities"]:
        if f["kind"] == "storage":
            buffers.extend(add(f) for _ in range(f["count"]))
    for f in colony["facilities"]:
        if f["kind"] in ("basic", "advanced", "hightech"):
            factories.extend(add(f, type_id) for _ in range(f["count"]))
        if f["kind"] == "ecu":
            ecu = add(f, f["product_type_id"], f["heads"])
    def connect(a, b):
        if any({l["S"], l["D"]} == {a, b} for l in data["L"]):
            return
        data["L"].append({"S": a, "D": b, "Lv": max(colony["link_levels"], default=0)})
    for buffer in buffers[1:]:
        connect(buffers[0], buffer)
    groups = {b: 0 for b in buffers}
    for i, factory in enumerate(factories):
        buffer = buffers[i % len(buffers)]
        groups[buffer] += 1
        connect(buffer, factory)
        for material in recipe["inputs"]:
            data["R"].append({"P": [buffer, factory], "Q": material["quantity"], "T": material["type_id"]})
        data["R"].append({"P": [factory, buffer], "Q": recipe["output"]["quantity"], "T": type_id})
    if ecu:
        connect(ecu, buffers[0])
        for buffer, n in groups.items():
            if n:
                raw = recipe["inputs"][0]
                path = [ecu, buffer] if buffer == buffers[0] else [ecu, buffers[0], buffer]
                data["R"].append({"P": path, "Q": max(1, math.ceil(n * raw["quantity"] * 14400 / recipe["cycle_time"])), "T": raw["type_id"]})
    checked = inspect_template(json.dumps(data), catalog, pins)
    checked["instructions"] = ["Preview in EVE before building. Adjust pin spacing, links and extractor heads for the actual planet.", "Upgrade the command center to the stated level; it is not included in the template pins.", "Storage buffers split factory inputs and outputs. Use expedited transfers from/to the launchpad at each visit; staging transfer cooldown is not simulated.", "Set the extractor program and review routes after installation. Extractor routes here use a conservative four-hour allowance.", "Generated coordinates are a starting layout, not the aggregate fit certificate. Confirm CPU, power, storage distribution and link load in-game."]
    return checked
