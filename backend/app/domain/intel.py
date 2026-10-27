"""Portable intel contracts and evidence math; no web, ORM, EQM or token code."""
from __future__ import annotations
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
import re

SCHEMA_VERSION = "eqm.intel.v1"
KINDS = {"character", "corporation", "alliance"}

class PublicIntelSource(Protocol):
    async def resolve(self, names: list[str]) -> dict: ...
    async def profile(self, kind: str, eve_id: int) -> dict: ...
    async def stats(self, kind: str, eve_id: int) -> dict: ...
    async def page(self, kind: str, eve_id: int, feed: str, page: int) -> list[dict]: ...
    async def killmail(self, killmail_id: int, killmail_hash: str) -> dict: ...
    async def names(self, ids: list[int]) -> list[dict]: ...
    async def type_info(self, type_id: int) -> dict: ...
    async def system_info(self, system_id: int) -> dict: ...
    async def close(self) -> None: ...

@dataclass(frozen=True)
class IntelPrincipal:
    subject: str
    can_investigate: bool
    private_character_ids: frozenset[int] = frozenset()


def utc(value: datetime | str) -> datetime:
    if isinstance(value, str): value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)


def parse_entities(text: str) -> list[dict]:
    result, seen = [], set()
    for raw in text.splitlines():
        raw = raw.strip().split("\t")[0].strip()
        if not raw or raw.casefold() in {"name", "character", "pilot"}: continue
        match = re.fullmatch(r"(?:https://(?:www\.)?zkillboard\.com/)?(character|corporation|alliance)(?:/|:)([0-9]+)/?(?:\?.*)?", raw, re.I)
        if match:
            row = {"kind": match[1].lower(), "eve_id": int(match[2]), "input": raw}
            key = (row["kind"], row["eve_id"])
        else:
            if len(raw) > 255 or raw.startswith(("http:", "https:")):
                raise ValueError("Use names or zKill character/corporation/alliance URLs; arbitrary URLs are not fetched")
            row = {"input": raw}; key = raw.casefold()
        if key not in seen: result.append(row); seen.add(key)
    if len(result) > 100: raise ValueError("Resolve at most 100 entities at a time")
    if not result: raise ValueError("Paste at least one character, corporation or alliance")
    return result


def positive_number(value: Any) -> int:
    try: return max(0, int(value or 0))
    except (TypeError, ValueError): return 0


def zkill_badges(stats: dict) -> list[dict]:
    """Import upstream indicators without inventing tags from unrelated labels."""
    result = []
    for name, count in (stats.get("activityTags") or {}).items():
        if name in {"blops", "logi", "capital", "super", "titan"} and positive_number(count):
            result.append({"label": name.upper(), "count": positive_number(count), "source": "zkill", "window_days": 90,
                           "meaning": "Recorded attacker appearances in this ship role"})
    for field, label, threshold in [("cyno", "CYNO", 1), ("awoxCount", "AWOX", 10), ("allianceAwoxCount", "ALLIANCE AWOX", 15), ("factionAwoxCount", "FACTION AWOX", 20), ("gankerCount", "GANKER", 10)]:
        value = stats.get(field)
        if isinstance(value, dict): count = positive_number(value.get("count"))
        else: count = positive_number(value)
        if count >= threshold:
            result.append({"label": label, "count": count, "source": "zkill", "window_days": 365,
                           "meaning": "Fitted cyno losses; does not establish that a cyno was lit" if field == "cyno" else "Upstream zKill character indicator"})
    for field in ("fc", "bait"):
        value = stats.get(field)
        if isinstance(value, dict) and str(value.get("level", "")).lower() in {"low", "medium", "high"}:
            badge={"label": field.upper(), "level": str(value["level"]).lower(), "source": "zkill", "window_days": 365, "meaning": "Upstream inferred activity indicator"}
            if field=="bait":badge["count"]=positive_number(value.get("count"))
            result.append(badge)
    # zKill's ROOKIE presentation is derived from its public birthday and recent
    # PvP statistics. Keep this explicitly separate from imported indicators.
    birthday=(stats.get("info") or {}).get("birthday")
    pvp=(stats.get("recentLabels") or {}).get("pvp")
    if birthday and isinstance(pvp,dict):
        try:age=(datetime.now(timezone.utc)-utc(birthday)).days
        except (ValueError,TypeError):age=-1
        if 0<=age<180 and positive_number(pvp.get("shipsLost"))>positive_number(pvp.get("shipsDestroyed")) and not any(row["label"] in {"CAPITAL","SUPER","TITAN","CYNO","BAIT"} for row in result):
            result.append({"label":"ROOKIE","source":"zkill-rule","window_days":90,"meaning":"Computed from zKill public age and recent PvP counters using its documented rookie rule"})
    return result


def sample_evidence(row: dict, killmail_id: int) -> None:
    """Keep up to ten recent links while facts are processed chronologically."""
    row["evidence"].append(killmail_id)
    if len(row["evidence"]) > 10: row["evidence"].pop(0)


