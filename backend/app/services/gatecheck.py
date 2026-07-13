from __future__ import annotations

import asyncio
import math
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from collections.abc import Iterable
from typing import Any

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import EveGroup, EveStargate, EveSystem, EveType, SystemIndustrialKillObservation, SystemKillFetchCache, SystemPvpKillObservation
from app.services.navigation import plan_gate_route, resolve_system, serialize_system

ZKILLBOARD_BASE_URL = "https://zkillboard.com/api"
ESI_BASE_URL = "https://esi.evetech.net/latest"
USER_AGENT = "EVE-Quartermaster/0.1.7-beta navigation-intel"
INDUSTRIAL_CACHE_FEED = "zkill_industrial"
PVP_CACHE_FEED = "zkill_pvp"
INDUSTRIAL_CACHE_RETENTION_DAYS = 90
INDUSTRIAL_CACHE_TTL_MINUTES = 30
LOCAL_THREAT_MAX_PILOTS = 250
LOCAL_THREAT_JOB_MAX_PILOTS = 2000
LOCAL_THREAT_ZKILL_BATCH_SIZE = 20
LOCAL_THREAT_ZKILL_CONCURRENCY = 2
INDUSTRIAL_SHIP_GROUP_NAMES = {
    "hauler",
    "industrial",
    "deep space transport",
    "blockade runner",
    "industrial command ship",
    "freighter",
    "jump freighter",
}


def parse_kill_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def killmail_value(entry: dict[str, Any]) -> float:
    zkb = entry.get("zkb") if isinstance(entry.get("zkb"), dict) else {}
    value = zkb.get("totalValue") if isinstance(zkb, dict) else 0
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None





def optional_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def killmail_war_id(kill: dict[str, Any]) -> int | None:
    zkb = kill.get("zkb") if isinstance(kill.get("zkb"), dict) else {}
    raw = kill.get("war_id") or kill.get("warID") or kill.get("war")
    if raw in (None, "") and isinstance(zkb, dict):
        raw = zkb.get("war_id") or zkb.get("warID") or zkb.get("war")
    return optional_int(raw)

def victim_ship_type_id(kill: dict[str, Any]) -> int | None:
    victim = kill.get("victim") if isinstance(kill.get("victim"), dict) else {}
    return optional_int(victim.get("ship_type_id") if isinstance(victim, dict) else None)


def industrial_ship_type_ids(db: Session, type_ids: set[int]) -> set[int]:
    if not type_ids:
        return set()
    rows = db.execute(
        select(EveType.type_id, EveGroup.name)
        .join(EveGroup, EveType.group_id == EveGroup.group_id)
        .where(EveType.type_id.in_(type_ids))
    ).all()
    return {
        int(type_id)
        for type_id, group_name in rows
        if str(group_name or "").strip().lower() in INDUSTRIAL_SHIP_GROUP_NAMES
    }


