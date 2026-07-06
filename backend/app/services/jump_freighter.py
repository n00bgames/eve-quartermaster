from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from heapq import heappop, heappush
from math import ceil, floor, sqrt
from typing import Any

import httpx

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import EveConstellation, EveStargate, EveStation, EveSystem
from app.models.navigation import SystemIndustrialKillObservation, SystemJumpObservation, SystemPvpKillObservation
from app.services.navigation import resolve_system, security_band, serialize_system

LIGHT_YEAR_METERS = 9_460_730_472_580_800
JDC_RANGE_BONUS_PER_LEVEL = 0.2
JFC_FUEL_REDUCTION_PER_LEVEL = 0.1
ESI_SYSTEM_JUMPS_URL = "https://esi.evetech.net/latest/universe/system_jumps/?datasource=tranquility"
USER_AGENT = "EVE-Quartermaster/0.1.4-beta capital-route-intel"

FUEL_TYPE_NAMES = {
    16274: "Helium Isotopes",
    17887: "Oxygen Isotopes",
    17888: "Nitrogen Isotopes",
    17889: "Hydrogen Isotopes",
}


@dataclass(frozen=True)
class JumpFreighterShip:
    name: str
    type_id: int
    fuel_type_id: int
    fuel_type_name: str
    fuel_per_light_year: int
    base_range_ly: float
    ship_class: str


def capital_ship(name: str, type_id: int, fuel_type_id: int, fuel_per_light_year: int, base_range_ly: float, ship_class: str) -> JumpFreighterShip:
    return JumpFreighterShip(name, type_id, fuel_type_id, FUEL_TYPE_NAMES[fuel_type_id], fuel_per_light_year, base_range_ly, ship_class)


