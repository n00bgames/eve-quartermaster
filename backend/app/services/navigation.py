from __future__ import annotations

from collections.abc import Iterable
import heapq
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import EveConstellation, EveStargate, EveSystem


def security_band(security_status: float | None) -> str:
    if security_status is None:
        return "unknown"
    if security_status >= 0.45:
        return "highsec"
    if security_status > 0.0:
        return "lowsec"
    return "nullsec"


def serialize_system(system: EveSystem, jump_index: int | None = None) -> dict[str, Any]:
    constellation = system.constellation
    region = constellation.region if constellation is not None else None
    payload: dict[str, Any] = {
        "system_id": system.system_id,
        "name": system.name,
        "security_status": system.security_status,
        "security_class": system.security_class,
        "security_band": security_band(system.security_status),
        "constellation_id": constellation.constellation_id if constellation else None,
        "constellation_name": constellation.name if constellation else None,
        "region_id": region.region_id if region else None,
        "region_name": region.name if region else None,
        "x": system.x,
        "y": system.y,
        "z": system.z,
    }
    if jump_index is not None:
        payload["jump_index"] = jump_index
    return payload


def search_systems(db: Session, query: str, limit: int = 20) -> list[dict[str, Any]]:
    cleaned = query.strip()
    if not cleaned:
        return []
    numeric_id = int(cleaned) if cleaned.isdigit() else None
    clauses = [EveSystem.name.ilike(f"%{cleaned}%")]
    if numeric_id is not None:
        clauses.append(EveSystem.system_id == numeric_id)
    systems = db.scalars(
        select(EveSystem)
        .options(selectinload(EveSystem.constellation).selectinload(EveConstellation.region))
        .where(or_(*clauses))
        .order_by(func.lower(EveSystem.name))
        .limit(max(1, min(limit, 50)))
    ).all()
    return [serialize_system(system) for system in systems]


def resolve_system(db: Session, query: str) -> EveSystem:
    cleaned = query.strip()
    if not cleaned:
        raise ValueError("System name is required")
    if cleaned.isdigit():
        system = db.get(EveSystem, int(cleaned))
        if system is not None:
            return system
    exact = db.scalar(select(EveSystem).where(func.lower(EveSystem.name) == cleaned.lower()))
    if exact is not None:
        return exact
    prefix = db.scalar(select(EveSystem).where(EveSystem.name.ilike(f"{cleaned}%")).order_by(func.lower(EveSystem.name)).limit(1))
    if prefix is not None:
        return prefix
    partial = db.scalar(select(EveSystem).where(EveSystem.name.ilike(f"%{cleaned}%")).order_by(func.lower(EveSystem.name)).limit(1))
    if partial is not None:
        return partial
    raise ValueError(f"No solar system matched '{cleaned}'")


def _security_map(db: Session) -> dict[int, float | None]:
    return dict(db.execute(select(EveSystem.system_id, EveSystem.security_status)).all())


def _adjacency(db: Session, allowed_systems: set[int] | None = None) -> dict[int, list[int]]:
    rows = db.execute(select(EveStargate.system_id, EveStargate.destination_system_id)).all()
    graph: dict[int, list[int]] = {}
    for system_id, destination_system_id in rows:
        if destination_system_id is None:
            continue
        if allowed_systems is not None and (system_id not in allowed_systems or destination_system_id not in allowed_systems):
            continue
        graph.setdefault(system_id, []).append(destination_system_id)
    return graph


RouteState = tuple[int, int]


def _reconstruct_path(parent: dict[RouteState, RouteState | None], destination_state: RouteState) -> list[int]:
    path: list[int] = []
    cursor: RouteState | None = destination_state
    while cursor is not None:
        path.append(cursor[0])
        cursor = parent[cursor]
    path.reverse()
    return path


def _lowsec_chain_penalty(chain_length: int) -> int:
    if chain_length <= 0:
        return 0
    if chain_length == 1:
        return 2
    if chain_length == 2:
        return 6
    if chain_length == 3:
        return 15
    return 30 + max(0, chain_length - 4) * 10


def _route_step_cost(system_id: int, security_by_system: dict[int, float | None], prefer_safer: bool, consecutive_lowsec: int) -> tuple[int, int]:
    if not prefer_safer:
        return 1, 0
    band = security_band(security_by_system.get(system_id))
    if band == "highsec":
        return 1, 0
    if band == "lowsec":
        next_chain = consecutive_lowsec + 1
        return 1 + 8 + _lowsec_chain_penalty(next_chain), next_chain
    if band == "nullsec":
        return 1 + 60, 0
    return 1 + 10, 0