def filter_industrial_kills(db: Session, kills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    type_ids = {ship_type_id for kill in kills if (ship_type_id := victim_ship_type_id(kill)) is not None}
    industrial_type_ids = industrial_ship_type_ids(db, type_ids)
    return [kill for kill in kills if (victim_ship_type_id(kill) or 0) in industrial_type_ids]


def zkill_url(kill: dict[str, Any]) -> str | None:
    zkb = kill.get("zkb") if isinstance(kill.get("zkb"), dict) else {}
    url = zkb.get("url") if isinstance(zkb, dict) else None
    if url:
        return str(url)
    killmail_id = optional_int(kill.get("killmail_id"))
    return f"https://zkillboard.com/kill/{killmail_id}/" if killmail_id is not None else None


def gatecheck_score(kill_count: int, total_value: float, latest_kill_at: str | None, hours: int) -> int:
    score = kill_count * 10
    score += min(40, int(total_value / 1_000_000_000) * 5)
    latest = parse_kill_time(latest_kill_at)
    if latest is not None:
        age_hours = max(0.0, (datetime.now(timezone.utc) - latest.astimezone(timezone.utc)).total_seconds() / 3600)
        if age_hours <= 1:
            score += 35
        elif age_hours <= 6:
            score += 20
        elif age_hours <= max(12, hours / 2):
            score += 10
    return min(100, score)


def risk_label(score: int) -> str:
    if score >= 70:
        return "hot"
    if score >= 35:
        return "active"
    if score > 0:
        return "warm"
    return "quiet"


def type_names(db: Session, type_ids: set[int]) -> dict[int, str]:
    if not type_ids:
        return {}
    rows = db.execute(select(EveType.type_id, EveType.name).where(EveType.type_id.in_(type_ids))).all()
    return {int(type_id): str(name) for type_id, name in rows}


async def resolve_esi_names(client: httpx.AsyncClient, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    resolved: dict[int, str] = {}
    ordered_ids = sorted(ids)
    for index in range(0, len(ordered_ids), 900):
        chunk = ordered_ids[index:index + 900]
        try:
            response = await client.post(f"{ESI_BASE_URL}/universe/names/?datasource=tranquility", json=chunk)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                continue
            resolved.update({int(item["id"]): str(item["name"]) for item in payload if item.get("id") is not None and item.get("name")})
        except httpx.HTTPError:
            continue
    return resolved


async def station_name(client: httpx.AsyncClient, station_id: int) -> str | None:
    try:
        response = await client.get(f"{ESI_BASE_URL}/universe/stations/{station_id}/?datasource=tranquility")
        response.raise_for_status()
        payload = response.json()
        name = payload.get("name") if isinstance(payload, dict) else None
        return str(name) if name else None
    except httpx.HTTPError:
        return None


async def kill_location(db: Session, client: httpx.AsyncClient, kill: dict[str, Any]) -> dict[str, Any]:
    zkb = kill.get("zkb") if isinstance(kill.get("zkb"), dict) else {}
    location_id = optional_int(zkb.get("locationID") if isinstance(zkb, dict) else None)
    if location_id is None:
        return {"location_id": None, "location_kind": "space", "location_name": "In space"}

    gate = db.get(EveStargate, location_id)
    if gate is not None:
        destination = db.get(EveSystem, gate.destination_system_id) if gate.destination_system_id is not None else None
        return {
            "location_id": location_id,
            "location_kind": "gate",
            "location_name": f"Stargate to {destination.name}" if destination else f"Stargate {location_id}",
        }

    station = await station_name(client, location_id)
    if station:
        return {"location_id": location_id, "location_kind": "station", "location_name": station}

    if location_id >= 1_000_000_000_000:
        return {"location_id": location_id, "location_kind": "structure", "location_name": f"Structure {location_id}"}
    return {"location_id": location_id, "location_kind": "space", "location_name": f"Location {location_id}"}


def final_blow_attacker(kill: dict[str, Any]) -> dict[str, Any] | None:
    attackers = kill.get("attackers") if isinstance(kill.get("attackers"), list) else []
    for attacker in attackers:
        if isinstance(attacker, dict) and attacker.get("final_blow"):
            return attacker
    return attackers[-1] if attackers and isinstance(attackers[-1], dict) else None


def attacker_weapon_type_ids(kill: dict[str, Any]) -> set[int]:
    attackers = kill.get("attackers") if isinstance(kill.get("attackers"), list) else []
    ids: set[int] = set()
    for attacker in attackers:
        if not isinstance(attacker, dict):
            continue
        weapon_type_id = optional_int(attacker.get("weapon_type_id"))
        if weapon_type_id is not None:
            ids.add(weapon_type_id)
    return ids


def kill_uses_smartbomb(kill: dict[str, Any], type_name_map: dict[int, str]) -> bool:
    return any("smartbomb" in str(type_name_map.get(type_id, "")).lower() for type_id in attacker_weapon_type_ids(kill))


def collect_name_ids(kills: list[dict[str, Any]]) -> set[int]:
    ids: set[int] = set()
    for kill in kills[:5]:
        victim = kill.get("victim") if isinstance(kill.get("victim"), dict) else {}
        for key in ("character_id", "corporation_id", "alliance_id"):
            value = optional_int(victim.get(key) if isinstance(victim, dict) else None)
            if value is not None:
                ids.add(value)

        final = final_blow_attacker(kill)
        if not final:
            continue
        for key in ("character_id", "corporation_id", "alliance_id"):
            value = optional_int(final.get(key))
            if value is not None:
                ids.add(value)
    return ids


def collect_type_ids(kills: list[dict[str, Any]]) -> set[int]:
    ids: set[int] = set()
    for kill in kills[:5]:
        victim = kill.get("victim") if isinstance(kill.get("victim"), dict) else {}
        victim_ship = optional_int(victim.get("ship_type_id") if isinstance(victim, dict) else None)
        if victim_ship is not None:
            ids.add(victim_ship)
        final = final_blow_attacker(kill)
        final_ship = optional_int(final.get("ship_type_id")) if final else None
        if final_ship is not None:
            ids.add(final_ship)
        ids.update(attacker_weapon_type_ids(kill))
    return ids


async def killmail_samples(db: Session, client: httpx.AsyncClient, kills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    names = await resolve_esi_names(client, collect_name_ids(kills))
    hulls = type_names(db, collect_type_ids(kills))
    character_ids = {
        entity_id
        for kill in kills[:5]
        for entity_id in (
            optional_int((kill.get("victim") or {}).get("character_id")) if isinstance(kill.get("victim"), dict) else None,
            optional_int((final_blow_attacker(kill) or {}).get("character_id")),
        )
        if entity_id is not None
    }
    security = await gather_with_limit(sorted(character_ids), LOCAL_THREAT_ZKILL_CONCURRENCY, lambda character_id: character_public_info(client, character_id))
    samples: list[dict[str, Any]] = []
    for kill in kills[:5]:
        victim = kill.get("victim") if isinstance(kill.get("victim"), dict) else {}
        attackers = kill.get("attackers") if isinstance(kill.get("attackers"), list) else []
        final = final_blow_attacker(kill) or {}
        victim_ship_type_id = optional_int(victim.get("ship_type_id") if isinstance(victim, dict) else None)
        victim_character_id = optional_int(victim.get("character_id") if isinstance(victim, dict) else None)
        victim_corporation_id = optional_int(victim.get("corporation_id") if isinstance(victim, dict) else None)
        victim_alliance_id = optional_int(victim.get("alliance_id") if isinstance(victim, dict) else None)
        final_ship_type_id = optional_int(final.get("ship_type_id"))
        character_id = optional_int(final.get("character_id"))
        corporation_id = optional_int(final.get("corporation_id"))
        alliance_id = optional_int(final.get("alliance_id"))
        location = await kill_location(db, client, kill)
        war_id = killmail_war_id(kill)
        zkb = kill.get("zkb") if isinstance(kill.get("zkb"), dict) else {}
        samples.append(
            {
                "killmail_id": kill.get("killmail_id"),
                "killmail_time": kill.get("killmail_time"),
                "zkb_url": zkill_url(kill),
                "total_value": killmail_value(kill),
                "smartbomb_used": kill_uses_smartbomb(kill, hulls),
                "war_id": war_id,
                "is_wardec": war_id is not None,
                "victim_ship_type_id": victim_ship_type_id,
                "victim_hull": hulls.get(victim_ship_type_id or 0, f"Type {victim_ship_type_id}" if victim_ship_type_id else "Unknown hull"),
                "victim": {
                    "character_id": victim_character_id,
                    "character_name": names.get(victim_character_id or 0, f"Character {victim_character_id}" if victim_character_id else "Unknown pilot"),
                    "security_status": optional_float(security.get(victim_character_id or 0, {}).get("security_status")),
                    "corporation_id": victim_corporation_id,
                    "corporation_name": names.get(victim_corporation_id or 0, f"Corporation {victim_corporation_id}" if victim_corporation_id else None),
                    "alliance_id": victim_alliance_id,
                    "alliance_name": names.get(victim_alliance_id or 0) if victim_alliance_id else None,
                },
                "attacker_count": len(attackers),
                "combatant_count": len(attackers) + 1,
                **location,
                "final_blow": {
                    "character_id": character_id,
                    "character_name": names.get(character_id or 0, f"Character {character_id}" if character_id else "Unknown pilot"),
                    "security_status": optional_float(security.get(character_id or 0, {}).get("security_status")),
                    "corporation_id": corporation_id,
                    "corporation_name": names.get(corporation_id or 0, f"Corporation {corporation_id}" if corporation_id else None),
                    "alliance_id": alliance_id,
                    "alliance_name": names.get(alliance_id or 0) if alliance_id else None,
                    "ship_type_id": final_ship_type_id,
                    "ship_type_name": hulls.get(final_ship_type_id or 0, f"Type {final_ship_type_id}" if final_ship_type_id else "Unknown ship"),
                },
            }
        )
    return samples


async def fetch_system_kills(client: httpx.AsyncClient, system_id: int, past_seconds: int) -> list[dict[str, Any]]:
    url = f"{ZKILLBOARD_BASE_URL}/kills/solarSystemID/{system_id}/pastSeconds/{past_seconds}/"
    response = await client.get(url)
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, list) else []


def local_threat_names(raw_names: Any, max_pilots: int = LOCAL_THREAT_MAX_PILOTS) -> list[str]:
    if isinstance(raw_names, list):
        candidates = [str(name).strip() for name in raw_names]
    else:
        text = str(raw_names or "")
        candidates = [part.strip() for part in re.split(r"[\r\n,;]+", text)]

    names: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        cleaned = re.sub(r"^\[[0-9:. ]+\]\s*", "", candidate).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        key = cleaned.casefold()
        if len(cleaned) < 3 or key in seen:
            continue
        seen.add(key)
        names.append(cleaned)
        if len(names) >= max_pilots:
            break
    return names


async def resolve_character_names(client: httpx.AsyncClient, names: list[str]) -> dict[str, dict[str, Any]]:
    if not names:
        return {}
    try:
        response = await client.post(f"{ESI_BASE_URL}/universe/ids/?datasource=tranquility", json=names)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError:
        return {}

    characters = payload.get("characters") if isinstance(payload, dict) else []
    resolved: dict[str, dict[str, Any]] = {}
    if isinstance(characters, list):
        for character in characters:
            if not isinstance(character, dict):
                continue
            name = str(character.get("name") or "").strip()
            character_id = optional_int(character.get("id"))
            if name and character_id is not None:
                resolved[name.casefold()] = {"name": name, "character_id": character_id}
    return resolved


async def character_public_info(client: httpx.AsyncClient, character_id: int) -> dict[str, Any]:
    try:
        response = await client.get(f"{ESI_BASE_URL}/characters/{character_id}/?datasource=tranquility")
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}
    except httpx.HTTPError:
        return {}


async def gather_with_limit(items: list[int], limit: int, worker) -> dict[int, Any]:
    semaphore = asyncio.Semaphore(limit)

    async def run(item: int) -> tuple[int, Any]:
        async with semaphore:
            return item, await worker(item)

    pairs = await asyncio.gather(*(run(item) for item in items))
    return {item: value for item, value in pairs}


def kills_in_window(kills: list[dict[str, Any]], days: int) -> list[dict[str, Any]]:
    cutoff = utc_now() - timedelta(days=max(1, min(days, INDUSTRIAL_CACHE_RETENTION_DAYS)))
    recent: list[dict[str, Any]] = []
    for kill in kills:
        kill_time = parse_kill_time(str(kill.get("killmail_time") or ""))
        if kill_time is None:
            continue
        if kill_time.astimezone(timezone.utc) >= cutoff:
            recent.append(kill)
    return recent


async def fetch_character_kills(client: httpx.AsyncClient, character_id: int, days: int, losses: bool = False) -> list[dict[str, Any]]:
    endpoint = "losses" if losses else "kills"
    try:
        response = await client.get(f"{ZKILLBOARD_BASE_URL}/{endpoint}/characterID/{character_id}/")
        response.raise_for_status()
        payload = response.json()
        return kills_in_window(payload, days) if isinstance(payload, list) else []
    except httpx.HTTPError:
        return []


async def fetch_character_stats(client: httpx.AsyncClient, character_id: int) -> dict[str, Any]:
    try:
        response = await client.get(f"{ZKILLBOARD_BASE_URL}/stats/characterID/{character_id}/")
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}
    except httpx.HTTPError:
        return {}