JUMP_FREIGHTERS: dict[str, JumpFreighterShip] = {
    "anshar": capital_ship("Anshar", 28848, 17887, 9400, 5.0, "Jump Freighter"),
    "ark": capital_ship("Ark", 28850, 16274, 8800, 5.0, "Jump Freighter"),
    "nomad": capital_ship("Nomad", 28846, 17889, 8200, 5.0, "Jump Freighter"),
    "rhea": capital_ship("Rhea", 28844, 17888, 10000, 5.0, "Jump Freighter"),
    "rorqual": capital_ship("Rorqual", 28352, 17887, 4000, 5.0, "Capital Industrial Ship"),
    "archon": capital_ship("Archon", 23757, 16274, 3000, 3.5, "Carrier"),
    "chimera": capital_ship("Chimera", 23915, 17888, 3000, 3.5, "Carrier"),
    "nidhoggur": capital_ship("Nidhoggur", 24483, 17889, 3000, 3.5, "Carrier"),
    "thanatos": capital_ship("Thanatos", 23911, 17887, 3000, 3.5, "Carrier"),
    "salvation": capital_ship("Salvation", 92822, 16274, 3000, 3.75, "Command Carrier"),
    "simurgh": capital_ship("Simurgh", 92823, 17888, 3000, 3.75, "Command Carrier"),
    "gaia": capital_ship("Gaia", 92824, 17887, 3000, 3.75, "Command Carrier"),
    "ymir": capital_ship("Ymir", 92825, 17889, 3000, 3.75, "Command Carrier"),
    "revelation": capital_ship("Revelation", 19720, 16274, 3000, 3.5, "Dreadnought"),
    "moros": capital_ship("Moros", 19724, 17887, 3000, 3.5, "Dreadnought"),
    "phoenix": capital_ship("Phoenix", 19726, 17888, 3000, 3.5, "Dreadnought"),
    "naglfar": capital_ship("Naglfar", 19722, 17889, 3000, 3.5, "Dreadnought"),
    "chemosh": capital_ship("Chemosh", 42243, 16274, 3000, 3.5, "Dreadnought"),
    "vehement": capital_ship("Vehement", 42124, 17887, 3000, 3.5, "Dreadnought"),
    "caiman": capital_ship("Caiman", 45647, 17888, 3000, 3.5, "Dreadnought"),
    "zirnitra": capital_ship("Zirnitra", 52907, 16274, 3000, 3.5, "Dreadnought"),
    "sarathiel": capital_ship("Sarathiel", 87381, 17889, 3000, 3.5, "Dreadnought"),
    "revelation navy issue": capital_ship("Revelation Navy Issue", 73790, 16274, 3000, 3.5, "Dreadnought"),
    "moros navy issue": capital_ship("Moros Navy Issue", 73792, 17887, 3000, 3.5, "Dreadnought"),
    "phoenix navy issue": capital_ship("Phoenix Navy Issue", 73793, 17888, 3000, 3.5, "Dreadnought"),
    "naglfar fleet issue": capital_ship("Naglfar Fleet Issue", 73787, 17889, 3000, 3.5, "Dreadnought"),
    "bane": capital_ship("Bane", 77283, 16274, 3000, 4.0, "Lancer Dreadnought"),
    "hubris": capital_ship("Hubris", 77281, 17887, 3000, 4.0, "Lancer Dreadnought"),
    "karura": capital_ship("Karura", 77284, 17888, 3000, 4.0, "Lancer Dreadnought"),
    "valravn": capital_ship("Valravn", 77288, 17889, 3000, 4.0, "Lancer Dreadnought"),
    "apostle": capital_ship("Apostle", 37604, 16274, 3000, 3.5, "Force Auxiliary"),
    "minokawa": capital_ship("Minokawa", 37605, 17888, 3000, 3.5, "Force Auxiliary"),
    "lif": capital_ship("Lif", 37606, 17889, 3000, 3.5, "Force Auxiliary"),
    "ninazu": capital_ship("Ninazu", 37607, 17887, 3000, 3.5, "Force Auxiliary"),
    "dagon": capital_ship("Dagon", 42242, 16274, 3000, 3.5, "Force Auxiliary"),
    "loggerhead": capital_ship("Loggerhead", 45645, 17888, 3000, 3.5, "Force Auxiliary"),
    "aeon": capital_ship("Aeon", 23919, 16274, 3000, 3.0, "Supercarrier"),
    "wyvern": capital_ship("Wyvern", 23917, 17888, 3000, 3.0, "Supercarrier"),
    "hel": capital_ship("Hel", 22852, 17889, 3000, 3.0, "Supercarrier"),
    "nyx": capital_ship("Nyx", 23913, 17887, 3000, 3.0, "Supercarrier"),
    "revenant": capital_ship("Revenant", 3514, 16274, 3000, 3.0, "Supercarrier"),
    "vendetta": capital_ship("Vendetta", 42125, 17887, 3000, 3.0, "Supercarrier"),
    "avatar": capital_ship("Avatar", 11567, 16274, 3000, 3.0, "Titan"),
    "leviathan": capital_ship("Leviathan", 3764, 17888, 3000, 3.0, "Titan"),
    "ragnarok": capital_ship("Ragnarok", 23773, 17889, 3000, 3.0, "Titan"),
    "erebus": capital_ship("Erebus", 671, 17887, 3000, 3.0, "Titan"),
    "vanquisher": capital_ship("Vanquisher", 42126, 17887, 3000, 3.0, "Titan"),
    "molok": capital_ship("Molok", 42241, 16274, 3000, 3.0, "Titan"),
    "komodo": capital_ship("Komodo", 45649, 17888, 3000, 3.0, "Titan"),
    "azariel": capital_ship("Azariel", 78576, 17889, 3000, 3.0, "Titan"),
}
# User-provided/public JF station-operation guidance, rendered as EQM data rather than copied artwork.
# The placement note is intentionally conservative; actual cyno placement depends on station geometry.
STATION_CYNO_GUIDE: dict[str, dict[str, Any]] = {
    "Amarr Industrial Station": {"range_km": 2, "risk": "dangerous", "note": "Very tight docking radius. Use practiced bookmarks only."},
    "Minmatar Research Station": {"range_km": 3, "risk": "dangerous", "note": "Very tight docking radius. Use practiced bookmarks only."},
    "Minmatar Station": {"range_km": 3, "risk": "dangerous", "note": "Very tight docking radius. Use practiced bookmarks only."},
    "Gallente Industrial Station": {"range_km": 5, "risk": "dangerous", "note": "Small margin for error and bump geometry."},
    "Minmatar Hub": {"range_km": 5, "risk": "dangerous", "note": "Small margin for error and bump geometry."},
    "Minmatar Trade Post": {"range_km": 5, "risk": "dangerous", "note": "Small margin for error and bump geometry."},
    "Caldari Logistics Station": {"range_km": 10, "risk": "questionable", "note": "Usable with care; verify cyno bookmark."},
    "Caldari Station Hub": {"range_km": 10, "risk": "questionable", "note": "Usable with care; verify cyno bookmark."},
    "Amarr Standard Station": {"range_km": 12.5, "risk": "questionable", "note": "Moderate docking radius; station geometry still matters."},
    "Gallente Administrative Station": {"range_km": 12.5, "risk": "questionable", "note": "Moderate docking radius; station geometry still matters."},
    "Amarr Trade Post": {"range_km": 15, "risk": "questionable", "note": "Moderate docking radius; station geometry still matters."},
    "Gallente Trading Hub": {"range_km": 15, "risk": "questionable", "note": "Moderate docking radius; station geometry still matters."},
    "Minmatar Military Station": {"range_km": 15, "risk": "questionable", "note": "Moderate docking radius; station geometry still matters."},
    "Caldari Military Station": {"range_km": 17.5, "risk": "questionable", "note": "Careful but workable; verify station model."},
    "Amarr Mining Station": {"range_km": 20, "risk": "safer", "note": "Friendlier docking radius, still use a proper cyno bookmark."},
    "Caldari Mining Station": {"range_km": 20, "risk": "safer", "note": "Friendlier docking radius, still use a proper cyno bookmark."},
    "Caldari Research Station": {"range_km": 20, "risk": "safer", "note": "Friendlier docking radius, still use a proper cyno bookmark."},
    "Minmatar Industrial Station": {"range_km": 20, "risk": "safer", "note": "Friendlier docking radius, still use a proper cyno bookmark."},
    "Caldari Food Processing Plant Station": {"range_km": 25, "risk": "safer", "note": "Generous docking radius."},
    "Gallente Logistics Station": {"range_km": 25, "risk": "safer", "note": "Generous docking radius."},
    "Gallente Military Station": {"range_km": 25, "risk": "safer", "note": "Generous docking radius."},
    "Gallente Mining Station": {"range_km": 25, "risk": "safer", "note": "Generous docking radius."},
    "Amarr Research Station": {"range_km": 30, "risk": "safer", "note": "Generous docking radius."},
    "Gallente Station Hub": {"range_km": 30, "risk": "safer", "note": "Generous docking radius."},
    "Amarr Station Hub": {"range_km": 40, "risk": "safer", "note": "Very forgiving docking radius."},
    "Amarr Station Military": {"range_km": 40, "risk": "safer", "note": "Very forgiving docking radius."},
    "Caldari Administrative Station": {"range_km": 40, "risk": "safer", "note": "Very forgiving docking radius."},
    "Caldari Trading Station": {"range_km": 40, "risk": "safer", "note": "Very forgiving docking radius."},
    "Gallente Research Station": {"range_km": 40, "risk": "safer", "note": "Very forgiving docking radius."},
    "Minmatar Mining Station": {"range_km": 50, "risk": "safer", "note": "Most forgiving docking radius in the guide."},
}