def summarize_evidence(kind: str, eve_id: int, facts: list[dict], from_at: datetime, to_at: datetime) -> dict:
    """Facts are unique killmails with compact participant rows and type metadata.

    Associations are co-attacker appearances, never inferred identity or fleet
    membership. Engagements group a system's appearances with <=30-minute gaps.
    """
    column = f"{kind}_id"
    systems, ships, hours, associates = {}, {}, Counter(), {}
    kill_ids, loss_ids, smart_ids, known_weapon_ids, solo_ids = set(), set(), set(), set(), set()
    timeline = defaultdict(lambda: {"kills": 0, "losses": 0})
    gang_sizes = []
    matched_facts = []
    seen = set()
    for fact in sorted(facts, key=lambda row: (row["time"], row["id"])):
        kid, at = fact["id"], utc(fact["time"])
        if kid in seen or not (utc(from_at) <= at < utc(to_at)): continue
        seen.add(kid)
        mine = [p for p in fact["attackers"] if p.get(column) == eve_id]
        lost = fact["victim"].get(column) == eve_id
        if not mine and not lost: continue
        matched_facts.append({"id": kid, "time": at.isoformat(), "system_id": fact["system_id"], "side": "both" if mine and lost else "attacker" if mine else "victim", "npc_only": bool(fact.get("npc_only"))})
        if fact.get("npc_only"): continue
        if mine: kill_ids.add(kid); timeline[at.date().isoformat()]["kills"] += 1
        if lost: loss_ids.add(kid); timeline[at.date().isoformat()]["losses"] += 1
        hours[at.hour] += 1
        system = systems.setdefault(fact["system_id"], {"id": fact["system_id"], "name": fact.get("system_name"), "region_id": fact.get("region_id"), "region_name": fact.get("region_name"), "kills": 0, "losses": 0, "last_seen": at.isoformat(), "evidence": []})
        system["kills"] += bool(mine); system["losses"] += lost; system["last_seen"] = at.isoformat()
        sample_evidence(system, kid)
        for ship_id in {p.get("ship_type_id") for p in mine if p.get("ship_type_id")} | ({fact["victim"].get("ship_type_id")} if lost and fact["victim"].get("ship_type_id") else set()):
            entry = ships.setdefault(ship_id, {"id": ship_id, "kills": 0, "losses": 0, "evidence": []})
            entry["kills"] += any(p.get("ship_type_id") == ship_id for p in mine)
            entry["losses"] += bool(lost and fact["victim"].get("ship_type_id") == ship_id)
            sample_evidence(entry, kid)
        if not mine: continue
        player_attackers = {p["character_id"] for p in fact["attackers"] if p.get("character_id")}
        gang_sizes.append(len(player_attackers))
        if fact.get("solo"): solo_ids.add(kid)
        if any(p.get("weapon_known") for p in mine): known_weapon_ids.add(kid)
        if any(p.get("smartbomb") for p in mine): smart_ids.add(kid)
        # At most one count per other entity per kill, even when a corp fields
        # many pilots. Historical affiliation comes from this killmail.
        others = set()
        for p in fact["attackers"]:
            if p.get(column) == eve_id: continue
            for other_kind in ("character", "corporation", "alliance"):
                oid = p.get(f"{other_kind}_id")
                if oid and not (other_kind == kind and oid == eve_id): others.add((other_kind, oid))
        for other_kind, oid in others:
            item = associates.setdefault((other_kind, oid), {"kind": other_kind, "id": oid, "kills": 0, "days_set": set(), "events": [], "evidence": []})
            item["kills"] += 1; item["days_set"].add(at.date().isoformat()); item["events"].append((fact["system_id"], at))
            sample_evidence(item, kid)
    relationships = []
    for row in associates.values():
        last_by_system, engagements = {}, 0
        for system_id, at in row.pop("events"):
            if system_id not in last_by_system or at - last_by_system[system_id] > timedelta(minutes=30): engagements += 1
            last_by_system[system_id] = at
        row["distinct_days"] = len(row.pop("days_set")); row["estimated_engagements"] = engagements
        row["share_of_subject_kills_percent"] = round(100 * row["kills"] / len(kill_ids), 1) if kill_ids else None
        relationships.append(row)
    relationships.sort(key=lambda row: (-row["kills"], -row["distinct_days"], row["kind"], row["id"]))
    return {"kills": len(kill_ids), "losses": len(loss_ids), "solo_kills": len(solo_ids),
            "smartbomb": {"confirmed_kills": len(smart_ids), "observed_kills": len(kill_ids), "weapon_known_kills": len(known_weapon_ids),
                          "confirmed_percent": round(100 * len(smart_ids) / len(kill_ids), 1) if kill_ids else None,
                          "frequent": len(smart_ids) >= 5 and len(smart_ids) / max(1,len(kill_ids)) >= .2},
            "average_recorded_attacker_count": round(sum(gang_sizes) / len(gang_sizes),1) if gang_sizes else None,
            "systems": sorted(systems.values(), key=lambda row: (-(row["kills"]+row["losses"]),row["id"])),
            "ships": sorted(ships.values(), key=lambda row: (-(row["kills"]+row["losses"]),row["id"])),
            "utc_hours": [{"hour": hour, "appearances": hours[hour]} for hour in range(24)],
            "timeline": [{"date": day, **counts} for day,counts in sorted(timeline.items())],
            "associates": relationships, "evidence": sorted(matched_facts, key=lambda row: row["time"], reverse=True)}