def stat_number(stats: dict[str, Any], key: str) -> float:
    value = stats.get(key)
    if value is None and isinstance(stats.get("allTimeSum"), dict):
        value = stats["allTimeSum"].get(key)
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def latest_kill_time(kills: list[dict[str, Any]]) -> str | None:
    times = [str(kill.get("killmail_time")) for kill in kills if kill.get("killmail_time")]
    return max(times) if times else None


def group_kill_count(kills: list[dict[str, Any]]) -> int:
    grouped = 0
    for kill in kills:
        attackers = kill.get("attackers") if isinstance(kill.get("attackers"), list) else []
        if len([attacker for attacker in attackers if isinstance(attacker, dict)]) > 1:
            grouped += 1
    return grouped


def local_threat_lifetime_score(stats: dict[str, Any]) -> int:
    lifetime_kills = stat_number(stats, "shipsDestroyed")
    lifetime_losses = stat_number(stats, "shipsLost")
    destroyed_value = stat_number(stats, "iskDestroyed")
    danger_ratio = stat_number(stats, "dangerRatio")
    gang_ratio = stat_number(stats, "gangRatio")
    solo_kills = stat_number(stats, "soloKills")

    score = 0.0
    if lifetime_kills > 0:
        score += min(35.0, math.log10(lifetime_kills + 1) * 8.75)
    if destroyed_value > 0:
        score += min(20.0, max(0.0, (math.log10(destroyed_value + 1) - 9.0) * 4.0))
    score += min(25.0, danger_ratio * 0.25)
    if solo_kills > 0:
        score += min(8.0, math.log10(solo_kills + 1) * 2.5)
    score += min(5.0, gang_ratio * 0.05)
    if lifetime_losses > lifetime_kills and lifetime_losses > 0:
        score -= min(8.0, ((lifetime_losses - lifetime_kills) / lifetime_losses) * 8.0)
    return max(0, min(100, int(round(score))))


def local_threat_period_score(recent_kills: list[dict[str, Any]], recent_losses: list[dict[str, Any]]) -> int:
    group_percent = (group_kill_count(recent_kills) / len(recent_kills) * 100) if recent_kills else 0.0
    destroyed_value = sum(killmail_value(kill) for kill in recent_kills)
    score = 0.0
    score += min(42.0, len(recent_kills) * 6.0)
    score += min(12.0, len(recent_losses) * 2.0)
    if destroyed_value > 0:
        score += min(20.0, max(0.0, (math.log10(destroyed_value + 1) - 8.0) * 4.0))
    score += min(14.0, group_percent * 0.14)
    latest = parse_kill_time(latest_kill_time(recent_kills + recent_losses))
    if latest is not None:
        age_hours = max(0.0, (utc_now() - latest.astimezone(timezone.utc)).total_seconds() / 3600)
        if age_hours <= 24:
            score += 12.0
        elif age_hours <= 72:
            score += 7.0
        elif age_hours <= 168:
            score += 3.0
    return max(0, min(100, int(round(score))))


