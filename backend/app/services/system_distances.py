from __future__ import annotations

import asyncio
import math
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EsiToken, EveStargate, EveStation, EveSystem, Location
from app.models.enums import LocationKind
from app.models.system_objects import EveSystemObject, NavigationStructure, SystemObjectSync
from app.services.esi_client import EsiClient

ORDER = {"gate": 0, "station": 1, "upwell": 2, "planet": 3, "moon": 4, "belt": 5, "star": 6}
STRUCTURE_SCOPE = "esi-universe.read_structures.v1"


def position(payload: dict) -> dict[str, float | None]:
    raw = payload.get("position") or {}
    result = {}
    for axis in ("x", "y", "z"):
        value = raw.get(axis) if isinstance(raw, dict) else None
        try:
            value = float(value) if value is not None else None
        except (TypeError, ValueError):
            value = None
        result[axis] = value if value is not None and math.isfinite(value) else None
    return result


def store_public(db: Session, object_id: int, system_id: int, kind: str, name: str, coords: dict, source: str):
    row = db.get(EveSystemObject, object_id)
    if row is None:
        row = EveSystemObject(object_id=object_id)
        db.add(row)
    row.system_id, row.kind, row.name, row.source = system_id, kind, name, source
    for axis in ("x", "y", "z"):
        setattr(row, axis, coords.get(axis))
    return row


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def serialize(object_id: int, name: str, kind: str, row, source: str) -> dict:
    coords = {axis: getattr(row, axis) for axis in ("x", "y", "z")}
    valid = all(v is not None and math.isfinite(v) for v in coords.values())
    return {"object_id": str(object_id), "name": name, "kind": kind, "position": coords if valid else None, "source": source}


def eligible_tokens(db: Session, user_id: int) -> list[EsiToken]:
    return [t for t in db.scalars(select(EsiToken).where(EsiToken.user_id == user_id, EsiToken.revoked_at.is_(None))).all()
            if STRUCTURE_SCOPE in t.scopes.split()]


def system_objects(db: Session, system_id: int, user_id: int) -> dict:
    system = db.get(EveSystem, system_id)
    if not system:
        raise HTTPException(404, "Solar system not found. Import the SDE map first.")
    rows = {}
    for row in db.scalars(select(EveSystemObject).where(EveSystemObject.system_id == system_id)):
        rows[row.object_id] = serialize(row.object_id, row.name, row.kind, row, row.source)
    for row in db.scalars(select(EveStargate).where(EveStargate.system_id == system_id)):
        destination = db.get(EveSystem, row.destination_system_id) if row.destination_system_id else None
        item = serialize(row.stargate_id, f"Stargate ({destination.name if destination else row.stargate_id})", "gate", row, "sde")
        if item["position"] is not None or row.stargate_id not in rows:
            rows[row.stargate_id] = item
    for row in db.scalars(select(EveStation).where(EveStation.system_id == system_id)):
        item = serialize(row.station_id, row.name or f"Station {row.station_id}", "station", row, "sde")
        if item["position"] is not None or row.station_id not in rows:
            rows[row.station_id] = item
    token_ids = [t.id for t in eligible_tokens(db, user_id)]
    now = datetime.now(timezone.utc)
    if token_ids:
        for row in db.scalars(select(NavigationStructure).where(NavigationStructure.token_id.in_(token_ids), NavigationStructure.system_id == system_id, NavigationStructure.expires_at > now)):
            rows[row.structure_id] = serialize(row.structure_id, row.name, "upwell", row, "esi")
    cache = db.get(SystemObjectSync, system_id)
    return {"system_id": system_id, "system_name": system.name,
            "objects": sorted(rows.values(), key=lambda r: (ORDER.get(r["kind"], 9), r["name"].casefold(), r["object_id"])),
            "checked_at": utc(cache.checked_at).isoformat() if cache else None,
            "message": cache.message if cache else "SDE positions loaded. Refresh ESI objects to fill missing celestial data.",
            "coverage_note": "Static objects and known accessible Upwell structures only. ESI does not enumerate every anchored object. Private structure positions are cached for up to one hour; access and docking are not guaranteed."}