STATION_CYNO_REFERENCE_PAGES: dict[str, list[int]] = {
    "Amarr Industrial Station": [5],
    "Amarr Mining Station": [6],
    "Amarr Research Station": [7],
    "Amarr Standard Station": [8],
    "Amarr Station Hub": [9],
    "Amarr Station Military": [10],
    "Amarr Trade Post": [11],
    "Caldari Administrative Station": [12],
    "Caldari Food Processing Plant Station": [13],
    "Caldari Logistics Station": [14, 15],
    "Caldari Military Station": [16],
    "Caldari Mining Station": [17],
    "Caldari Research Station": [18],
    "Caldari Station Hub": [19],
    "Caldari Trading Station": [20],
    "Gallente Administrative Station": [21, 22],
    "Gallente Industrial Station": [23, 24],
    "Gallente Logistics Station": [25],
    "Gallente Military Station": [26],
    "Gallente Mining Station": [27],
    "Gallente Research Station": [28],
    "Gallente Station Hub": [29],
    "Gallente Trading Hub": [30],
    "Minmatar Hub": [31, 32],
    "Minmatar Industrial Station": [33],
    "Minmatar Military Station": [34],
    "Minmatar Mining Station": [35],
    "Minmatar Research Station": [36, 37],
    "Minmatar Station": [38, 39],
    "Minmatar Trade Post": [40, 41],
}


def clamp_skill(value: int) -> int:
    return max(0, min(5, int(value)))


def ship_config(ship_name: str) -> JumpFreighterShip:
    key = ship_name.strip().lower()
    if key not in JUMP_FREIGHTERS:
        raise ValueError(f"Unknown capital jump ship '{ship_name}'")
    return JUMP_FREIGHTERS[key]


def jump_range_ly(ship: JumpFreighterShip, jdc_level: int) -> float:
    return ship.base_range_ly * (1 + clamp_skill(jdc_level) * JDC_RANGE_BONUS_PER_LEVEL)


def fuel_for_jump(distance_ly: float, ship: JumpFreighterShip, jfc_level: int) -> int:
    multiplier = max(0.5, 1 - clamp_skill(jfc_level) * JFC_FUEL_REDUCTION_PER_LEVEL)
    return int(ceil(distance_ly * ship.fuel_per_light_year * multiplier))