def local_threat_notes(stats: dict[str, Any], recent_kills: list[dict[str, Any]], recent_losses: list[dict[str, Any]], score: int) -> list[str]:
    notes: list[str] = []
    lifetime_kills = int(stat_number(stats, "shipsDestroyed"))
    lifetime_losses = int(stat_number(stats, "shipsLost"))
    destroyed_value = stat_number(stats, "iskDestroyed")
    if recent_kills:
        notes.append(f"{len(recent_kills)} public kills in window")
    if recent_losses:
        notes.append(f"{len(recent_losses)} public losses in window")
    grouped = group_kill_count(recent_kills)
    if grouped:
        notes.append(f"{grouped} group kills in window")
    if lifetime_kills:
        notes.append(f"{lifetime_kills:,} lifetime kills")
    if destroyed_value:
        notes.append(f"{destroyed_value:,.0f} ISK destroyed all time")
    if score == 0 and lifetime_losses == 0:
        notes.append("No public PvP signal found")
    return notes[:4]

def top_loss_hulls(db: Session, losses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hulls = type_names(db, {ship_id for loss in losses if (ship_id := victim_ship_type_id(loss)) is not None})
    counts: Counter[str] = Counter()
    for loss in losses:
        ship_id = victim_ship_type_id(loss)
        counts[hulls.get(ship_id or 0, f"Type {ship_id}" if ship_id else "Unknown hull")] += 1
    return rank_counter(counts, limit=3)


async def local_threat_analysis(db: Session, raw_names: Any, *, days: int = 30) -> dict[str, Any]:
    days = max(1, min(days, INDUSTRIAL_CACHE_RETENTION_DAYS))
    names = local_threat_names(raw_names)
    generated_at = utc_now().isoformat()
    errors: list[str] = []
    pilots: list[dict[str, Any]] = []

    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=20.0, follow_redirects=True) as client:
        resolved = await resolve_character_names(client, names)
        resolved_ids = [int(item["character_id"]) for item in resolved.values()]
        public_infos = await gather_with_limit(resolved_ids, LOCAL_THREAT_ZKILL_CONCURRENCY, lambda character_id: character_public_info(client, character_id))
        org_ids = {
            org_id
            for info in public_infos.values()
            for key in ("corporation_id", "alliance_id")
            if (org_id := optional_int(info.get(key))) is not None
        }
        org_names = await resolve_esi_names(client, org_ids)

        async def zkill_detail(character_id: int) -> dict[str, Any]:
            recent_kills = await fetch_character_kills(client, character_id, days, losses=False)
            recent_losses = await fetch_character_kills(client, character_id, days, losses=True)
            stats = await fetch_character_stats(client, character_id)
            return {"recent_kills": recent_kills, "recent_losses": recent_losses, "stats": stats}

        details: dict[int, dict[str, Any]] = {}
        for start in range(0, len(resolved_ids), LOCAL_THREAT_ZKILL_BATCH_SIZE):
            batch = resolved_ids[start:start + LOCAL_THREAT_ZKILL_BATCH_SIZE]
            details.update(await gather_with_limit(batch, LOCAL_THREAT_ZKILL_CONCURRENCY, zkill_detail))
            if start + LOCAL_THREAT_ZKILL_BATCH_SIZE < len(resolved_ids):
                await asyncio.sleep(0.4)

        for name in names:
            resolved_row = resolved.get(name.casefold())
            if not resolved_row:
                pilots.append(
                    {
                        "input_name": name,
                        "name": name,
                        "resolved": False,
                        "danger_score": 0,
                        "danger_label": "unknown",
                        "period_danger_score": 0,
                        "period_danger_label": "unknown",
                        "recent_kills": 0,
                        "recent_losses": 0,
                        "group_kills": 0,
                        "group_kill_percent": 0,
                        "solo_kills": 0,
                        "notes": ["Could not resolve as a public EVE character"],
                    }
                )
                continue

            character_id = int(resolved_row["character_id"])
            info = public_infos.get(character_id, {})
            corporation_id = optional_int(info.get("corporation_id"))
            alliance_id = optional_int(info.get("alliance_id"))
            security_status = optional_float(info.get("security_status"))
            detail = details.get(character_id, {})
            recent_kills = detail.get("recent_kills") or []
            recent_losses = detail.get("recent_losses") or []
            stats = detail.get("stats") or {}

            score = local_threat_lifetime_score(stats)
            period_score = local_threat_period_score(recent_kills, recent_losses)
            last_activity = latest_kill_time(recent_kills + recent_losses)
            group_kills = group_kill_count(recent_kills)
            group_percent = round((group_kills / len(recent_kills) * 100), 1) if recent_kills else 0
            pilots.append(
                {
                    "input_name": name,
                    "name": str(resolved_row["name"]),
                    "resolved": True,
                    "character_id": character_id,
                    "security_status": security_status,
                    "corporation_id": corporation_id,
                    "corporation_name": org_names.get(corporation_id or 0),
                    "alliance_id": alliance_id,
                    "alliance_name": org_names.get(alliance_id or 0),
                    "danger_score": score,
                    "danger_label": risk_label(score),
                    "period_danger_score": period_score,
                    "period_danger_label": risk_label(period_score),
                    "recent_kills": len(recent_kills),
                    "recent_losses": len(recent_losses),
                    "group_kills": group_kills,
                    "group_kill_percent": group_percent,
                    "ships_destroyed": int(stat_number(stats, "shipsDestroyed")),
                    "ships_lost": int(stat_number(stats, "shipsLost")),
                    "isk_destroyed": stat_number(stats, "iskDestroyed"),
                    "isk_lost": stat_number(stats, "iskLost"),
                    "danger_ratio": stat_number(stats, "dangerRatio"),
                    "gang_ratio": stat_number(stats, "gangRatio"),
                    "solo_kills": int(stat_number(stats, "soloKills")),
                    "last_activity_at": last_activity,
                    "zkb_url": f"https://zkillboard.com/character/{character_id}/",
                    "top_loss_hulls": top_loss_hulls(db, recent_losses),
                    "notes": local_threat_notes(stats, recent_kills, recent_losses, score),
                }
            )

    pilots.sort(key=lambda pilot: (int(pilot.get("danger_score") or 0), int(pilot.get("recent_kills") or 0)), reverse=True)
    return {
        "generated_at": generated_at,
        "days": days,
        "input_count": len(names),
        "resolved_count": sum(1 for pilot in pilots if pilot.get("resolved")),
        "zkill_analyzed_count": sum(1 for pilot in pilots if pilot.get("resolved")),
        "max_pilots": LOCAL_THREAT_MAX_PILOTS,
        "zkill_detail_limit": LOCAL_THREAT_MAX_PILOTS,
        "errors": list(dict.fromkeys(errors)),
        "pilots": pilots,
    }


