"""Owner-only aggregates over stored journeys and permission-gated killmails.

These queries aggregate the full scope in SQL, independently of replay limits.
Travel observations and killmail hulls remain separate evidence sources.
"""
from datetime import datetime, timezone

from sqlalchemy import String, and_, case, cast, distinct, func, literal, or_, select

from app.models import EveCharacter, EveSystem, EveType, Killmail, KillmailAttacker
from app.models.journey import JourneyShipSegment, JourneyTracker, JourneyVisit
from app.services import journey
from app.services.permissions import can_view_section


def combat_allowed(db, user):
    return any(can_view_section(user, section, db) for section in ("killboard", "battle_reports", "intel_reports"))


def duration(first, last, start, end):
    clipped_first = case((first < start, start), else_=first)
    clipped_last = case((last > end, end), else_=last)
    seconds = func.extract("epoch", clipped_last) - func.extract("epoch", clipped_first)
    return case((seconds > 0, seconds), else_=0)


def rank(db, query, limit):
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    rows = [dict(row) for row in db.execute(query.limit(limit)).mappings()]
    for row in rows:
        if "observed_seconds" in row:
            row["observed_seconds"] = float(row["observed_seconds"] or 0)
    return {"rows": rows, "total": total, "limit": limit, "truncated": total > limit}


def system_name(column):
    return func.coalesce(EveSystem.name, literal("System ") + cast(column, String))


def ship_name(column):
    return func.coalesce(EveType.name, case((column.is_(None), "Unknown hull"),
        else_=literal("Type ") + cast(column, String)))