def distance_ly(a: EveSystem, b: EveSystem) -> float:
    if None in (a.x, a.y, a.z, b.x, b.y, b.z):
        raise ValueError("Both systems need SDE coordinates for jump plotting")
    meters = sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)
    return meters / LIGHT_YEAR_METERS


def cyno_eligible(system: EveSystem) -> bool:
    return security_band(system.security_status) != "highsec"


def _known_space_systems(db: Session) -> list[EveSystem]:
    return db.scalars(
        select(EveSystem)
        .where(EveSystem.system_id < 31000000)
        .where(EveSystem.x.is_not(None), EveSystem.y.is_not(None), EveSystem.z.is_not(None))
    ).all()


def _npc_station_system_ids(db: Session) -> set[int]:
    return set(db.scalars(select(EveStation.system_id).where(EveStation.system_id.is_not(None)).distinct()).all())


def _station_safety_system_ids(db: Session, station_safety: str) -> set[int]:
    mode = station_safety.strip().lower()
    if mode == "any":
        return _npc_station_system_ids(db)
    if mode not in {"avoid_red_only", "green"}:
        raise ValueError("Unknown station safety filter. Use any, avoid_red_only, or green.")

    stations = db.scalars(
        select(EveStation)
        .options(selectinload(EveStation.station_type), selectinload(EveStation.system))
        .where(EveStation.system_id.is_not(None))
    ).all()
    risks_by_system: dict[int, set[str]] = {}
    for station in stations:
        type_name = station.station_type.name if station.station_type else (f"Type {station.type_id}" if station.type_id else None)
        risk = station_cyno_guidance(type_name).get("risk", "unknown")
        risks_by_system.setdefault(station.system_id, set()).add(str(risk))

    if mode == "green":
        return {system_id for system_id, risks in risks_by_system.items() if "safer" in risks}
    return {system_id for system_id, risks in risks_by_system.items() if risks - {"dangerous"}}


def _station_safety_label(station_safety: str) -> str:
    return {
        "any": "Any NPC station",
        "avoid_red_only": "Avoid red-only systems",
        "green": "Only green stations",
    }.get(station_safety.strip().lower(), station_safety)


def _grid_key(system: EveSystem, cell_meters: float) -> tuple[int, int, int]:
    return (floor((system.x or 0) / cell_meters), floor((system.y or 0) / cell_meters), floor((system.z or 0) / cell_meters))


def _neighbor_systems(system: EveSystem, grid: dict[tuple[int, int, int], list[EveSystem]], cell_meters: float) -> list[EveSystem]:
    sx, sy, sz = _grid_key(system, cell_meters)
    candidates: list[EveSystem] = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                candidates.extend(grid.get((sx + dx, sy + dy, sz + dz), []))
    return candidates


def _jump_path(db: Session, origin: EveSystem, destination: EveSystem, max_range_ly: float, station_safety: str = "any", avoid_system_ids: set[int] | None = None) -> list[int]:
    if origin.system_id == destination.system_id:
        return [origin.system_id]
    if not cyno_eligible(destination):
        raise ValueError("Jump freighter destination must be lowsec/nullsec for a cyno. Use a nearby cyno system, then plan the gate leg separately.")
    station_system_ids = _npc_station_system_ids(db)
    if destination.system_id not in station_system_ids:
        raise ValueError(f"{destination.name} has no imported NPC stations. Jump freighter cyno targets must have an NPC station; choose a nearby station system and gate the final leg.")
    allowed_station_system_ids = _station_safety_system_ids(db, station_safety)
    if destination.system_id not in allowed_station_system_ids:
        raise ValueError(f"{destination.name} has NPC stations, but none match the station safety filter: {_station_safety_label(station_safety)}.")
    avoid_system_ids = set(avoid_system_ids or set())
    avoid_system_ids.discard(origin.system_id)
    avoid_system_ids.discard(destination.system_id)

    systems = _known_space_systems(db)
    by_id = {system.system_id: system for system in systems}
    by_id[origin.system_id] = origin
    by_id[destination.system_id] = destination
    max_meters = max_range_ly * LIGHT_YEAR_METERS
    grid: dict[tuple[int, int, int], list[EveSystem]] = {}
    for system in by_id.values():
        grid.setdefault(_grid_key(system, max_meters), []).append(system)

    distances: dict[int, float] = {origin.system_id: 0.0}
    parent: dict[int, int | None] = {origin.system_id: None}
    queue: list[tuple[float, float, int]] = [(0.0, 0.0, origin.system_id)]
    visited: set[int] = set()

    while queue:
        _, current_cost, current_id = heappop(queue)
        if current_id in visited:
            continue
        visited.add(current_id)
        if current_id == destination.system_id:
            break
        current = by_id[current_id]
        for candidate in _neighbor_systems(current, grid, max_meters):
            if candidate.system_id == current_id or candidate.system_id in visited:
                continue
            if candidate.system_id in avoid_system_ids:
                continue
            if candidate.system_id != destination.system_id and not cyno_eligible(candidate):
                continue
            if candidate.system_id != origin.system_id and candidate.system_id not in allowed_station_system_ids:
                continue
            jump_distance = distance_ly(current, candidate)
            if jump_distance > max_range_ly:
                continue
            next_cost = current_cost + jump_distance
            if next_cost < distances.get(candidate.system_id, float("inf")):
                distances[candidate.system_id] = next_cost
                parent[candidate.system_id] = current_id
                # Bias toward destination to keep routes natural while still preserving distance cost.
                heappush(queue, (next_cost + distance_ly(candidate, destination) * 0.01, next_cost, candidate.system_id))

    if destination.system_id not in parent:
        raise ValueError(f"No jump route found within {max_range_ly:.2f} LY range. Try higher JDC or a different midpoint.")

    path: list[int] = []
    cursor: int | None = destination.system_id
    while cursor is not None:
        path.append(cursor)
        cursor = parent[cursor]
    path.reverse()
    return path