async def gatecheck_route(
    db: Session,
    origin: str,
    destination: str,
    *,
    highsec_only: bool = False,
    prefer_safer: bool = False,
    avoid_system_ids: Iterable[int] | None = None,
    hours: int = 1,
    industrial_only: bool = True,
) -> dict[str, Any]:
    hours = max(1, min(hours, 168))
    route = plan_gate_route(db, origin, destination, highsec_only=highsec_only, prefer_safer=prefer_safer, avoid_system_ids=avoid_system_ids)
    past_seconds = hours * 3600
    enriched_systems: list[dict[str, Any]] = []
    total_kills = 0
    total_value = 0.0
    errors: list[str] = []

    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=12.0, follow_redirects=True) as client:
        for system in route["systems"]:
            next_system = dict(system)
            try:
                kills = await fetch_system_kills(client, int(system["system_id"]), past_seconds)
                kills.sort(key=lambda item: str(item.get("killmail_time") or ""), reverse=True)
                if industrial_only:
                    kills = filter_industrial_kills(db, kills)
                kill_count = len(kills)
                value = sum(killmail_value(kill) for kill in kills)
                latest = str(kills[0].get("killmail_time")) if kills else None
                score = gatecheck_score(kill_count, value, latest, hours)
                next_system.update(
                    {
                        "recent_kill_count": kill_count,
                        "recent_destroyed_value": value,
                        "latest_killmail_time": latest,
                        "risk_score": score,
                        "risk_label": risk_label(score),
                        "sample_killmails": await killmail_samples(db, client, kills),
                    }
                )
                total_kills += kill_count
                total_value += value
            except httpx.HTTPError as exc:
                next_system.update(
                    {
                        "recent_kill_count": None,
                        "recent_destroyed_value": None,
                        "latest_killmail_time": None,
                        "risk_score": None,
                        "risk_label": "unknown",
                        "sample_killmails": [],
                    }
                )
                errors.append(f"{system['name']}: {exc}")
            enriched_systems.append(next_system)

    route["systems"] = enriched_systems
    route["gatecheck"] = {
        "hours": hours,
        "industrial_only": industrial_only,
        "total_recent_kills": total_kills,
        "total_destroyed_value": total_value,
        "checked_systems": len(enriched_systems),
        "error_count": len(errors),
        "errors": errors[:8],
    }
    return route

def collect_all_name_ids(kills: list[dict[str, Any]]) -> set[int]:
    ids: set[int] = set()
    for kill in kills:
        victim = kill.get("victim") if isinstance(kill.get("victim"), dict) else {}
        for key in ("character_id", "corporation_id", "alliance_id"):
            value = optional_int(victim.get(key) if isinstance(victim, dict) else None)
            if value is not None:
                ids.add(value)

        attackers = kill.get("attackers") if isinstance(kill.get("attackers"), list) else []
        for attacker in attackers:
            if not isinstance(attacker, dict):
                continue
            for key in ("character_id", "corporation_id", "alliance_id"):
                value = optional_int(attacker.get(key))
                if value is not None:
                    ids.add(value)
    return ids


def collect_all_type_ids(kills: list[dict[str, Any]]) -> set[int]:
    ids: set[int] = set()
    for kill in kills:
        victim_ship = victim_ship_type_id(kill)
        if victim_ship is not None:
            ids.add(victim_ship)
        final = final_blow_attacker(kill)
        final_ship = optional_int(final.get("ship_type_id")) if final else None
        if final_ship is not None:
            ids.add(final_ship)
        ids.update(attacker_weapon_type_ids(kill))
    return ids


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def observation_window_start(days: int) -> datetime:
    bounded_days = max(1, min(days, INDUSTRIAL_CACHE_RETENTION_DAYS))
    return utc_now() - timedelta(days=bounded_days)


def cache_is_fresh(cache: SystemKillFetchCache | None) -> bool:
    if cache is None:
        return False
    expires_at = cache.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at > utc_now()


