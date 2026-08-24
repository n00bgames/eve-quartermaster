from __future__ import annotations

from collections import Counter, defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import EveAlliance, EveCharacter, EveConstellation, EveCorporation, EveGroup, EveRegion, EveSystem, EveType, Killmail, KillmailAttacker, User
from app.services.killboard_entities import cached_killboard_name_maps
from app.services.permissions import role_rank


def available_report_pilots(db: Session, user: User) -> list[dict[str, Any]]:
    query = select(EveCharacter).order_by(EveCharacter.name)
    if role_rank(user, db) < role_rank("officer"):
        query = query.where(EveCharacter.owner_user_id == user.id)
    return [
        {
            "character_id": row.character_id,
            "name": row.name,
            "corporation_id": row.corporation_id,
        }
        for row in db.scalars(query).all()
    ]


def _require_report_pilot(db: Session, user: User, character_id: int) -> EveCharacter:
    character = db.scalar(select(EveCharacter).where(EveCharacter.character_id == character_id))
    if character is None:
        raise LookupError("Tracked character was not found")
    if character.owner_user_id != user.id and role_rank(user, db) < role_rank("officer"):
        raise PermissionError("This character is not linked to your account")
    return character


def _affiliation(
    character_id: int | None,
    corporation_id: int | None,
    alliance_id: int | None,
    faction_id: int | None,
) -> str | None:
    if alliance_id:
        return f"alliance:{alliance_id}"
    if corporation_id:
        return f"corporation:{corporation_id}"
    if faction_id:
        return f"faction:{faction_id}"
    if character_id:
        return f"character:{character_id}"
    return None


def _victim_affiliation(row: Killmail) -> str | None:
    return _affiliation(row.victim_character_id, row.victim_corporation_id, row.victim_alliance_id, row.victim_faction_id)


def _attacker_affiliation(row: KillmailAttacker) -> str | None:
    return _affiliation(row.character_id, row.corporation_id, row.alliance_id, row.faction_id)


def _affiliation_aliases(
    character_id: int | None,
    corporation_id: int | None,
    alliance_id: int | None,
    faction_id: int | None,
) -> set[str]:
    """Return equivalent identity nodes for one participant.

    Killmails occasionally omit an alliance on one appearance while including it
    on another. Linking the character, corporation, and alliance prevents that
    incomplete payload from splitting one organization across report sides.
    """
    values = {
        f"character:{character_id}" if character_id else None,
        f"corporation:{corporation_id}" if corporation_id else None,
        f"alliance:{alliance_id}" if alliance_id else None,
    }
    if not corporation_id and not alliance_id and faction_id:
        values.add(f"faction:{faction_id}")
    return {value for value in values if value}


def _victim_affiliation_aliases(row: Killmail) -> set[str]:
    return _affiliation_aliases(row.victim_character_id, row.victim_corporation_id, row.victim_alliance_id, row.victim_faction_id)


def _attacker_affiliation_aliases(row: KillmailAttacker) -> set[str]:
    return _affiliation_aliases(row.character_id, row.corporation_id, row.alliance_id, row.faction_id)


def _killmail_affiliations(row: Killmail) -> set[str]:
    values = {_victim_affiliation(row), *(_attacker_affiliation(attacker) for attacker in row.attackers)}
    return {value for value in values if value}


def _pilot_affiliation(row: Killmail, character_id: int) -> str | None:
    if row.victim_character_id == character_id:
        return _victim_affiliation(row)
    attacker = next((item for item in row.attackers if item.character_id == character_id), None)
    return _attacker_affiliation(attacker) if attacker else None


def _connected_killmails(rows: list[Killmail], seed: Killmail, pilot_affiliation: str | None) -> list[Killmail]:
    included_ids = {seed.killmail_id}
    affiliations = _killmail_affiliations(seed)
    if pilot_affiliation:
        affiliations.add(pilot_affiliation)
    changed = True
    while changed:
        changed = False
        for row in rows:
            if row.killmail_id in included_ids:
                continue
            row_affiliations = _killmail_affiliations(row)
            if affiliations.intersection(row_affiliations):
                included_ids.add(row.killmail_id)
                affiliations.update(row_affiliations)
                changed = True
    return [row for row in rows if row.killmail_id in included_ids]