def station_cyno_guidance(station_type_name: str | None) -> dict[str, Any]:
    if not station_type_name:
        return {"risk": "unknown", "range_km": None, "note": "No station type imported yet.", "reference_links": []}
    guide = STATION_CYNO_GUIDE.get(station_type_name)
    if guide is None:
        return {"risk": "unknown", "range_km": None, "note": "No station cyno guidance recorded for this station type yet.", "reference_links": []}
    result = dict(guide)
    pages = STATION_CYNO_REFERENCE_PAGES.get(station_type_name, [])
    result["reference_links"] = [
        {
            "label": f"Cyno placement {index + 1}" if len(pages) > 1 else "Cyno placement",
            "url": f"/cyno-guides/station-cyno-guide-page-{page:02d}.png",
        }
        for index, page in enumerate(pages)
    ]
    return result


def _station_roman_numeral(value: int | None) -> str | None:
    if value is None or value <= 0:
        return None
    numerals: tuple[tuple[int, str], ...] = (
        (1000, "M"),
        (900, "CM"),
        (500, "D"),
        (400, "CD"),
        (100, "C"),
        (90, "XC"),
        (50, "L"),
        (40, "XL"),
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    )
    remaining = value
    output: list[str] = []
    for number, symbol in numerals:
        while remaining >= number:
            output.append(symbol)
            remaining -= number
    return "".join(output)


def station_display_name(station: EveStation, type_name: str | None) -> str:
    generic_names = {name for name in (type_name, station.operation_name, f"Station {station.station_id}") if name}
    if station.name and station.name not in generic_names and not station.name.startswith("Type "):
        return station.name

    celestial = _station_roman_numeral(station.celestial_index)
    system_name = station.system.name if station.system else None
    if celestial and system_name:
        location = f"{system_name} {celestial}"
        if station.orbit_index is not None:
            location = f"{location} - Moon {station.orbit_index}"
        suffix_parts = [part for part in (station.owner_name, station.operation_name) if part]
        suffix = " ".join(suffix_parts) or type_name
        return f"{location} - {suffix}" if suffix else location

    return station.name or type_name or f"Station {station.station_id}"

def serialize_station(station: EveStation) -> dict[str, Any]:
    type_name = station.station_type.name if station.station_type else (f"Type {station.type_id}" if station.type_id else None)
    label = station_display_name(station, type_name)
    return {
        "station_id": station.station_id,
        "name": label,
        "type_id": station.type_id,
        "type_name": type_name,
        "operation_id": station.operation_id,
        "operation_name": station.operation_name,
        "orbit_id": station.orbit_id,
        "cyno_guidance": station_cyno_guidance(type_name),
    }