def rank_counter(counter: Counter[str], *, limit: int = 5, values: Counter[str] | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, count in counter.most_common(limit):
        rows.append({"name": name, "count": count, "total_value": float(values[name]) if values else 0})
    return rows


def attacker_org_counters(rows: list[SystemIndustrialKillObservation], org_key: str) -> tuple[Counter[str], Counter[str]]:
    counts: Counter[str] = Counter()
    values: Counter[str] = Counter()
    for row in rows:
        raw = row.raw_json if isinstance(row.raw_json, dict) else {}
        attackers = raw.get("attackers") if isinstance(raw.get("attackers"), list) else []
        seen_for_kill: set[str] = set()
        for attacker in attackers:
            if not isinstance(attacker, dict):
                continue
            org_id = optional_int(attacker.get(org_key))
            if org_id is None:
                continue
            raw_names = raw.get("_eqm_names") if isinstance(raw.get("_eqm_names"), dict) else {}
            name = str(raw_names.get(str(org_id)) or f"{org_key.replace('_id', '').title()} {org_id}")
            if org_key == "corporation_id" and row.final_blow_corporation_id == org_id and row.final_blow_corporation_name:
                name = row.final_blow_corporation_name
            if org_key == "alliance_id" and row.final_blow_alliance_id == org_id and row.final_blow_alliance_name:
                name = row.final_blow_alliance_name
            if name in seen_for_kill:
                continue
            seen_for_kill.add(name)
            counts[name] += 1
            values[name] += row.total_value or 0
    return counts, values


def time_period_label(killmail_time: datetime) -> str:
    hour = killmail_time.astimezone(timezone.utc).hour
    return f"{hour:02d}:00-{(hour + 1) % 24:02d}:00 UTC"


def group_size_bucket(attacker_count: int) -> str:
    return f"{attacker_count} attacker{'s' if attacker_count != 1 else ''}"


def build_industrial_threat_analysis(
    db: Session,
    system: EveSystem,
    *,
    days: int,
    refresh_hours: int,
    live_fetch_performed: bool,
    cache: SystemKillFetchCache | None,
) -> dict[str, Any]:
    window_start = observation_window_start(days)
    rows = db.scalars(
        select(SystemIndustrialKillObservation)
        .where(SystemIndustrialKillObservation.system_id == system.system_id)
        .where(SystemIndustrialKillObservation.killmail_time >= window_start)
        .order_by(SystemIndustrialKillObservation.killmail_time.desc())
    ).all()

    hulls: Counter[str] = Counter()
    hull_values: Counter[str] = Counter()
    periods: Counter[str] = Counter()
    period_values: Counter[str] = Counter()
    locations: Counter[str] = Counter()
    location_values: Counter[str] = Counter()
    final_hulls: Counter[str] = Counter()
    final_hull_values: Counter[str] = Counter()
    group_sizes: Counter[str] = Counter()
    group_size_values: Counter[str] = Counter()

    total_value = Decimal("0")
    latest_kill_at: str | None = None
    for row in rows:
        total_value += row.total_value or Decimal("0")
        if latest_kill_at is None:
            latest_kill_at = row.killmail_time.isoformat()

        hull = row.victim_hull or "Unknown hull"
        hulls[hull] += 1
        hull_values[hull] += row.total_value or 0

        period = time_period_label(row.killmail_time)
        periods[period] += 1
        period_values[period] += row.total_value or 0

        location_name = row.location_name or "Unknown location"
        location = f"{row.location_kind or 'space'} · {location_name}"
        locations[location] += 1
        location_values[location] += row.total_value or 0

        final_hull = row.final_blow_ship_type_name or "Unknown final-blow hull"
        final_hulls[final_hull] += 1
        final_hull_values[final_hull] += row.total_value or 0

        size = group_size_bucket(row.attacker_count)
        group_sizes[size] += 1
        group_size_values[size] += row.total_value or 0

    corp_counts, corp_values = attacker_org_counters(list(rows), "corporation_id")
    alliance_counts, alliance_values = attacker_org_counters(list(rows), "alliance_id")
    score = gatecheck_score(len(rows), float(total_value), latest_kill_at, max(1, min(refresh_hours, 168)))

    return {
        "system": serialize_system(system),
        "days": max(1, min(days, INDUSTRIAL_CACHE_RETENTION_DAYS)),
        "retention_days": INDUSTRIAL_CACHE_RETENTION_DAYS,
        "refresh_hours": max(1, min(refresh_hours, 168)),
        "cache": {
            "live_fetch_performed": live_fetch_performed,
            "fetched_at": cache.fetched_at.isoformat() if cache else None,
            "expires_at": cache.expires_at.isoformat() if cache else None,
            "ttl_minutes": INDUSTRIAL_CACHE_TTL_MINUTES,
        },
        "total_industrial_kills": len(rows),
        "total_destroyed_value": float(total_value),
        "latest_killmail_time": latest_kill_at,
        "risk_score": score,
        "risk_label": risk_label(score),
        "top_victim_hulls": rank_counter(hulls, values=hull_values),
        "top_time_periods": rank_counter(periods, values=period_values),
        "top_attacker_corporations": rank_counter(corp_counts, values=corp_values),
        "top_attacker_alliances": rank_counter(alliance_counts, values=alliance_values),
        "most_dangerous_locations": rank_counter(locations, values=location_values),
        "top_final_blow_hulls": rank_counter(final_hulls, values=final_hull_values),
        "top_attacker_group_sizes": rank_counter(group_sizes, values=group_size_values),
    }


async def cache_system_industrial_kills(db: Session, client: httpx.AsyncClient, system_id: int, hours: int) -> int:
    hours = max(1, min(hours, 168))
    kills = await fetch_system_kills(client, system_id, hours * 3600)
    kills.sort(key=lambda item: str(item.get("killmail_time") or ""), reverse=True)
    industrial_kills = filter_industrial_kills(db, kills)
    names = await resolve_esi_names(client, collect_all_name_ids(industrial_kills))
    hulls = type_names(db, collect_all_type_ids(industrial_kills))
    cached_count = 0

    for kill in industrial_kills:
        killmail_id = optional_int(kill.get("killmail_id"))
        kill_time = parse_kill_time(str(kill.get("killmail_time") or ""))
        if killmail_id is None or kill_time is None:
            continue

        victim = kill.get("victim") if isinstance(kill.get("victim"), dict) else {}
        attackers = kill.get("attackers") if isinstance(kill.get("attackers"), list) else []
        final = final_blow_attacker(kill) or {}
        location = await kill_location(db, client, kill)
        victim_ship = victim_ship_type_id(kill)
        final_ship = optional_int(final.get("ship_type_id"))
        victim_character_id = optional_int(victim.get("character_id") if isinstance(victim, dict) else None)
        victim_corporation_id = optional_int(victim.get("corporation_id") if isinstance(victim, dict) else None)
        victim_alliance_id = optional_int(victim.get("alliance_id") if isinstance(victim, dict) else None)
        final_character_id = optional_int(final.get("character_id"))
        final_corporation_id = optional_int(final.get("corporation_id"))
        final_alliance_id = optional_int(final.get("alliance_id"))

        observation = db.scalar(select(SystemIndustrialKillObservation).where(SystemIndustrialKillObservation.killmail_id == killmail_id))
        if observation is None:
            observation = SystemIndustrialKillObservation(killmail_id=killmail_id, system_id=system_id, killmail_time=kill_time)
            db.add(observation)
        observation.system_id = system_id
        observation.killmail_time = kill_time
        observation.total_value = Decimal(str(killmail_value(kill)))
        observation.zkb_url = zkill_url(kill)
        observation.victim_ship_type_id = victim_ship
        observation.victim_hull = hulls.get(victim_ship or 0, f"Type {victim_ship}" if victim_ship else "Unknown hull")
        observation.victim_character_id = victim_character_id
        observation.victim_character_name = names.get(victim_character_id or 0, f"Character {victim_character_id}" if victim_character_id else "Unknown pilot")
        observation.victim_corporation_id = victim_corporation_id
        observation.victim_corporation_name = names.get(victim_corporation_id or 0, f"Corporation {victim_corporation_id}" if victim_corporation_id else None)
        observation.victim_alliance_id = victim_alliance_id
        observation.victim_alliance_name = names.get(victim_alliance_id or 0) if victim_alliance_id else None
        observation.attacker_count = len(attackers)
        observation.combatant_count = len(attackers) + 1
        observation.smartbomb_used = kill_uses_smartbomb(kill, hulls)
        observation.war_id = killmail_war_id(kill)
        observation.location_id = location.get("location_id")
        observation.location_kind = location.get("location_kind")
        observation.location_name = location.get("location_name")
        observation.final_blow_character_id = final_character_id
        observation.final_blow_character_name = names.get(final_character_id or 0, f"Character {final_character_id}" if final_character_id else "Unknown pilot")
        observation.final_blow_corporation_id = final_corporation_id
        observation.final_blow_corporation_name = names.get(final_corporation_id or 0, f"Corporation {final_corporation_id}" if final_corporation_id else None)
        observation.final_blow_alliance_id = final_alliance_id
        observation.final_blow_alliance_name = names.get(final_alliance_id or 0) if final_alliance_id else None
        observation.final_blow_ship_type_id = final_ship
        observation.final_blow_ship_type_name = hulls.get(final_ship or 0, f"Type {final_ship}" if final_ship else "Unknown ship")
        raw_with_names = dict(kill)
        raw_with_names["_eqm_names"] = {str(entity_id): name for entity_id, name in names.items()}
        observation.raw_json = raw_with_names
        observation.cached_at = utc_now()
        cached_count += 1
    return cached_count


async def system_industrial_threat(
    db: Session,
    system_query: str,
    *,
    refresh_hours: int = 24,
    days: int = INDUSTRIAL_CACHE_RETENTION_DAYS,
    force_refresh: bool = False,
) -> dict[str, Any]:
    refresh_hours = max(1, min(refresh_hours, 168))
    days = max(1, min(days, INDUSTRIAL_CACHE_RETENTION_DAYS))
    system = resolve_system(db, system_query)
    now = utc_now()
    db.execute(delete(SystemIndustrialKillObservation).where(SystemIndustrialKillObservation.killmail_time < now - timedelta(days=INDUSTRIAL_CACHE_RETENTION_DAYS)))

    cache = db.scalar(
        select(SystemKillFetchCache)
        .where(SystemKillFetchCache.system_id == system.system_id)
        .where(SystemKillFetchCache.lookback_hours == refresh_hours)
        .where(SystemKillFetchCache.feed == INDUSTRIAL_CACHE_FEED)
    )
    live_fetch_performed = False
    if force_refresh or not cache_is_fresh(cache):
        async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=18.0, follow_redirects=True) as client:
            try:
                cached_count = await cache_system_industrial_kills(db, client, system.system_id, refresh_hours)
                if cache is None:
                    cache = SystemKillFetchCache(system_id=system.system_id, lookback_hours=refresh_hours, feed=INDUSTRIAL_CACHE_FEED)
                    db.add(cache)
                cache.fetched_at = now
                cache.expires_at = now + timedelta(minutes=INDUSTRIAL_CACHE_TTL_MINUTES)
                cache.kill_count = cached_count
                cache.status = "success"
                cache.message = f"Cached {cached_count} industrial kill observations from zKill."
                live_fetch_performed = True
            except httpx.HTTPError as exc:
                if cache is None:
                    cache = SystemKillFetchCache(system_id=system.system_id, lookback_hours=refresh_hours, feed=INDUSTRIAL_CACHE_FEED)
                    db.add(cache)
                cache.fetched_at = now
                cache.expires_at = now + timedelta(minutes=5)
                cache.status = "error"
                cache.message = str(exc)
        db.commit()

    return build_industrial_threat_analysis(db, system, days=days, refresh_hours=refresh_hours, live_fetch_performed=live_fetch_performed, cache=cache)