def _side_map(rows: Iterable[Killmail], selected_affiliation: str | None) -> dict[str, int]:
    same_edges: dict[str, set[str]] = defaultdict(set)
    opposite_edges: dict[str, set[str]] = defaultdict(set)
    nodes: set[str] = set()
    for row in rows:
        victim = _victim_affiliation(row)
        victim_aliases = _victim_affiliation_aliases(row)
        attacker_aliases = [(attacker, _attacker_affiliation_aliases(attacker)) for attacker in row.attackers]
        participant_aliases = [victim_aliases, *(aliases for _, aliases in attacker_aliases)]
        for aliases in participant_aliases:
            nodes.update(aliases)
            if aliases:
                leader = sorted(aliases)[0]
                for alias in aliases - {leader}:
                    same_edges[leader].add(alias)
                    same_edges[alias].add(leader)
        attackers = sorted({
            affiliation
            for attacker, aliases in attacker_aliases
            if (affiliation := _attacker_affiliation(attacker)) and not aliases.intersection(victim_aliases)
        })
        if victim:
            nodes.add(victim)
        nodes.update(attackers)
        if attackers:
            leader = attackers[0]
            for attacker in attackers[1:]:
                same_edges[leader].add(attacker)
                same_edges[attacker].add(leader)
            if victim:
                for attacker in attackers:
                    opposite_edges[attacker].add(victim)
                    opposite_edges[victim].add(attacker)

    if selected_affiliation is None:
        selected_affiliation = next(iter(nodes), None)
    assigned: dict[str, int] = {}
    conflicted: set[str] = set()
    if selected_affiliation:
        assigned[selected_affiliation] = 0
        queue: deque[str] = deque([selected_affiliation])
        while queue:
            current = queue.popleft()
            for neighbor in same_edges[current]:
                proposed = assigned[current]
                if neighbor in assigned and assigned[neighbor] != proposed:
                    conflicted.update({current, neighbor})
                elif neighbor not in assigned:
                    assigned[neighbor] = proposed
                    queue.append(neighbor)
            for neighbor in opposite_edges[current]:
                proposed = 1 - assigned[current]
                if neighbor in assigned and assigned[neighbor] != proposed:
                    conflicted.update({current, neighbor})
                elif neighbor not in assigned:
                    assigned[neighbor] = proposed
                    queue.append(neighbor)
    for node in nodes:
        if node == selected_affiliation:
            assigned[node] = 0
        elif node not in assigned or node in conflicted:
            assigned[node] = 2
    return assigned


def _names(db: Session, rows: list[Killmail]) -> dict[str, dict[int, str]]:
    character_ids = {value for row in rows for value in [row.victim_character_id, *(attacker.character_id for attacker in row.attackers)] if value}
    corporation_ids = {value for row in rows for value in [row.victim_corporation_id, *(attacker.corporation_id for attacker in row.attackers)] if value}
    alliance_ids = {value for row in rows for value in [row.victim_alliance_id, *(attacker.alliance_id for attacker in row.attackers)] if value}
    faction_ids = {value for row in rows for value in [row.victim_faction_id, *(attacker.faction_id for attacker in row.attackers)] if value}
    cached = cached_killboard_name_maps(db, {
        "character": set(character_ids), "corporation": set(corporation_ids),
        "alliance": set(alliance_ids), "faction": set(faction_ids),
    })

    def merge(model: type, id_column: Any, name_column: Any, ids: set[int], category: str) -> dict[int, str]:
        local = {int(entity_id): str(name) for entity_id, name in db.execute(select(id_column, name_column).where(id_column.in_(ids))).all()} if ids else {}
        return {**cached[category], **local}

    return {
        "character": merge(EveCharacter, EveCharacter.character_id, EveCharacter.name, set(character_ids), "character"),
        "corporation": merge(EveCorporation, EveCorporation.corporation_id, EveCorporation.name, set(corporation_ids), "corporation"),
        "alliance": merge(EveAlliance, EveAlliance.alliance_id, EveAlliance.name, set(alliance_ids), "alliance"),
        "faction": cached["faction"],
    }


def _team_for(side_map: dict[str, int], affiliation: str | None) -> int:
    return side_map.get(affiliation or "", 2)