def stations_by_system(db: Session, system_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    if not system_ids:
        return {}
    stations = db.scalars(
        select(EveStation)
        .options(selectinload(EveStation.station_type), selectinload(EveStation.system))
        .where(EveStation.system_id.in_(system_ids))
        .order_by(EveStation.system_id, EveStation.operation_name, EveStation.station_id)
    ).all()
    result: dict[int, list[dict[str, Any]]] = {}
    for station in stations:
        result.setdefault(station.system_id, []).append(serialize_station(station))
    return result


def route_map_context(db: Session, route_systems: list[EveSystem], gate_hops: int = 1, max_systems: int = 160) -> dict[str, Any]:
    route_ids = [system.system_id for system in route_systems]
    if not route_ids:
        return {"gate_hops": 0, "truncated": False, "systems": [], "stargates": []}

    hop_limit = max(0, min(2, int(gate_hops)))
    context_ids = set(route_ids)
    frontier = set(route_ids)
    truncated = False

    for _ in range(hop_limit):
        if not frontier:
            break
        rows = db.execute(
            select(EveStargate.system_id, EveStargate.destination_system_id)
            .where(EveStargate.destination_system_id.is_not(None))
            .where(EveStargate.system_id.in_(frontier))
        ).all()
        next_frontier: set[int] = set()
        for _, destination_system_id in rows:
            if destination_system_id is None or destination_system_id in context_ids:
                continue
            if len(context_ids) >= max_systems:
                truncated = True
                continue
            context_ids.add(destination_system_id)
            next_frontier.add(destination_system_id)
        frontier = next_frontier

    systems = db.scalars(
        select(EveSystem)
        .options(selectinload(EveSystem.constellation).selectinload(EveConstellation.region))
        .where(EveSystem.system_id.in_(context_ids))
        .where(EveSystem.x.is_not(None), EveSystem.y.is_not(None), EveSystem.z.is_not(None))
    ).all()
    systems_by_id = {system.system_id: system for system in systems}
    visible_ids = set(systems_by_id)

    stargate_rows = db.execute(
        select(EveStargate.system_id, EveStargate.destination_system_id)
        .where(EveStargate.system_id.in_(visible_ids))
        .where(EveStargate.destination_system_id.in_(visible_ids))
    ).all()
    seen_edges: set[tuple[int, int]] = set()
    stargates: list[dict[str, int]] = []
    for system_id, destination_system_id in stargate_rows:
        if destination_system_id is None or system_id == destination_system_id:
            continue
        edge = tuple(sorted((system_id, destination_system_id)))
        if edge in seen_edges:
            continue
        seen_edges.add(edge)
        stargates.append({"from_system_id": edge[0], "to_system_id": edge[1]})

    ordered_systems = sorted(systems, key=lambda system: (system.system_id not in route_ids, system.name.lower()))
    return {
        "gate_hops": hop_limit,
        "truncated": truncated,
        "systems": [
            {**serialize_system(system), "on_route": system.system_id in route_ids}
            for system in ordered_systems
        ],
        "stargates": sorted(stargates, key=lambda edge: (edge["from_system_id"], edge["to_system_id"])),
    }

def _jump_activity_hours(hours: int) -> int:
    return max(1, min(24, int(hours)))


def _jump_observation_bucket(now: datetime | None = None) -> datetime:
    observed = now or datetime.now(UTC)
    return observed.replace(minute=0, second=0, microsecond=0)


def _fetch_system_jump_counts() -> dict[int, int]:
    try:
        with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=12.0, follow_redirects=True) as client:
            response = client.get(ESI_SYSTEM_JUMPS_URL)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError):
        return {}
    counts: dict[int, int] = {}
    for row in payload if isinstance(payload, list) else []:
        try:
            counts[int(row["system_id"])] = int(row.get("ship_jumps") or 0)
        except (KeyError, TypeError, ValueError):
            continue
    return counts


def refresh_system_jump_observations(db: Session, system_ids: list[int]) -> dict[str, Any]:
    unique_ids = sorted({int(system_id) for system_id in system_ids if system_id})
    if not unique_ids:
        return {"refreshed": False, "observed_at": None, "system_count": 0}

    counts = _fetch_system_jump_counts()
    if not counts:
        return {"refreshed": False, "observed_at": None, "system_count": 0}

    observed_at = _jump_observation_bucket()
    existing = {
        row.system_id: row
        for row in db.scalars(
            select(SystemJumpObservation)
            .where(SystemJumpObservation.system_id.in_(unique_ids))
            .where(SystemJumpObservation.observed_at == observed_at)
        ).all()
    }
    written = 0
    for system_id in unique_ids:
        ship_jumps = int(counts.get(system_id, 0))
        row = existing.get(system_id)
        if row:
            row.ship_jumps = ship_jumps
            row.cached_at = datetime.now(UTC)
        else:
            db.add(SystemJumpObservation(system_id=system_id, observed_at=observed_at, ship_jumps=ship_jumps))
        written += 1
    db.commit()
    return {"refreshed": True, "observed_at": observed_at.isoformat(), "system_count": written}