async def refresh_public(db: Session, system_id: int, client: EsiClient) -> str:
    now = datetime.now(timezone.utc)
    cache = db.get(SystemObjectSync, system_id)
    if cache and utc(cache.expires_at) > now:
        return cache.message
    manifest = await client.get(f"/universe/systems/{system_id}/")
    tasks: list[tuple[int, str, str]] = []
    for key, kind, endpoint in (("stargates", "gate", "stargates"), ("stations", "station", "stations")):
        tasks.extend((int(i), kind, endpoint) for i in manifest.get(key, []))
    for planet in manifest.get("planets", []):
        tasks.append((int(planet["planet_id"]), "planet", "planets"))
        tasks.extend((int(i), "moon", "moons") for i in planet.get("moons", []))
        tasks.extend((int(i), "belt", "asteroid_belts") for i in planet.get("asteroid_belts", []))
    # A star's local origin is zero; do not use the system's galaxy coordinates.
    if manifest.get("star_id"):
        store_public(db, int(manifest["star_id"]), system_id, "star", f"{manifest['name']} — Sun", dict(x=0., y=0., z=0.), "esi")
    semaphore = asyncio.Semaphore(6)
    async def fetch(entry):
        object_id, kind, endpoint = entry
        async with semaphore:
            try:
                return entry, await client.get(f"/universe/{endpoint}/{object_id}/")
            except (HTTPException, httpx.HTTPError):
                return entry, None
    results = await asyncio.gather(*(fetch(entry) for entry in tasks))
    failures = 0
    for (object_id, kind, _), payload in results:
        if payload is None or int(payload.get("system_id", payload.get("solar_system_id", system_id))) != system_id or any(v is None for v in position(payload).values()):
            failures += 1
            continue
        store_public(db, object_id, system_id, kind, payload.get("name", f"{kind.title()} {object_id}"), position(payload), "esi")
    message = f"ESI checked {len(tasks)} static objects; {failures} unavailable."
    if cache is None:
        cache = SystemObjectSync(system_id=system_id)
        db.add(cache)
    cache.checked_at, cache.expires_at, cache.message = now, now + timedelta(minutes=5 if failures else 1440), message
    db.flush()
    return message


async def refresh_structures(db: Session, system_id: int, user_id: int, structure_id: int | None = None) -> int:
    # Resolve candidates using only the viewer's own tokens, including for admins.
    from app.api.esi import refresh_access_token
    tokens = eligible_tokens(db, user_id)
    if not tokens:
        return 0
    if structure_id is not None:
        candidates = {structure_id}
    else:
        candidates = set(db.scalars(select(Location.eve_location_id).where(Location.system_id == system_id, Location.location_kind == LocationKind.STRUCTURE, Location.eve_location_id.is_not(None))))
        candidates.update(db.scalars(select(NavigationStructure.structure_id).where(NavigationStructure.system_id == system_id, NavigationStructure.token_id.in_([t.id for t in tokens]))))
    if not candidates:
        return 0
    if len(candidates) > 200:
        raise HTTPException(400, "More than 200 known structures here. Resolve individual structure IDs instead.")
    resolved = set()
    for token in tokens:
        # Persist rotated refresh tokens before making further ESI requests.
        try:
            access = await refresh_access_token(token)
            db.commit()
        except (HTTPException, httpx.HTTPError):
            continue
        client = EsiClient(access_token=access)
        semaphore = asyncio.Semaphore(6)
        async def fetch_structure(object_id):
            async with semaphore:
                try:
                    return object_id, await client.get(f"/universe/structures/{object_id}/"), None
                except (HTTPException, httpx.HTTPError) as exc:
                    return object_id, None, getattr(exc, "status_code", None)
        results = await asyncio.gather(*(fetch_structure(i) for i in sorted(candidates - resolved)))
        for object_id, payload, status in results:
            old = db.get(NavigationStructure, (token.id, object_id))
            if payload is None:
                if old and status in (401, 403, 404):
                    db.delete(old)
                continue
            if int(payload.get("solar_system_id", 0)) != system_id:
                if old:
                    db.delete(old)
                continue
            row = old or NavigationStructure(token_id=token.id, structure_id=object_id)
            row.system_id, row.name = system_id, payload["name"]
            for axis, value in position(payload).items():
                setattr(row, axis, value)
            row.checked_at = datetime.now(timezone.utc)
            row.expires_at = row.checked_at + timedelta(hours=1)
            db.add(row)
            resolved.add(object_id)
    db.commit()
    return len(resolved)