def overview(db, user, character_id=None, period="range", from_at=None, to_at=None, ship_order="visits", limit=10):
    at = journey.now()
    start, end = journey.window(from_at, to_at) if period == "range" else (datetime(2003, 1, 1, tzinfo=timezone.utc), at)
    character = journey.own_character(db, user, character_id) if character_id is not None else None
    cohort_query = select(EveCharacter.id.label("character_id"), EveCharacter.character_id.label("eve_id"), EveCharacter.name)
    cohort_query = cohort_query.where(EveCharacter.owner_user_id == user.id)
    if character is not None:
        cohort_query = cohort_query.where(EveCharacter.id == character.id)
    cohort = cohort_query.subquery("analytics_pilots")
    trackers = select(JourneyTracker.id.label("tracker_id"), cohort.c.character_id).join(
        cohort, cohort.c.character_id == JourneyTracker.character_id).where(JourneyTracker.user_id == user.id).subquery()

    # Lag sees the preceding visit even when it predates the selected range.
    order = (JourneyVisit.first_seen_at, JourneyVisit.id)
    visits = select(JourneyVisit.id, JourneyVisit.system_id, JourneyVisit.first_seen_at, JourneyVisit.last_seen_at,
        JourneyVisit.gap_before, trackers.c.character_id,
        func.lag(JourneyVisit.system_id).over(partition_by=JourneyVisit.tracker_id, order_by=order).label("previous_system"))\
        .join(trackers, trackers.c.tracker_id == JourneyVisit.tracker_id).where(JourneyVisit.first_seen_at < end).subquery()
    window = select(visits).where(visits.c.last_seen_at >= start).subquery()
    jump = case((and_(visits.c.first_seen_at >= start, visits.c.gap_before.is_(False),
        visits.c.previous_system.is_not(None), visits.c.previous_system != visits.c.system_id), 1), else_=0)
    jump_stats = select(visits.c.character_id, func.sum(jump).label("jumps")).group_by(visits.c.character_id).subquery()
    pilot_visits = select(window.c.character_id, func.count().label("visits"),
        func.count(distinct(window.c.system_id)).label("systems")).group_by(window.c.character_id).subquery()
    total_visits, total_systems = db.execute(select(func.count(), func.count(distinct(window.c.system_id))).select_from(window)).one()
    total_jumps = db.scalar(select(func.coalesce(func.sum(jump_stats.c.jumps), 0))) or 0

    hull = select(JourneyShipSegment.id, JourneyShipSegment.visit_id, JourneyShipSegment.ship_type_id,
        duration(JourneyShipSegment.first_seen_at, JourneyShipSegment.last_seen_at, start, end).label("observed_seconds"))\
        .join(window, window.c.id == JourneyShipSegment.visit_id).where(
            JourneyShipSegment.first_seen_at < end, JourneyShipSegment.last_seen_at >= start).subquery()
    hull_stats = select(hull.c.ship_type_id, func.count(distinct(hull.c.visit_id)).label("visits"),
        func.count().label("segments"), func.sum(hull.c.observed_seconds).label("observed_seconds"))\
        .group_by(hull.c.ship_type_id).subquery()
    hull_seconds, known_visits = db.execute(select(func.coalesce(func.sum(hull.c.observed_seconds), 0),
        func.count(distinct(hull.c.visit_id)))).one()
    systems = select(window.c.system_id, system_name(window.c.system_id).label("name"), func.count().label("visits"))\
        .outerjoin(EveSystem, EveSystem.system_id == window.c.system_id).group_by(window.c.system_id, EveSystem.name)\
        .order_by(func.count().desc(), system_name(window.c.system_id), window.c.system_id)

    available = combat_allowed(db, user)
    kills = losses = None
    kill_hulls = pilot_kills = pilot_losses = None
    empty = {"rows": [], "total": 0, "limit": limit, "truncated": False}
    killing_systems = lost_hulls = empty
    if available:
        # One attacker identity per pilot/mail; duplicates cannot inflate ranks.
        # Conflicting hull IDs remain unknown rather than choosing a guessed hull.
        attackers = select(KillmailAttacker.killmail_id, KillmailAttacker.character_id,
            case((func.count(distinct(KillmailAttacker.ship_type_id)) == 1, func.max(KillmailAttacker.ship_type_id)),
                 else_=None).label("ship_type_id")).where(KillmailAttacker.character_id.in_(select(cohort.c.eve_id)))\
            .group_by(KillmailAttacker.killmail_id, KillmailAttacker.character_id).subquery()
        kill_rows = select(Killmail.killmail_id, Killmail.solar_system_id.label("system_id"),
            cohort.c.character_id, attackers.c.ship_type_id).join(attackers, attackers.c.killmail_id == Killmail.killmail_id)\
            .join(cohort, cohort.c.eve_id == attackers.c.character_id).where(Killmail.killmail_time >= start,
                Killmail.killmail_time < end, or_(Killmail.victim_character_id.is_(None),
                    Killmail.victim_character_id != attackers.c.character_id)).subquery()
        loss_rows = select(Killmail.killmail_id, cohort.c.character_id, Killmail.victim_ship_type_id.label("ship_type_id"))\
            .join(cohort, cohort.c.eve_id == Killmail.victim_character_id).where(
                Killmail.killmail_time >= start, Killmail.killmail_time < end).subquery()
        kills = db.scalar(select(func.count(distinct(kill_rows.c.killmail_id)))) or 0
        losses = db.scalar(select(func.count(distinct(loss_rows.c.killmail_id)))) or 0
        kill_hulls = select(kill_rows.c.ship_type_id, func.count(distinct(kill_rows.c.killmail_id)).label("kills"))\
            .group_by(kill_rows.c.ship_type_id).subquery()
        pilot_kills = select(kill_rows.c.character_id, func.count(distinct(kill_rows.c.killmail_id)).label("kills"))\
            .group_by(kill_rows.c.character_id).subquery()
        pilot_losses = select(loss_rows.c.character_id, func.count(distinct(loss_rows.c.killmail_id)).label("losses"))\
            .group_by(loss_rows.c.character_id).subquery()
        kill_count = func.count(distinct(kill_rows.c.killmail_id))
        killing_systems = rank(db, select(kill_rows.c.system_id, system_name(kill_rows.c.system_id).label("name"), kill_count.label("kills"))
            .outerjoin(EveSystem, EveSystem.system_id == kill_rows.c.system_id).group_by(kill_rows.c.system_id, EveSystem.name)
            .order_by(kill_count.desc(), system_name(kill_rows.c.system_id), kill_rows.c.system_id), limit)
        loss_count = func.count(distinct(loss_rows.c.killmail_id))
        lost_hulls = rank(db, select(loss_rows.c.ship_type_id, ship_name(loss_rows.c.ship_type_id).label("name"), loss_count.label("losses"))
            .outerjoin(EveType, EveType.type_id == loss_rows.c.ship_type_id).group_by(loss_rows.c.ship_type_id, EveType.name)
            .order_by(loss_count.desc(), ship_name(loss_rows.c.ship_type_id), func.coalesce(loss_rows.c.ship_type_id, -1)), limit)

    name = ship_name(hull_stats.c.ship_type_id)
    ships = select(hull_stats, name.label("name")).outerjoin(EveType, EveType.type_id == hull_stats.c.ship_type_id)
    if available:
        ships = ships.add_columns(func.coalesce(kill_hulls.c.kills, 0).label("kills"))\
            .outerjoin(kill_hulls, kill_hulls.c.ship_type_id == hull_stats.c.ship_type_id)
    else:
        ships = ships.add_columns(literal(None).label("kills"))
    sorting = (hull_stats.c.observed_seconds.desc(), hull_stats.c.visits.desc()) if ship_order == "span" else (
        hull_stats.c.visits.desc(), hull_stats.c.observed_seconds.desc())
    ships = ships.order_by(*sorting, name, hull_stats.c.ship_type_id)
    # Combat ranks must order the full candidate set by kills before top-N;
    # the travel visit/span selector applies only to the most-flown ranking.
    combat_ships = rank(db, ships.where(kill_hulls.c.kills > 0).order_by(None)
        .order_by(kill_hulls.c.kills.desc(), name, hull_stats.c.ship_type_id), limit) if available else empty
    pilots = select(cohort, func.coalesce(pilot_visits.c.visits, 0).label("visits"),
        func.coalesce(pilot_visits.c.systems, 0).label("systems"), func.coalesce(jump_stats.c.jumps, 0).label("jumps"))\
        .outerjoin(pilot_visits, pilot_visits.c.character_id == cohort.c.character_id)\
        .outerjoin(jump_stats, jump_stats.c.character_id == cohort.c.character_id)
    if available:
        pilots = pilots.add_columns(func.coalesce(pilot_kills.c.kills, 0).label("kills"), func.coalesce(pilot_losses.c.losses, 0).label("losses"))\
            .outerjoin(pilot_kills, pilot_kills.c.character_id == cohort.c.character_id)\
            .outerjoin(pilot_losses, pilot_losses.c.character_id == cohort.c.character_id)
    else:
        pilots = pilots.add_columns(literal(None).label("kills"), literal(None).label("losses"))
    pilots = pilots.order_by(func.coalesce(jump_stats.c.jumps, 0).desc(), func.coalesce(pilot_visits.c.visits, 0).desc(),
        cohort.c.name, cohort.c.character_id)
    return {"scope": {"character_id": character.id if character else None, "name": character.name if character else "All my pilots",
                "period": period, "from_at": start.isoformat(), "to_at": end.isoformat(), "ship_order": ship_order},
        "checked_at": at.isoformat(), "combat_available": available,
        "summary": {"pilots": db.scalar(select(func.count()).select_from(cohort)) or 0, "visits": total_visits,
            "systems": total_systems, "jumps": int(total_jumps), "observed_seconds": float(hull_seconds),
            "visits_without_hull": total_visits - known_visits, "kills": kills, "losses": losses},
        "systems": rank(db, systems, limit), "ships": rank(db, ships, limit), "combat_ships": combat_ships,
        "kill_systems": killing_systems, "lost_ships": lost_hulls, "pilots": rank(db, pilots, limit),
        "notices": [
            "Travel rankings aggregate all stored observations in scope, independently of the replay limits. Visits overlap the selected dates.",
            "Observed jumps count consecutive system changes without a recorded gap, at the destination observation time. Fast stops can be missed; these are not verified stargate jumps.",
            "Most-flown ships rank by observed visits or confirmed hull span. Recorded hulls with kills rank by imported kills; lost hulls rank by imported losses. Combat rankings and their bars do not use the visit/span selector. Spans stop at the last confirmed sample, exclude recording gaps, can include docked time, and are not flight/online time. Missing hull history stays unknown.",
            "Combat uses existing imported killmails for these pilots and dates, independently of recorded travel. Kill hulls come from the pilot's attacker entry; lost hulls come from the victim. No historical flight hull is inferred.",
            "Distinct killmails count once per ranking group. Shared kills can appear in multiple pilot/hull groups; a mail can be a kill for one selected pilot and a loss for another. Imports may be incomplete."
            if available else "Combat rankings are unavailable without Killboard, Battle Reports or Intel Reports permission."]}
