"""Parse copied directional scans against SDE; never infer pilots from ship names."""
from __future__ import annotations

from collections import Counter
import math
import re
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload
from app.models import EveGroup, EveType

MAX_OBJECTS = 5000
RECONS = ("Huginn", "Lachesis", "Rook", "Curse")


def parse(text: str) -> tuple[list[dict], list[dict]]:
    objects, ignored = [], []
    for number, raw in enumerate(text.lstrip("\ufeff").splitlines(), 1):
        if not raw.strip():
            continue
        cells = [c.strip() for c in (raw.split("\t") if "\t" in raw else re.split(r" {2,}", raw.strip()))]
        lower = [c.lower() for c in cells]
        if "type" in lower and "name" in lower and "distance" in lower:
            continue
        reason = None
        if len(cells) == 4:
            identity, name, type_name, distance = cells
            type_id = int(identity) if identity.isdecimal() and len(identity) < 11 else None
            if type_id is None or not 0 < type_id < 2**31:
                reason = "Invalid type ID"
        elif len(cells) == 3:
            name, type_name, distance = cells
            type_id = None
        else:
            reason = "Expected Name / Type / Distance, with optional leading type ID"
            name = type_name = distance = ""
            type_id = None
        if not reason and (not type_name or len(name) > 255 or len(type_name) > 255 or len(distance) > 64
                           or any(ord(c) < 32 for c in name + type_name + distance)):
            reason = "Missing type name, overlong field, or control character"
        if reason:
            # Do not retain arbitrary rejected input in a public report.
            ignored.append({"line": number, "reason": reason})
        else:
            objects.append({"type_id": type_id, "name": name, "type_name": type_name, "distance": distance})
        if len(objects) + len(ignored) > MAX_OBJECTS:
            raise ValueError(f"A d-scan supports at most {MAX_OBJECTS:,} object rows.")
    if not objects:
        raise ValueError("No d-scan rows found. Copy the scan results with Ctrl+A, Ctrl+C and paste the tab-separated rows.")
    return objects, ignored


def category(item) -> str:
    group = item.group
    if group is None or group.category is None:
        return "unresolved"
    name = group.category.name.lower() if group and group.category else ""
    group_name = group.name.lower() if group else ""
    if name == "ship":
        return "ships"
    if name == "deployable" or any(term in group_name for term in ("secure container", "freight container", "cargo container")):
        return "deployables"
    if name in {"drone", "fighter"}:
        return "drones"
    if name in {"structure", "starbase", "sovereignty structure"}:
        return "structures"
    return "other"


def catalog(db, objects):
    ids = sorted({o["type_id"] for o in objects if o["type_id"]})
    names = sorted({o["type_name"].lower() for o in objects if not o["type_id"]} | {n.lower() for n in RECONS})
    found = {}
    for offset in range(0, max(len(ids), len(names)), 300):
        rows = db.scalars(select(EveType).where(or_(EveType.type_id.in_(ids[offset:offset+300]),
                           func.lower(EveType.name).in_(names[offset:offset+300])))
                          .options(selectinload(EveType.group).selectinload(EveGroup.category))).all()
        found.update({t.type_id: t for t in rows})
    by_name = {}
    for item in found.values():
        by_name.setdefault(item.name.lower(), []).append(item)
    return found, {name: items[0] for name, items in by_name.items() if len(items) == 1}


def summarize(db, objects: list[dict], manual_recons: dict[str, int]) -> dict:
    by_id, by_name = catalog(db, objects)
    groups, warnings, resolved_objects = {}, [], []
    for obj in objects:
        item = by_id.get(obj["type_id"]) if obj["type_id"] else by_name.get(obj["type_name"].lower())
        if item and obj["type_id"] and item.name.lower() != obj["type_name"].lower():
            warnings.append("Some pasted type names disagree with their type IDs; imported SDE names were used.")
        resolved = {**obj, "type_id": item.type_id if item else obj["type_id"],
                    "type_name": item.name if item else obj["type_name"], "resolved": item is not None}
        resolved_objects.append(resolved)
        key = (item.type_id if item else obj["type_id"], resolved["type_name"])
        if key not in groups:
            mass = float(item.mass) if item and item.mass is not None else None
            groups[key] = {"type_id": resolved["type_id"], "type_name": resolved["type_name"],
                           "group_name": item.group.name if item and item.group else "Unknown class",
                           "category": category(item) if item else "unresolved", "observed": 0, "manual": 0,
                           "unit_mass_kg": mass if mass is not None and math.isfinite(mass) and mass > 0 else None}
        groups[key]["observed"] += 1
    for name, count in manual_recons.items():
        if not count:
            continue
        item = by_name.get(name.lower())
        if item is None or category(item) != "ships":
            raise ValueError(f"Import or refresh the SDE before adding manual {name} counts.")
        key = (item.type_id, item.name)
        if key not in groups:
            mass = float(item.mass) if item.mass is not None else None
            groups[key] = {"type_id": item.type_id, "type_name": item.name, "group_name": item.group.name,
                           "category": "ships", "observed": 0, "manual": 0,
                           "unit_mass_kg": mass if mass is not None and math.isfinite(mass) and mass > 0 else None}
        groups[key]["manual"] = count
    rows = [{**g, "count": g["observed"] + g["manual"]} for g in groups.values()]
    rows.sort(key=lambda r: (-r["count"], r["type_name"].casefold(), r["type_id"] or 0))
    classes = Counter()
    ships = [r for r in rows if r["category"] == "ships"]
    for row in ships:
        classes[row["group_name"]] += row["count"]
    missing_mass = sum(r["count"] for r in ships if r["unit_mass_kg"] is None)
    unresolved_count = sum(r["observed"] for r in rows if r["category"] == "unresolved")
    warnings.append("D-scan gives object names and types, not pilot/corporation ownership. Ship names are never used to assign ownership or red markings.")
    if unresolved_count:
        warnings.append(f"{unresolved_count} objects have unresolved SDE types. Their classification and mass are unknown; import or refresh the SDE.")
    if missing_mass:
        warnings.append(f"Mass is unavailable for {missing_mass} identified ships; the mass shown is a partial sum.")
    if any(manual_recons.values()):
        warnings.append("Manual combat recons are user-supplied estimates, added to observed counts; they were not detected by this d-scan.")
    return {"objects": resolved_objects, "rows": rows, "object_count": len(objects),
            "ship_count": sum(r["count"] for r in ships), "observed_ship_count": sum(r["observed"] for r in ships),
            "manual_ship_count": sum(manual_recons.values()), "manual_recons": manual_recons,
            "unresolved_count": unresolved_count,
            "classes": [{"name": name, "count": count} for name, count in sorted(classes.items(), key=lambda x: (-x[1], x[0]))],
            "ship_mass_kg": sum(r["unit_mass_kg"] * r["count"] for r in ships if r["unit_mass_kg"] is not None),
            "mass_unknown_count": missing_mass, "mass_complete": not missing_mass and not unresolved_count,
            "warnings": list(dict.fromkeys(warnings)), "source": "Directional scan clipboard with imported SDE classification and base hull mass; manual additions are labeled."}