def _pilot_killmails(db: Session, character_id: int) -> list[Killmail]:
    involved = or_(
        Killmail.victim_character_id == character_id,
        Killmail.attackers.any(KillmailAttacker.character_id == character_id),
    )
    return list(db.scalars(
        select(Killmail)
        .where(involved)
        .options(selectinload(Killmail.attackers), selectinload(Killmail.enrichment))
        .order_by(Killmail.killmail_time.desc())
        .limit(250)
    ).all())


def _pilot_activity_clusters(
    pilot_rows: list[Killmail],
    *,
    gap: timedelta,
    maximum_span: timedelta,
) -> list[list[Killmail]]:
    clusters: list[list[Killmail]] = []
    index = 0
    while index < len(pilot_rows):
        seed = pilot_rows[index]
        cluster = [seed]
        previous = seed.killmail_time
        index += 1
        while index < len(pilot_rows):
            candidate = pilot_rows[index]
            if seed.killmail_time - candidate.killmail_time > maximum_span or previous - candidate.killmail_time > gap:
                break
            cluster.append(candidate)
            previous = candidate.killmail_time
            index += 1
        clusters.append(cluster)
    return clusters


def battle_report_history(
    db: Session,
    user: User,
    *,
    character_id: int,
    gap_minutes: int = 15,
    max_duration_hours: int = 6,
    limit: int = 50,
) -> dict[str, Any]:
    pilot = _require_report_pilot(db, user, character_id)
    gap_minutes = max(5, min(60, int(gap_minutes)))
    max_duration_hours = max(1, min(12, int(max_duration_hours)))
    pilot_rows = _pilot_killmails(db, character_id)
    clusters = _pilot_activity_clusters(
        pilot_rows,
        gap=timedelta(minutes=gap_minutes),
        maximum_span=timedelta(hours=max_duration_hours),
    )
    selected_clusters = clusters[:max(1, min(250, int(limit)))]
    system_ids = {row.solar_system_id for cluster in selected_clusters for row in cluster}
    system_names = dict(db.execute(
        select(EveSystem.system_id, EveSystem.name).where(EveSystem.system_id.in_(system_ids))
    ).all()) if system_ids else {}
    return {
        "pilot": {"character_id": pilot.character_id, "name": pilot.name},
        "reports": [
            {
                "seed_killmail_id": cluster[0].killmail_id,
                "start_time": cluster[-1].killmail_time.isoformat(),
                "end_time": cluster[0].killmail_time.isoformat(),
                "pilot_killmail_count": len(cluster),
                "systems": [
                    {"system_id": system_id, "system_name": system_names.get(system_id, f"System {system_id}")}
                    for system_id in sorted({row.solar_system_id for row in cluster})
                ],
            }
            for cluster in selected_clusters
        ],
        "total_reports": len(clusters),
        "coverage": {
            "warning": "History is grouped from the selected pilot's 250 most recent locally retained killmails. zKillboard discovery remains best-effort and may be incomplete.",
            "grouping_gap_minutes": gap_minutes,
        },
    }