def victim_org_counters(rows: list[Any], org_key: str) -> tuple[Counter[str], Counter[str]]:
    counts: Counter[str] = Counter()
    values: Counter[str] = Counter()
    for row in rows:
        org_id = getattr(row, org_key, None)
        if org_id is None:
            continue
        name_attr = org_key.replace("_id", "_name")
        name = getattr(row, name_attr, None) or f"{org_key.replace('_id', '').replace('victim_', '').title()} {org_id}"
        counts[name] += 1
        values[name] += row.total_value or 0
    return counts, values


def build_pvp_intel_analysis(
    db: Session,
    system: EveSystem,
    *,
    days: int,
    refresh_hours: int,
    live_fetch_performed: bool,
    cache: SystemKillFetchCache | None,
) -> dict[str, Any]:
    window_start = observation_window_start(days)
    rows = db.scalars(
        select(SystemPvpKillObservation)
        .where(SystemPvpKillObservation.system_id == system.system_id)
        .where(SystemPvpKillObservation.killmail_time >= window_start)
        .order_by(SystemPvpKillObservation.killmail_time.desc())
    ).all()

    hulls: Counter[str] = Counter()
    hull_values: Counter[str] = Counter()
    periods: Counter[str] = Counter()
    period_values: Counter[str] = Counter()
    locations: Counter[str] = Counter()
    location_values: Counter[str] = Counter()
    final_hulls: Counter[str] = Counter()
    final_hull_values: Counter[str] = Counter()
    group_sizes: Counter[str] = Counter()
    group_size_values: Counter[str] = Counter()

    total_value = Decimal("0")
    latest_kill_at: str | None = None
    for row in rows:
        total_value += row.total_value or Decimal("0")
        if latest_kill_at is None:
            latest_kill_at = row.killmail_time.isoformat()

        hull = row.victim_hull or "Unknown hull"
        hulls[hull] += 1
        hull_values[hull] += row.total_value or 0

        period = time_period_label(row.killmail_time)
        periods[period] += 1
        period_values[period] += row.total_value or 0

        location_name = row.location_name or "Unknown location"
        location = f"{row.location_kind or 'space'} · {location_name}"
        locations[location] += 1
        location_values[location] += row.total_value or 0

        final_hull = row.final_blow_ship_type_name or "Unknown final-blow hull"
        final_hulls[final_hull] += 1
        final_hull_values[final_hull] += row.total_value or 0

        size = group_size_bucket(row.attacker_count)
        group_sizes[size] += 1
        group_size_values[size] += row.total_value or 0

    attacker_corp_counts, attacker_corp_values = attacker_org_counters(list(rows), "corporation_id")
    attacker_alliance_counts, attacker_alliance_values = attacker_org_counters(list(rows), "alliance_id")
    victim_corp_counts, victim_corp_values = victim_org_counters(list(rows), "victim_corporation_id")
    victim_alliance_counts, victim_alliance_values = victim_org_counters(list(rows), "victim_alliance_id")
    score = gatecheck_score(len(rows), float(total_value), latest_kill_at, max(1, min(refresh_hours, 168)))

    return {
        "system": serialize_system(system),
        "days": max(1, min(days, INDUSTRIAL_CACHE_RETENTION_DAYS)),
        "retention_days": INDUSTRIAL_CACHE_RETENTION_DAYS,
        "refresh_hours": max(1, min(refresh_hours, 168)),
        "cache": {
            "live_fetch_performed": live_fetch_performed,
            "fetched_at": cache.fetched_at.isoformat() if cache else None,
            "expires_at": cache.expires_at.isoformat() if cache else None,
            "ttl_minutes": INDUSTRIAL_CACHE_TTL_MINUTES,
        },
        "total_kills": len(rows),
        "total_destroyed_value": float(total_value),
        "latest_killmail_time": latest_kill_at,
        "risk_score": score,
        "risk_label": risk_label(score),
        "top_victim_hulls": rank_counter(hulls, values=hull_values),
        "top_time_periods": rank_counter(periods, values=period_values),
        "top_attacker_corporations": rank_counter(attacker_corp_counts, values=attacker_corp_values),
        "top_attacker_alliances": rank_counter(attacker_alliance_counts, values=attacker_alliance_values),
        "top_victim_corporations": rank_counter(victim_corp_counts, values=victim_corp_values),
        "top_victim_alliances": rank_counter(victim_alliance_counts, values=victim_alliance_values),
        "most_dangerous_locations": rank_counter(locations, values=location_values),
        "top_final_blow_hulls": rank_counter(final_hulls, values=final_hull_values),
        "top_attacker_group_sizes": rank_counter(group_sizes, values=group_size_values),
    }


