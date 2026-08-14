from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from itertools import combinations
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import EveAlliance, EveCharacter, EveConstellation, EveCorporation, EveRegion, EveSystem, EveType, Killmail, KillmailAttacker, User
from app.services.killboard_entities import cached_killboard_name_maps
from app.services.permissions import role_rank


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def available_scopes(db: Session, user: User) -> list[dict[str, Any]]:
    owned = db.scalars(select(EveCharacter).where(EveCharacter.owner_user_id == user.id).order_by(EveCharacter.name)).all()
    scopes: list[dict[str, Any]] = [{"scope_type": "account", "scope_id": user.id, "label": "My combined account"}]
    scopes.extend({"scope_type": "character", "scope_id": row.character_id, "label": row.name} for row in owned)
    corporation_ids = {row.corporation_id for row in owned if row.corporation_id is not None}
    if role_rank(user, db) >= role_rank("officer"):
        corporation_ids.update(db.scalars(select(EveCorporation.id)).all())
    if corporation_ids:
        corporations = db.scalars(select(EveCorporation).where(EveCorporation.id.in_(corporation_ids)).order_by(EveCorporation.name)).all()
        scopes.extend({"scope_type": "corporation", "scope_id": row.corporation_id, "label": f"{row.name} [{row.ticker or '—'}]"} for row in corporations)
    if role_rank(user, db) >= role_rank("admin"):
        scopes.append({"scope_type": "all", "scope_id": 0, "label": "All tracked EQM entities"})
    return scopes


def scope_identities(db: Session, user: User, scope_type: str, scope_id: int | None) -> dict[str, set[int]]:
    characters: set[int] = set()
    corporations: set[int] = set()
    if scope_type == "account":
        if scope_id not in {None, user.id}:
            raise PermissionError("Accounts may only view their own combined killboard")
        rows = db.scalars(select(EveCharacter).where(EveCharacter.owner_user_id == user.id)).all()
        characters = {row.character_id for row in rows}
    elif scope_type == "character":
        if scope_id is None:
            raise ValueError("A character scope requires scope_id")
        character = db.scalar(select(EveCharacter).where(EveCharacter.character_id == scope_id))
        if character is None:
            raise LookupError("Tracked character was not found")
        if character.owner_user_id != user.id and role_rank(user, db) < role_rank("officer"):
            raise PermissionError("This character is not linked to your account")
        characters.add(character.character_id)
    elif scope_type == "corporation":
        if scope_id is None:
            raise ValueError("A corporation scope requires scope_id")
        corporation = db.scalar(select(EveCorporation).where(EveCorporation.corporation_id == scope_id))
        if corporation is None:
            raise LookupError("Tracked corporation was not found")
        corporations.add(corporation.corporation_id)
    elif scope_type == "all":
        if role_rank(user, db) < role_rank("admin"):
            raise PermissionError("Administrator access is required for the all-entities scope")
        characters = set(db.scalars(select(EveCharacter.character_id)).all())
        corporations = set(db.scalars(select(EveCorporation.corporation_id)).all())
    else:
        raise ValueError("Unsupported killboard scope")
    return {"characters": characters, "corporations": corporations}


def _matches_victim(killmail: Killmail, identities: dict[str, set[int]]) -> bool:
    return (killmail.victim_character_id in identities["characters"]) or (killmail.victim_corporation_id in identities["corporations"])


def _matching_attackers(killmail: Killmail, identities: dict[str, set[int]]) -> list[KillmailAttacker]:
    return [row for row in killmail.attackers if row.character_id in identities["characters"] or row.corporation_id in identities["corporations"]]


def _rank(counter: Counter[str], limit: int = 8) -> list[dict[str, Any]]:
    return [{"name": name, "count": int(count)} for name, count in counter.most_common(limit)]


def _entity_label(character_id: int | None, corporation_id: int | None, alliance_id: int | None, character_names: dict[int, str], corporation_names: dict[int, str], alliance_names: dict[int, str]) -> str | None:
    if character_id:
        return character_names.get(character_id, f"Character {character_id}")
    if corporation_id:
        return corporation_names.get(corporation_id, f"Corporation {corporation_id}")
    if alliance_id:
        return alliance_names.get(alliance_id, f"Alliance {alliance_id}")
    return None