def jump_activity_summary(db: Session, system_id: int, hours: int = 6) -> dict[str, Any]:
    window_hours = _jump_activity_hours(hours)
    since = datetime.now(UTC) - timedelta(hours=window_hours)
    rows = db.scalars(
        select(SystemJumpObservation)
        .where(SystemJumpObservation.system_id == system_id)
        .where(SystemJumpObservation.observed_at >= since)
        .order_by(SystemJumpObservation.observed_at.desc())
    ).all()
    total_jumps = sum(row.ship_jumps for row in rows)
    observations = len(rows)
    coverage = observations / max(1, window_hours)
    if observations == 0:
        confidence = "none"
    elif coverage >= 0.66:
        confidence = "high"
    elif coverage >= 0.33:
        confidence = "medium"
    else:
        confidence = "low"
    if total_jumps >= 1000 or (window_hours and total_jumps / window_hours >= 150):
        activity_label = "very active"
    elif total_jumps >= 250 or (window_hours and total_jumps / window_hours >= 40):
        activity_label = "active"
    elif total_jumps >= 50 or (window_hours and total_jumps / window_hours >= 10):
        activity_label = "moderate"
    else:
        activity_label = "quiet"
    latest = rows[0].observed_at.isoformat() if rows else None
    return {
        "hours": window_hours,
        "total_jumps": total_jumps,
        "jumps_per_hour": round(total_jumps / max(1, window_hours), 1),
        "observations": observations,
        "confidence": confidence,
        "activity_label": activity_label,
        "latest_observed_at": latest,
    }

def _kill_filter_label(kill_filter: str) -> str:
    return "Industrial kills only" if kill_filter == "industrial" else "All kills"


def kill_summary(db: Session, system_id: int, hours: int = 24, kill_filter: str = "industrial") -> dict[str, Any]:
    mode = kill_filter.strip().lower()
    if mode not in {"industrial", "all"}:
        raise ValueError("Unknown kill filter. Use industrial or all.")
    model = SystemIndustrialKillObservation if mode == "industrial" else SystemPvpKillObservation
    since = datetime.now(UTC) - timedelta(hours=max(1, min(hours, 168)))
    rows = db.scalars(
        select(model)
        .where(model.system_id == system_id)
        .where(model.killmail_time >= since)
        .order_by(model.killmail_time.desc())
        .limit(5)
    ).all()
    return {
        "hours": hours,
        "filter": {"mode": mode, "label": _kill_filter_label(mode)},
        "count": len(rows),
        "latest_killmail_time": rows[0].killmail_time.isoformat() if rows else None,
        "sample_killmails": [
            {
                "killmail_id": row.killmail_id,
                "killmail_time": row.killmail_time.isoformat(),
                "zkb_url": row.zkb_url,
                "victim_hull": row.victim_hull,
                "smartbomb_used": row.smartbomb_used,
                "victim_character_id": row.victim_character_id,
                "victim_character_name": row.victim_character_name,
                "victim_corporation_id": row.victim_corporation_id,
                "victim_corporation_name": row.victim_corporation_name,
                "victim_alliance_id": row.victim_alliance_id,
                "victim_alliance_name": row.victim_alliance_name,
                "attacker_count": row.attacker_count,
                "location_kind": row.location_kind,
                "location_name": row.location_name,
                "final_blow_character_id": row.final_blow_character_id,
                "final_blow_character_name": row.final_blow_character_name,
                "final_blow_corporation_id": row.final_blow_corporation_id,
                "final_blow_corporation_name": row.final_blow_corporation_name,
                "final_blow_alliance_id": row.final_blow_alliance_id,
                "final_blow_alliance_name": row.final_blow_alliance_name,
                "final_blow_ship_type_name": row.final_blow_ship_type_name,
            }
            for row in rows
        ],
    }


def industrial_kill_summary(db: Session, system_id: int, hours: int = 24) -> dict[str, Any]:
    return kill_summary(db, system_id, hours, "industrial")