def _route_path(
    graph: dict[int, list[int]],
    origin_id: int,
    destination_id: int,
    security_by_system: dict[int, float | None],
    prefer_safer: bool,
) -> list[int] | None:
    origin_chain = 1 if prefer_safer and security_band(security_by_system.get(origin_id)) == "lowsec" else 0
    origin_state: RouteState = (origin_id, origin_chain)
    parent: dict[RouteState, RouteState | None] = {origin_state: None}
    best_cost: dict[RouteState, int] = {origin_state: 0}
    best_hops: dict[RouteState, int] = {origin_state: 0}
    queue: list[tuple[int, int, int, int]] = [(0, 0, origin_id, origin_chain)]

    while queue:
        cost, hops, current, consecutive_lowsec = heapq.heappop(queue)
        current_state: RouteState = (current, consecutive_lowsec)
        if cost != best_cost.get(current_state) or hops != best_hops.get(current_state):
            continue
        if current == destination_id:
            return _reconstruct_path(parent, current_state)

        for next_system in graph.get(current, []):
            step_cost, next_chain = _route_step_cost(next_system, security_by_system, prefer_safer, consecutive_lowsec)
            next_state: RouteState = (next_system, next_chain)
            next_cost = cost + step_cost
            next_hops = hops + 1
            known_cost = best_cost.get(next_state)
            known_hops = best_hops.get(next_state)
            if known_cost is not None and (next_cost > known_cost or (next_cost == known_cost and known_hops is not None and next_hops >= known_hops)):
                continue
            best_cost[next_state] = next_cost
            best_hops[next_state] = next_hops
            parent[next_state] = current_state
            heapq.heappush(queue, (next_cost, next_hops, next_system, next_chain))

    return None

def route_map_context(db: Session, route_system_ids: list[int], gate_hops: int = 1, max_systems: int = 180) -> dict[str, Any]:
    if not route_system_ids:
        return {"gate_hops": 0, "truncated": False, "systems": [], "stargates": []}

    route_ids = set(route_system_ids)
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
def plan_gate_route(
    db: Session,
    origin_query: str,
    destination_query: str,
    highsec_only: bool = False,
    prefer_safer: bool = False,
    avoid_system_ids: Iterable[int] | None = None,
    context_gate_hops: int = 1,
) -> dict[str, Any]:
    origin = resolve_system(db, origin_query)
    destination = resolve_system(db, destination_query)
    if origin.system_id == destination.system_id:
        system = db.scalar(
            select(EveSystem)
            .options(selectinload(EveSystem.constellation).selectinload(EveConstellation.region))
            .where(EveSystem.system_id == origin.system_id)
        )
        if system is None:
            raise ValueError("Origin system could not be loaded")
        serialized = serialize_system(system, 0)
        return {
            "origin": serialize_system(system),
            "destination": serialize_system(system),
            "jump_count": 0,
            "systems": [serialized],
            "highsec_count": 1 if serialized["security_band"] == "highsec" else 0,
            "lowsec_count": 1 if serialized["security_band"] == "lowsec" else 0,
            "nullsec_count": 1 if serialized["security_band"] == "nullsec" else 0,
            "shortest_known": True,
            "prefer_safer": prefer_safer,
            "routing_preference": "highsec_only" if highsec_only else "prefer_safer" if prefer_safer else "shortest",
            "avoided_system_ids": [],
            "map_context": route_map_context(db, [origin.system_id], context_gate_hops),
        }

    security_by_system = _security_map(db)
    allowed_systems: set[int] | None = None
    if highsec_only:
        allowed_systems = {system_id for system_id, status in security_by_system.items() if security_band(status) == "highsec"}
        if origin.system_id not in allowed_systems or destination.system_id not in allowed_systems:
            raise ValueError("Highsec-only routes require both origin and destination to be highsec systems")

    avoid = {int(system_id) for system_id in (avoid_system_ids or [])}
    avoid.discard(origin.system_id)
    avoid.discard(destination.system_id)
    if allowed_systems is None and avoid:
        allowed_systems = set(security_by_system)
    if allowed_systems is not None:
        allowed_systems -= avoid

    graph = _adjacency(db, allowed_systems)
    if not graph:
        raise ValueError("No stargate graph is loaded. Import the SDE map data first.")

    path_ids = _route_path(graph, origin.system_id, destination.system_id, security_by_system, prefer_safer and not highsec_only)
    if path_ids is None:
        route_type = "highsec-only " if highsec_only else ""
        raise ValueError(f"No {route_type}gate route found from {origin.name} to {destination.name}")

    systems = db.scalars(
        select(EveSystem)
        .options(selectinload(EveSystem.constellation).selectinload(EveConstellation.region))
        .where(EveSystem.system_id.in_(path_ids))
    ).all()
    systems_by_id = {system.system_id: system for system in systems}
    route_systems = [serialize_system(systems_by_id[system_id], index) for index, system_id in enumerate(path_ids) if system_id in systems_by_id]
    highsec_count = sum(1 for system in route_systems if system["security_band"] == "highsec")
    lowsec_count = sum(1 for system in route_systems if system["security_band"] == "lowsec")
    nullsec_count = sum(1 for system in route_systems if system["security_band"] == "nullsec")

    return {
        "origin": serialize_system(systems_by_id.get(origin.system_id, origin)),
        "destination": serialize_system(systems_by_id.get(destination.system_id, destination)),
        "jump_count": max(0, len(route_systems) - 1),
        "systems": route_systems,
        "highsec_count": highsec_count,
        "lowsec_count": lowsec_count,
        "nullsec_count": nullsec_count,
        "shortest_known": not prefer_safer or highsec_only,
        "prefer_safer": prefer_safer,
        "routing_preference": "highsec_only" if highsec_only else "prefer_safer" if prefer_safer else "shortest",
        "avoided_system_ids": sorted(avoid),
        "map_context": route_map_context(db, path_ids, context_gate_hops),
    }