def _entity_names(db: Session, model: type, id_column: Any, name_column: Any, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    return {int(entity_id): str(name) for entity_id, name in db.execute(select(id_column, name_column).where(id_column.in_(ids))).all()}


def build_killboard_analytics(db: Session, user: User, *, scope_type: str = "account", scope_id: int | None = None, days: int = 30) -> dict[str, Any]:
    days = max(1, min(3650, int(days)))
    identities = scope_identities(db, user, scope_type, scope_id)
    if not identities["characters"] and not identities["corporations"]:
        return empty_analytics(scope_type, scope_id, days)
    cutoff = utc_now() - timedelta(days=days)
    victim_clauses = []
    attacker_clauses = []
    if identities["characters"]:
        victim_clauses.append(Killmail.victim_character_id.in_(identities["characters"]))
        attacker_clauses.append(Killmail.attackers.any(KillmailAttacker.character_id.in_(identities["characters"])))
    if identities["corporations"]:
        victim_clauses.append(Killmail.victim_corporation_id.in_(identities["corporations"]))
        attacker_clauses.append(Killmail.attackers.any(KillmailAttacker.corporation_id.in_(identities["corporations"])))
    rows = db.scalars(
        select(Killmail)
        .where(Killmail.killmail_time >= cutoff, or_(*(victim_clauses + attacker_clauses)))
        .options(selectinload(Killmail.attackers), selectinload(Killmail.enrichment))
        .order_by(Killmail.killmail_time.desc())
    ).all()

    type_ids = {row.victim_ship_type_id for row in rows if row.victim_ship_type_id}
    type_ids.update(attacker.ship_type_id for row in rows for attacker in row.attackers if attacker.ship_type_id)
    type_names = _entity_names(db, EveType, EveType.type_id, EveType.name, set(type_ids))
    system_ids = {row.solar_system_id for row in rows}
    systems = {row.system_id: row for row in db.scalars(select(EveSystem).where(EveSystem.system_id.in_(system_ids)).options(selectinload(EveSystem.constellation).selectinload(EveConstellation.region))).all()} if system_ids else {}

    character_ids = {value for row in rows for value in [row.victim_character_id, *(attacker.character_id for attacker in row.attackers)] if value}
    corporation_ids = {value for row in rows for value in [row.victim_corporation_id, *(attacker.corporation_id for attacker in row.attackers)] if value}
    alliance_ids = {value for row in rows for value in [row.victim_alliance_id, *(attacker.alliance_id for attacker in row.attackers)] if value}
    cached_names = cached_killboard_name_maps(db, {
        "character": set(character_ids), "corporation": set(corporation_ids),
        "alliance": set(alliance_ids), "faction": set(),
    })
    character_names = {**cached_names["character"], **_entity_names(db, EveCharacter, EveCharacter.character_id, EveCharacter.name, set(character_ids))}
    corporation_names = {**cached_names["corporation"], **_entity_names(db, EveCorporation, EveCorporation.corporation_id, EveCorporation.name, set(corporation_ids))}
    alliance_names = {**cached_names["alliance"], **_entity_names(db, EveAlliance, EveAlliance.alliance_id, EveAlliance.name, set(alliance_ids))}

    kills = losses = final_blows = solo_kills = fleet_kills = 0
    isk_destroyed = isk_lost = 0.0
    unknown_values = 0
    damage_done = total_target_damage = 0
    used_hulls: Counter[str] = Counter()
    killed_hulls: Counter[str] = Counter()
    lost_hulls: Counter[str] = Counter()
    systems_counter: Counter[str] = Counter()
    regions_counter: Counter[str] = Counter()
    security_counter: Counter[str] = Counter()
    opponents: Counter[str] = Counter()
    wingmates: Counter[tuple[str, str]] = Counter()
    timeline: dict[str, dict[str, float | int | str]] = defaultdict(lambda: {"kills": 0, "losses": 0, "isk_destroyed": 0.0, "isk_lost": 0.0})
    event_results: list[str] = []
    recent: list[dict[str, Any]] = []

    for row in rows:
        is_loss = _matches_victim(row, identities)
        matching_attackers = _matching_attackers(row, identities)
        is_kill = bool(matching_attackers)
        value = float(row.enrichment.estimated_total_value) if row.enrichment and row.enrichment.estimated_total_value is not None else None
        day = row.killmail_time.date().isoformat()
        system = systems.get(row.solar_system_id)
        if system:
            systems_counter[system.name] += 1
            security_counter[security_class(system.security_status)] += 1
            if system.constellation and system.constellation.region:
                regions_counter[system.constellation.region.name] += 1
        else:
            systems_counter[f"System {row.solar_system_id}"] += 1
            security_counter["Unknown"] += 1

        if is_kill:
            kills += 1
            event_results.append("kill")
            timeline[day]["kills"] += 1
            if value is None:
                unknown_values += 1
            else:
                isk_destroyed += value
                timeline[day]["isk_destroyed"] += value
            if row.enrichment and row.enrichment.solo is True:
                solo_kills += 1
            else:
                fleet_kills += 1
            victim_hull = type_names.get(row.victim_ship_type_id or 0, f"Type {row.victim_ship_type_id}" if row.victim_ship_type_id else "Unknown hull")
            killed_hulls[victim_hull] += 1
            for attacker in matching_attackers:
                used_hulls[type_names.get(attacker.ship_type_id or 0, f"Type {attacker.ship_type_id}" if attacker.ship_type_id else "Unknown hull")] += 1
                damage_done += attacker.damage_done
                final_blows += int(attacker.final_blow)
            total_target_damage += max(0, row.damage_taken)
            opponent_name = _entity_label(row.victim_character_id, row.victim_corporation_id, row.victim_alliance_id, character_names, corporation_names, alliance_names)
            if opponent_name:
                opponents[opponent_name] += 1
            participating = sorted({character_names.get(attacker.character_id or 0) for attacker in matching_attackers if character_names.get(attacker.character_id or 0)})
            for pair in combinations(participating, 2):
                wingmates[pair] += 1
        if is_loss:
            losses += 1
            event_results.append("loss")
            timeline[day]["losses"] += 1
            if value is None:
                unknown_values += 1
            else:
                isk_lost += value
                timeline[day]["isk_lost"] += value
            lost_hulls[type_names.get(row.victim_ship_type_id or 0, f"Type {row.victim_ship_type_id}" if row.victim_ship_type_id else "Unknown hull")] += 1
            for attacker in row.attackers:
                if attacker.character_id in identities["characters"] or attacker.corporation_id in identities["corporations"]:
                    continue
                opponent_name = _entity_label(attacker.character_id, attacker.corporation_id, attacker.alliance_id, character_names, corporation_names, alliance_names)
                if opponent_name:
                    opponents[opponent_name] += 1

        if len(recent) < 50:
            recent.append(serialize_recent(row, is_kill, is_loss, value, type_names, systems, character_names, corporation_names, alliance_names))

    current_streak = 0
    current_kind = event_results[0] if event_results else None
    for result in event_results:
        if result != current_kind:
            break
        current_streak += 1
    longest_kill = longest_loss = running_kill = running_loss = 0
    for result in reversed(event_results):
        running_kill = running_kill + 1 if result == "kill" else 0
        running_loss = running_loss + 1 if result == "loss" else 0
        longest_kill = max(longest_kill, running_kill)
        longest_loss = max(longest_loss, running_loss)

    known_total = isk_destroyed + isk_lost
    return {
        "scope": {"scope_type": scope_type, "scope_id": scope_id}, "days": days,
        "coverage": {
            "warning": "zKillboard discovery is best-effort and may not represent complete activity. Displayed killmail details are canonical ESI records; values and classifications are zKill-derived.",
            "record_count": len(rows), "earliest": rows[-1].killmail_time.isoformat() if rows else None,
            "latest": rows[0].killmail_time.isoformat() if rows else None, "unknown_value_records": unknown_values,
        },
        "summary": {
            "kills": kills, "losses": losses, "isk_destroyed": isk_destroyed, "isk_lost": isk_lost,
            "efficiency": (isk_destroyed / known_total * 100) if known_total else None,
            "solo_kills": solo_kills, "fleet_kills": fleet_kills, "final_blows": final_blows,
            "damage_done": damage_done, "damage_contribution_percent": (damage_done / total_target_damage * 100) if total_target_damage else None,
            "inactivity_days": max(0, (utc_now().date() - rows[0].killmail_time.date()).days) if rows else None,
        },
        "hulls": {"most_used": _rank(used_hulls), "most_killed": _rank(killed_hulls), "most_lost": _rank(lost_hulls)},
        "geography": {"systems": _rank(systems_counter), "regions": _rank(regions_counter), "security_classes": _rank(security_counter)},
        "opponents": _rank(opponents, 12),
        "streaks": {"current_kind": current_kind, "current": current_streak, "longest_kill": longest_kill, "longest_loss": longest_loss},
        "wingmates": [{"characters": list(pair), "shared_kills": count} for pair, count in wingmates.most_common(10)],
        "timeline": [{"date": day, **values} for day, values in sorted(timeline.items())],
        "recent": recent,
    }


def security_class(value: float | None) -> str:
    if value is None:
        return "Unknown"
    if value >= 0.45:
        return "Highsec"
    if value > 0:
        return "Lowsec"
    return "Nullsec / Wormhole"


def serialize_recent(row: Killmail, is_kill: bool, is_loss: bool, value: float | None, type_names: dict[int, str], systems: dict[int, EveSystem], character_names: dict[int, str], corporation_names: dict[int, str], alliance_names: dict[int, str]) -> dict[str, Any]:
    final = next((attacker for attacker in row.attackers if attacker.final_blow), None)
    system = systems.get(row.solar_system_id)
    return {
        "killmail_id": row.killmail_id, "killmail_time": row.killmail_time.isoformat(),
        "result": "friendly_fire" if is_kill and is_loss else "loss" if is_loss else "kill",
        "system_id": row.solar_system_id, "system_name": system.name if system else f"System {row.solar_system_id}",
        "region_name": system.constellation.region.name if system and system.constellation and system.constellation.region else None,
        "victim": {
            "character_id": row.victim_character_id, "character_name": character_names.get(row.victim_character_id or 0, f"Character {row.victim_character_id}" if row.victim_character_id else None),
            "corporation_id": row.victim_corporation_id, "corporation_name": corporation_names.get(row.victim_corporation_id or 0, f"Corporation {row.victim_corporation_id}" if row.victim_corporation_id else None),
            "alliance_id": row.victim_alliance_id, "alliance_name": alliance_names.get(row.victim_alliance_id or 0, f"Alliance {row.victim_alliance_id}" if row.victim_alliance_id else None),
            "ship_type_id": row.victim_ship_type_id, "ship_type_name": type_names.get(row.victim_ship_type_id or 0, f"Type {row.victim_ship_type_id}" if row.victim_ship_type_id else "Unknown hull"),
        },
        "final_blow": {
            "character_id": final.character_id, "character_name": character_names.get(final.character_id or 0, f"Character {final.character_id}" if final.character_id else None),
            "corporation_id": final.corporation_id, "corporation_name": corporation_names.get(final.corporation_id or 0, f"Corporation {final.corporation_id}" if final.corporation_id else None),
            "ship_type_id": final.ship_type_id, "ship_type_name": type_names.get(final.ship_type_id or 0),
        } if final else None,
        "attacker_count": len(row.attackers), "estimated_total_value": value,
        "points": row.enrichment.points if row.enrichment else None,
        "solo": row.enrichment.solo if row.enrichment else None, "npc": row.enrichment.npc if row.enrichment else None,
        "awox": row.enrichment.awox if row.enrichment else None,
        "zkill_url": row.enrichment.zkill_url if row.enrichment else f"https://zkillboard.com/kill/{row.killmail_id}/",
    }


def empty_analytics(scope_type: str, scope_id: int | None, days: int) -> dict[str, Any]:
    return {
        "scope": {"scope_type": scope_type, "scope_id": scope_id}, "days": days,
        "coverage": {"warning": "No locally cached canonical killmails match this scope. zKillboard discovery is best-effort and may not represent complete activity.", "record_count": 0, "earliest": None, "latest": None, "unknown_value_records": 0},
        "summary": {"kills": 0, "losses": 0, "isk_destroyed": 0, "isk_lost": 0, "efficiency": None, "solo_kills": 0, "fleet_kills": 0, "final_blows": 0, "damage_done": 0, "damage_contribution_percent": None, "inactivity_days": None},
        "hulls": {"most_used": [], "most_killed": [], "most_lost": []}, "geography": {"systems": [], "regions": [], "security_classes": []},
        "opponents": [], "streaks": {"current_kind": None, "current": 0, "longest_kill": 0, "longest_loss": 0}, "wingmates": [], "timeline": [], "recent": [],
    }