def build_latest_battle_report(
    db: Session,
    user: User,
    *,
    character_id: int,
    gap_minutes: int = 15,
    max_duration_hours: int = 6,
    seed_killmail_id: int | None = None,
    side_overrides: dict[int, int] | None = None,
    organization_overrides: dict[tuple[str, int], int] | None = None,
) -> dict[str, Any]:
    pilot = _require_report_pilot(db, user, character_id)
    gap_minutes = max(5, min(60, int(gap_minutes)))
    max_duration_hours = max(1, min(12, int(max_duration_hours)))
    pilot_rows = _pilot_killmails(db, character_id)
    if not pilot_rows:
        return {
            "pilot": {"character_id": pilot.character_id, "name": pilot.name},
            "report": None,
            "coverage": {
                "warning": "No locally cached killmail involves this pilot. Run Killboard sync and try again. zKillboard discovery is best-effort and may not be complete.",
                "canonical_source": "ESI",
                "discovery_source": "zKillboard",
            },
        }

    gap = timedelta(minutes=gap_minutes)
    maximum_span = timedelta(hours=max_duration_hours)
    clusters = _pilot_activity_clusters(pilot_rows, gap=gap, maximum_span=maximum_span)
    if seed_killmail_id is None:
        pilot_cluster = clusters[0]
    else:
        pilot_cluster = next((cluster for cluster in clusters if cluster[0].killmail_id == seed_killmail_id), None)
        if pilot_cluster is None:
            raise LookupError("The selected battle is not available in this pilot's retained report history")
    seed = pilot_cluster[0]

    system_ids = {row.solar_system_id for row in pilot_cluster}
    window_start = pilot_cluster[-1].killmail_time - gap
    window_end = seed.killmail_time + gap
    candidates = db.scalars(
        select(Killmail)
        .where(
            Killmail.solar_system_id.in_(system_ids),
            Killmail.killmail_time >= window_start,
            Killmail.killmail_time <= window_end,
        )
        .options(selectinload(Killmail.attackers), selectinload(Killmail.enrichment))
        .order_by(Killmail.killmail_time.asc())
    ).all()
    selected_affiliation = _pilot_affiliation(seed, character_id)
    rows = _connected_killmails(list(candidates), seed, selected_affiliation)
    rows.sort(key=lambda item: item.killmail_time)
    sides = _side_map(rows, selected_affiliation)
    manual_sides = {
        int(pilot_id): int(side)
        for pilot_id, side in (side_overrides or {}).items()
        if int(pilot_id) != character_id and int(side) in {0, 1, 2}
    }
    manual_organizations = {
        (str(kind), int(organization_id)): int(side)
        for (kind, organization_id), side in (organization_overrides or {}).items()
        if str(kind) in {"alliance", "corporation"} and int(organization_id) > 0 and int(side) in {0, 1, 2}
    }

    def classified_side(
        pilot_id: int | None,
        corporation_id: int | None,
        alliance_id: int | None,
        affiliation: str | None,
    ) -> int:
        if pilot_id == character_id:
            return 0
        if pilot_id is not None and pilot_id in manual_sides:
            return manual_sides[pilot_id]
        if corporation_id is not None and ("corporation", corporation_id) in manual_organizations:
            return manual_organizations[("corporation", corporation_id)]
        if alliance_id is not None and ("alliance", alliance_id) in manual_organizations:
            return manual_organizations[("alliance", alliance_id)]
        return _team_for(sides, affiliation)

    names = _names(db, rows)

    type_ids = {row.victim_ship_type_id for row in rows if row.victim_ship_type_id}
    type_ids.update(attacker.ship_type_id for row in rows for attacker in row.attackers if attacker.ship_type_id)
    type_rows = db.execute(
        select(EveType.type_id, EveType.name, EveGroup.group_id, EveGroup.name)
        .outerjoin(EveGroup, EveGroup.group_id == EveType.group_id)
        .where(EveType.type_id.in_(type_ids))
    ).all() if type_ids else []
    type_names = {int(type_id): str(type_name) for type_id, type_name, _, _ in type_rows}
    type_groups = {
        int(type_id): {"ship_group_id": group_id, "ship_group_name": str(group_name) if group_name else None}
        for type_id, _, group_id, group_name in type_rows
    }
    systems = {
        row.system_id: row
        for row in db.scalars(
            select(EveSystem)
            .where(EveSystem.system_id.in_({item.solar_system_id for item in rows}))
            .options(selectinload(EveSystem.constellation).selectinload(EveConstellation.region))
        ).all()
    }

    team_values: dict[int, dict[str, Any]] = {
        index: {
            "side": index,
            "label": "Selected pilot's side" if index == 0 else "Opposing side" if index == 1 else "Third parties / ambiguous",
            "pilot_ids": set(), "corporation_ids": set(), "alliance_ids": set(),
            "ships_lost": 0, "isk_lost": 0.0, "unknown_value_losses": 0, "damage_inflicted": 0,
            "organizations": Counter(),
        }
        for index in range(3)
    }
    participants: dict[int, dict[str, Any]] = {}
    composition: dict[int, dict[int, dict[str, Any]]] = defaultdict(lambda: defaultdict(lambda: {"pilot_ids": set(), "involved": 0, "lost": 0, "loss_value": 0.0}))
    timeline: list[dict[str, Any]] = []

    def participant(character: int, corporation: int | None, alliance: int | None, side: int) -> dict[str, Any]:
        row = participants.setdefault(character, {
            "character_id": character,
            "character_name": names["character"].get(character, f"Character {character}"),
            "corporation_id": corporation,
            "corporation_name": names["corporation"].get(corporation or 0, f"Corporation {corporation}" if corporation else None),
            "alliance_id": alliance,
            "alliance_name": names["alliance"].get(alliance or 0, f"Alliance {alliance}" if alliance else None),
            "side": side,
            "ship_type_ids": set(),
            "damage_done": 0,
            "damage_taken": 0,
            "killmail_participations": 0,
            "final_blows": 0,
            "losses": 0,
            "loss_value": 0.0,
        })
        if row["side"] != side:
            row["side"] = 2
        return row

    total_value = 0.0
    unknown_values = 0
    for row in rows:
        value = float(row.enrichment.estimated_total_value) if row.enrichment and row.enrichment.estimated_total_value is not None else None
        if value is None:
            unknown_values += 1
        else:
            total_value += value
        victim_side = classified_side(row.victim_character_id, row.victim_corporation_id, row.victim_alliance_id, _victim_affiliation(row))
        victim_name = names["character"].get(row.victim_character_id or 0) or names["corporation"].get(row.victim_corporation_id or 0) or "Unknown or NPC victim"
        hull_name = type_names.get(row.victim_ship_type_id or 0, f"Type {row.victim_ship_type_id}" if row.victim_ship_type_id else "Unknown hull")
        team_values[victim_side]["ships_lost"] += 1
        if value is None:
            team_values[victim_side]["unknown_value_losses"] += 1
        else:
            team_values[victim_side]["isk_lost"] += value
        if row.victim_character_id:
            victim = participant(row.victim_character_id, row.victim_corporation_id, row.victim_alliance_id, victim_side)
            victim["losses"] += 1
            victim["damage_taken"] += max(0, row.damage_taken)
            victim["loss_value"] += value or 0.0
            if row.victim_ship_type_id:
                victim["ship_type_ids"].add(row.victim_ship_type_id)
                ship = composition[victim_side][row.victim_ship_type_id]
                ship["pilot_ids"].add(row.victim_character_id)
                ship["involved"] += 1
                ship["lost"] += 1
                ship["loss_value"] += value or 0.0
        for attacker in row.attackers:
            attacker_side = classified_side(attacker.character_id, attacker.corporation_id, attacker.alliance_id, _attacker_affiliation(attacker))
            team_values[attacker_side]["damage_inflicted"] += max(0, attacker.damage_done)
            if attacker.character_id:
                actor = participant(attacker.character_id, attacker.corporation_id, attacker.alliance_id, attacker_side)
                actor["damage_done"] += max(0, attacker.damage_done)
                actor["killmail_participations"] += 1
                actor["final_blows"] += int(attacker.final_blow)
                if attacker.ship_type_id:
                    actor["ship_type_ids"].add(attacker.ship_type_id)
                    ship = composition[attacker_side][attacker.ship_type_id]
                    ship["pilot_ids"].add(attacker.character_id)
                    ship["involved"] += 1
        system = systems.get(row.solar_system_id)
        timeline.append({
            "killmail_id": row.killmail_id,
            "killmail_time": row.killmail_time.isoformat(),
            "system_id": row.solar_system_id,
            "system_name": system.name if system else f"System {row.solar_system_id}",
            "victim_name": victim_name,
            "victim_character_id": row.victim_character_id,
            "victim_corporation_id": row.victim_corporation_id,
            "victim_corporation_name": names["corporation"].get(row.victim_corporation_id or 0),
            "victim_alliance_id": row.victim_alliance_id,
            "victim_alliance_name": names["alliance"].get(row.victim_alliance_id or 0),
            "victim_ship_type_id": row.victim_ship_type_id,
            "victim_ship_type_name": hull_name,
            "victim_side": victim_side,
            "damage_taken": row.damage_taken,
            "estimated_total_value": value,
            "attacker_count": len(row.attackers),
            "zkill_url": row.enrichment.zkill_url if row.enrichment else f"https://zkillboard.com/kill/{row.killmail_id}/",
        })

    for row in participants.values():
        side = int(row["side"])
        team_values[side]["pilot_ids"].add(row["character_id"])
        if row["corporation_id"]:
            team_values[side]["corporation_ids"].add(row["corporation_id"])
        if row["alliance_id"]:
            team_values[side]["alliance_ids"].add(row["alliance_id"])
        if row["alliance_id"]:
            organization_id = int(row["alliance_id"])
            organization_name = names["alliance"].get(organization_id, f"Alliance {organization_id}")
            team_values[side]["organizations"][("alliance", organization_id, organization_name)] += 1
        elif row["corporation_id"]:
            organization_id = int(row["corporation_id"])
            organization_name = names["corporation"].get(organization_id, f"Corporation {organization_id}")
            team_values[side]["organizations"][("corporation", organization_id, organization_name)] += 1
        participant_ship_ids = sorted(row.pop("ship_type_ids"))
        row["ship_type_names"] = [type_names.get(type_id, f"Type {type_id}") for type_id in participant_ship_ids]
        row["ships"] = [
            {
                "type_id": type_id,
                "type_name": type_names.get(type_id, f"Type {type_id}"),
                "ship_group_id": type_groups.get(type_id, {}).get("ship_group_id"),
                "ship_group_name": type_groups.get(type_id, {}).get("ship_group_name"),
            }
            for type_id in participant_ship_ids
        ]

    known_total = sum(float(team["isk_lost"]) for team in team_values.values())
    teams = []
    for side, team in team_values.items():
        if side == 2 and not team["pilot_ids"] and not team["ships_lost"]:
            continue
        inflicted_value = known_total - float(team["isk_lost"])
        teams.append({
            "side": side,
            "label": team["label"],
            "pilot_count": len(team["pilot_ids"]),
            "corporation_count": len(team["corporation_ids"]),
            "alliance_count": len(team["alliance_ids"]),
            "ships_lost": team["ships_lost"],
            "isk_lost": team["isk_lost"],
            "unknown_value_losses": team["unknown_value_losses"],
            "damage_inflicted": team["damage_inflicted"],
            "efficiency": (inflicted_value / known_total * 100) if known_total else None,
            "organizations": [
                {"organization_type": kind, "organization_id": organization_id, "name": name, "pilot_count": count}
                for (kind, organization_id, name), count in team["organizations"].most_common(12)
            ],
        })

    composition_payload = []
    for side, ships in composition.items():
        for type_id, values in ships.items():
            composition_payload.append({
                "side": side,
                "ship_type_id": type_id,
                "ship_type_name": type_names.get(type_id, f"Type {type_id}"),
                "ship_group_id": type_groups.get(type_id, {}).get("ship_group_id"),
                "ship_group_name": type_groups.get(type_id, {}).get("ship_group_name"),
                "pilots": len(values["pilot_ids"]),
                "involved": values["involved"],
                "lost": values["lost"],
                "loss_value": values["loss_value"],
            })
    composition_payload.sort(key=lambda item: (item["side"], -item["involved"], item["ship_type_name"]))
    participant_payload = sorted(participants.values(), key=lambda row: (row["side"], -row["damage_done"], row["character_name"]))
    system_payload = []
    region_names: set[str] = set()
    for system_id in sorted({row.solar_system_id for row in rows}):
        system = systems.get(system_id)
        region_name = system.constellation.region.name if system and system.constellation and system.constellation.region else None
        if region_name:
            region_names.add(region_name)
        system_payload.append({
            "system_id": system_id,
            "system_name": system.name if system else f"System {system_id}",
            "security_status": system.security_status if system else None,
            "region_name": region_name,
        })

    start = rows[0].killmail_time
    end = rows[-1].killmail_time
    return {
        "pilot": {"character_id": pilot.character_id, "name": pilot.name},
        "report": {
            "seed_killmail_id": seed.killmail_id,
            "side_overrides": manual_sides,
            "organization_overrides": [
                {"organization_type": kind, "organization_id": organization_id, "side": side}
                for (kind, organization_id), side in sorted(manual_organizations.items())
            ],
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "duration_seconds": max(0, int((end - start).total_seconds())),
            "gap_minutes": gap_minutes,
            "systems": system_payload,
            "regions": sorted(region_names),
            "killmail_count": len(rows),
            "pilot_count": len(participants),
            "estimated_total_value": total_value,
            "unknown_value_killmails": unknown_values,
            "teams": teams,
            "participants": participant_payload,
            "timeline": timeline,
            "composition": composition_payload,
        },
        "coverage": {
            "warning": "This report is reconstructed from locally cached killmails discovered through zKillboard. Discovery may be incomplete; killmail facts are canonical ESI records and ISK values are zKillboard estimates.",
            "canonical_source": "ESI",
            "discovery_source": "zKillboard",
            "grouping_rule": f"Latest pilot activity connected by gaps of at most {gap_minutes} minutes, then affiliation-connected killmails in the same systems and window.",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        },
    }