async def cache_system_pvp_kills(db: Session, client: httpx.AsyncClient, system_id: int, hours: int) -> int:
    hours = max(1, min(hours, 168))
    kills = await fetch_system_kills(client, system_id, hours * 3600)
    kills.sort(key=lambda item: str(item.get("killmail_time") or ""), reverse=True)
    names = await resolve_esi_names(client, collect_all_name_ids(kills))
    hulls = type_names(db, collect_all_type_ids(kills))
    cached_count = 0

    for kill in kills:
        killmail_id = optional_int(kill.get("killmail_id"))
        kill_time = parse_kill_time(str(kill.get("killmail_time") or ""))
        if killmail_id is None or kill_time is None:
            continue

        victim = kill.get("victim") if isinstance(kill.get("victim"), dict) else {}
        attackers = kill.get("attackers") if isinstance(kill.get("attackers"), list) else []
        final = final_blow_attacker(kill) or {}
        location = await kill_location(db, client, kill)
        victim_ship = victim_ship_type_id(kill)
        final_ship = optional_int(final.get("ship_type_id"))
        victim_character_id = optional_int(victim.get("character_id") if isinstance(victim, dict) else None)
        victim_corporation_id = optional_int(victim.get("corporation_id") if isinstance(victim, dict) else None)
        victim_alliance_id = optional_int(victim.get("alliance_id") if isinstance(victim, dict) else None)
        final_character_id = optional_int(final.get("character_id"))
        final_corporation_id = optional_int(final.get("corporation_id"))
        final_alliance_id = optional_int(final.get("alliance_id"))

        observation = db.scalar(select(SystemPvpKillObservation).where(SystemPvpKillObservation.killmail_id == killmail_id))
        if observation is None:
            observation = SystemPvpKillObservation(killmail_id=killmail_id, system_id=system_id, killmail_time=kill_time)
            db.add(observation)
        observation.system_id = system_id
        observation.killmail_time = kill_time
        observation.total_value = Decimal(str(killmail_value(kill)))
        observation.zkb_url = zkill_url(kill)
        observation.victim_ship_type_id = victim_ship
        observation.victim_hull = hulls.get(victim_ship or 0, f"Type {victim_ship}" if victim_ship else "Unknown hull")
        observation.victim_character_id = victim_character_id
        observation.victim_character_name = names.get(victim_character_id or 0, f"Character {victim_character_id}" if victim_character_id else "Unknown pilot")
        observation.victim_corporation_id = victim_corporation_id
        observation.victim_corporation_name = names.get(victim_corporation_id or 0, f"Corporation {victim_corporation_id}" if victim_corporation_id else None)
        observation.victim_alliance_id = victim_alliance_id
        observation.victim_alliance_name = names.get(victim_alliance_id or 0) if victim_alliance_id else None
        observation.attacker_count = len(attackers)
        observation.combatant_count = len(attackers) + 1
        observation.smartbomb_used = kill_uses_smartbomb(kill, hulls)
        observation.war_id = killmail_war_id(kill)
        observation.location_id = location.get("location_id")
        observation.location_kind = location.get("location_kind")
        observation.location_name = location.get("location_name")
        observation.final_blow_character_id = final_character_id
        observation.final_blow_character_name = names.get(final_character_id or 0, f"Character {final_character_id}" if final_character_id else "Unknown pilot")
        observation.final_blow_corporation_id = final_corporation_id
        observation.final_blow_corporation_name = names.get(final_corporation_id or 0, f"Corporation {final_corporation_id}" if final_corporation_id else None)
        observation.final_blow_alliance_id = final_alliance_id
        observation.final_blow_alliance_name = names.get(final_alliance_id or 0) if final_alliance_id else None
        observation.final_blow_ship_type_id = final_ship
        observation.final_blow_ship_type_name = hulls.get(final_ship or 0, f"Type {final_ship}" if final_ship else "Unknown ship")
        raw_with_names = dict(kill)
        raw_with_names["_eqm_names"] = {str(entity_id): name for entity_id, name in names.items()}
        observation.raw_json = raw_with_names
        observation.cached_at = utc_now()
        cached_count += 1
    return cached_count


async def system_pvp_intel(
    db: Session,
    system_query: str,
    *,
    refresh_hours: int = 24,
    days: int = INDUSTRIAL_CACHE_RETENTION_DAYS,
    force_refresh: bool = False,
) -> dict[str, Any]:
    refresh_hours = max(1, min(refresh_hours, 168))
    days = max(1, min(days, INDUSTRIAL_CACHE_RETENTION_DAYS))
    system = resolve_system(db, system_query)
    now = utc_now()
    db.execute(delete(SystemPvpKillObservation).where(SystemPvpKillObservation.killmail_time < now - timedelta(days=INDUSTRIAL_CACHE_RETENTION_DAYS)))

    cache = db.scalar(
        select(SystemKillFetchCache)
        .where(SystemKillFetchCache.system_id == system.system_id)
        .where(SystemKillFetchCache.lookback_hours == refresh_hours)
        .where(SystemKillFetchCache.feed == PVP_CACHE_FEED)
    )
    live_fetch_performed = False
    if force_refresh or not cache_is_fresh(cache):
        async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=18.0, follow_redirects=True) as client:
            try:
                cached_count = await cache_system_pvp_kills(db, client, system.system_id, refresh_hours)
                if cache is None:
                    cache = SystemKillFetchCache(system_id=system.system_id, lookback_hours=refresh_hours, feed=PVP_CACHE_FEED)
                    db.add(cache)
                cache.fetched_at = now
                cache.expires_at = now + timedelta(minutes=INDUSTRIAL_CACHE_TTL_MINUTES)
                cache.kill_count = cached_count
                cache.status = "success"
                cache.message = f"Cached {cached_count} PvP kill observations from zKill."
                live_fetch_performed = True
            except httpx.HTTPError as exc:
                if cache is None:
                    cache = SystemKillFetchCache(system_id=system.system_id, lookback_hours=refresh_hours, feed=PVP_CACHE_FEED)
                    db.add(cache)
                cache.fetched_at = now
                cache.expires_at = now + timedelta(minutes=5)
                cache.status = "error"
                cache.message = str(exc)
        db.commit()

    return build_pvp_intel_analysis(db, system, days=days, refresh_hours=refresh_hours, live_fetch_performed=live_fetch_performed, cache=cache)