def plan_jump_freighter_route(
    db: Session,
    origin_query: str,
    destination_query: str,
    *,
    ship_name: str,
    jump_drive_calibration: int = 5,
    jump_fuel_conservation: int = 5,
    context_gate_hops: int = 1,
    station_safety: str = "any",
    kill_filter: str = "industrial",
    jump_activity_hours: int = 6,
    avoid_system_queries: list[str] | None = None,
) -> dict[str, Any]:
    ship = ship_config(ship_name)
    origin = resolve_system(db, origin_query)
    destination = resolve_system(db, destination_query)
    max_range = jump_range_ly(ship, jump_drive_calibration)
    station_safety = station_safety.strip().lower()
    kill_filter = kill_filter.strip().lower()
    if kill_filter not in {"industrial", "all"}:
        raise ValueError("Unknown kill filter. Use industrial or all.")
    jump_activity_hours = _jump_activity_hours(jump_activity_hours)
    avoid_systems: list[EveSystem] = []
    for query in avoid_system_queries or []:
        cleaned = query.strip()
        if not cleaned:
            continue
        system = resolve_system(db, cleaned)
        if system.system_id not in {origin.system_id, destination.system_id} and all(existing.system_id != system.system_id for existing in avoid_systems):
            avoid_systems.append(system)

    path_ids = _jump_path(db, origin, destination, max_range, station_safety, {system.system_id for system in avoid_systems})
    systems = db.scalars(
        select(EveSystem)
        .options(selectinload(EveSystem.constellation).selectinload(EveConstellation.region))
        .where(EveSystem.system_id.in_(path_ids))
    ).all()
    systems_by_id = {system.system_id: system for system in systems}
    ordered = [systems_by_id.get(system_id) or db.get(EveSystem, system_id) for system_id in path_ids]
    ordered = [system for system in ordered if system is not None]
    station_map = stations_by_system(db, [system.system_id for system in ordered])
    jump_activity_cache = refresh_system_jump_observations(db, [system.system_id for system in ordered])

    jumps: list[dict[str, Any]] = []
    total_distance = 0.0
    total_fuel = 0
    for index in range(1, len(ordered)):
        start = ordered[index - 1]
        end = ordered[index]
        jump_distance = distance_ly(start, end)
        fuel = fuel_for_jump(jump_distance, ship, jump_fuel_conservation)
        total_distance += jump_distance
        total_fuel += fuel
        jumps.append(
            {
                "jump_index": index,
                "from_system": serialize_system(start),
                "to_system": serialize_system(end),
                "distance_ly": round(jump_distance, 3),
                "fuel_units": fuel,
                "cyno_eligible": cyno_eligible(end),
                "stations": station_map.get(end.system_id, []),
                "industrial_kills_24h": industrial_kill_summary(db, end.system_id, 24),
                "kills_24h": kill_summary(db, end.system_id, 24, kill_filter),
                "jump_activity": jump_activity_summary(db, end.system_id, jump_activity_hours),
            }
        )

    return {
        "origin": serialize_system(ordered[0]),
        "destination": serialize_system(ordered[-1]),
        "ship": {
            "name": ship.name,
            "type_id": ship.type_id,
            "fuel_type_id": ship.fuel_type_id,
            "fuel_type_name": ship.fuel_type_name,
            "base_fuel_per_light_year": ship.fuel_per_light_year,
            "base_range_ly": ship.base_range_ly,
            "ship_class": ship.ship_class,
        },
        "skills": {
            "jump_drive_calibration": clamp_skill(jump_drive_calibration),
            "jump_fuel_conservation": clamp_skill(jump_fuel_conservation),
        },
        "max_range_ly": round(max_range, 2),
        "jump_count": len(jumps),
        "total_distance_ly": round(total_distance, 3),
        "total_fuel_units": total_fuel,
        "station_safety": {"mode": station_safety, "label": _station_safety_label(station_safety)},
        "kill_filter": {"mode": kill_filter, "label": _kill_filter_label(kill_filter)},
        "jump_activity": {"hours": jump_activity_hours, "cache": jump_activity_cache},
        "avoided_systems": [serialize_system(system) for system in avoid_systems],
        "jumps": jumps,
        "map_context": route_map_context(db, ordered, gate_hops=context_gate_hops),
        "station_cyno_guide": [
            {"station_type": name, **guide} for name, guide in sorted(STATION_CYNO_GUIDE.items(), key=lambda item: (item[1]["range_km"], item[0]))
        ],
        "notes": [
            "Highsec origins are allowed; every jump target must be low/null and have an imported NPC station.",
            f"Station safety filter: {_station_safety_label(station_safety)}.",
            f"Kill display: {_kill_filter_label(kill_filter)}.",
            f"Observed activity window: {jump_activity_hours}h; confidence depends on hourly samples collected by EQM.",
            f"Avoiding {len(avoid_systems)} system{'' if len(avoid_systems) == 1 else 's'}.",
            "Station guidance is operational reference data. Verify bookmarks and station geometry before risking a live capital jump.",
        ],
    }




