"""SQL aggregates over explicit owned cohorts, with filtering before aggregation.

Public callers use the same queries with a strict ship classification predicate.
The public projection is deliberately independent of private response shapes.
"""
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import String, and_, case, cast, distinct, exists, func, literal, select, union

from app.models import EveCharacter, EveGroup, EveSystem, EveType, Killmail, KillmailAttacker
from app.models.journey import JourneyShipSegment, JourneyTracker, JourneyVisit
from app.services import journey
from app.services.journey_analytics import combat_allowed, duration
from app.services.ship_hulls import capital_group_ids


def cohort(db, user, spec):
    query = select(EveCharacter.id.label('id'), EveCharacter.character_id.label('eve_id'), EveCharacter.name).where(
        EveCharacter.owner_user_id == user.id)
    ids = set(spec.get('character_ids') or [])
    if spec['cohort'] == 'selected':
        if not ids:
            raise HTTPException(422, 'Select at least one owned pilot')
        query = query.where(EveCharacter.id.in_(ids))
    if spec['cohort'] == 'fleet':
        query = query.where(exists(select(JourneyTracker.id).where(JourneyTracker.character_id == EveCharacter.id,
            JourneyTracker.user_id == user.id, JourneyTracker.enabled.is_(True))))
        if ids:
            query = query.where(EveCharacter.id.in_(ids))
    rows = [dict(r) for r in db.execute(query.order_by(EveCharacter.name, EveCharacter.id)).mappings()]
    if ids and {r['id'] for r in rows} != ids:
        raise HTTPException(404, 'One or more selected pilots are unavailable in this scope')
    return rows


def bounds(spec):
    if spec['period'] == 'all':
        return datetime(2003, 1, 1, tzinfo=timezone.utc), journey.now()
    return journey.window(spec.get('from_at'), spec.get('to_at'))


def allowed_hull(db, column, spec, public):
    predicates = []
    if spec.get('ship_type_id'):
        predicates.append(column == spec['ship_type_id'])
    excluded = set(spec.get('exclude_groups') or [])
    if spec.get('exclude_capitals'):
        excluded |= capital_group_ids(db)
    if spec.get('exclude_supercapitals'):
        excluded |= {30, 659}
        excluded |= set(db.scalars(select(EveGroup.group_id).where(EveGroup.category_id == 6,
            func.lower(EveGroup.name).in_(['titan', 'supercarrier']))))
    if spec.get('exclude_types'):
        predicates.append(column.notin_(spec['exclude_types']))
    if public or excluded:
        # Missing SDE classification never bypasses public exclusions.
        classified = select(EveType.type_id).join(EveGroup, EveGroup.group_id == EveType.group_id).where(
            EveType.type_id == column, EveGroup.category_id == 6)
        if excluded:
            classified = classified.where(EveGroup.group_id.notin_(excluded))
        predicates.append(exists(classified))
    return and_(*predicates) if predicates else literal(True)


def sources(db, user, spec, public=False):
    people = cohort(db, user, spec)
    start, end = bounds(spec)
    ids, eve_ids = [p['id'] for p in people], [p['eve_id'] for p in people]
    visits = select(JourneyVisit.id.label('visit_id'), JourneyVisit.system_id,
        JourneyTracker.character_id.label('pilot_id'), JourneyVisit.first_seen_at, JourneyVisit.last_seen_at).join(
        JourneyTracker, JourneyTracker.id == JourneyVisit.tracker_id).where(JourneyTracker.user_id == user.id,
        JourneyTracker.character_id.in_(ids), JourneyVisit.first_seen_at < end, JourneyVisit.last_seen_at >= start)
    if spec.get('system_id'):
        visits = visits.where(JourneyVisit.system_id == spec['system_id'])
    visits = visits.subquery('insight_visits')
    first = case((JourneyShipSegment.first_seen_at < start, start), else_=JourneyShipSegment.first_seen_at)
    last = case((JourneyShipSegment.last_seen_at > end, end), else_=JourneyShipSegment.last_seen_at)
    hull = select(JourneyShipSegment.id.label('segment_id'), visits.c.visit_id, visits.c.pilot_id,
        visits.c.system_id, JourneyShipSegment.ship_type_id.label('hull_id'), first.label('first_at'), last.label('last_at'),
        duration(JourneyShipSegment.first_seen_at, JourneyShipSegment.last_seen_at, start, end).label('seconds')).join(
        visits, visits.c.visit_id == JourneyShipSegment.visit_id).where(JourneyShipSegment.first_seen_at < end,
        JourneyShipSegment.last_seen_at >= start, allowed_hull(db, JourneyShipSegment.ship_type_id, spec, public)).subquery('insight_hulls')
    filtered = public or bool(spec.get('ship_type_id') or spec.get('exclude_types') or spec.get('exclude_groups') or
        spec.get('exclude_capitals') or spec.get('exclude_supercapitals'))
    eligible = select(visits)
    if filtered:
        eligible = eligible.where(visits.c.visit_id.in_(select(hull.c.visit_id)))
    visits = eligible.subquery('eligible_visits')
    available = combat_allowed(db, user)
    kills = losses = None
    if available:
        attackers = select(KillmailAttacker.killmail_id, KillmailAttacker.character_id,
            case((and_(func.count(KillmailAttacker.ship_type_id) == func.count(),
                func.count(distinct(KillmailAttacker.ship_type_id)) == 1), func.max(KillmailAttacker.ship_type_id)),
                else_=None).label('hull_id')).where(KillmailAttacker.character_id.in_(eve_ids)).group_by(
                KillmailAttacker.killmail_id, KillmailAttacker.character_id).subquery('insight_attackers')
        pilots = select(EveCharacter.id.label('pilot_id'), EveCharacter.character_id).where(EveCharacter.id.in_(ids)).subquery()
        query = select(Killmail.killmail_id.label('mail_id'), Killmail.solar_system_id.label('system_id'),
            pilots.c.pilot_id, attackers.c.hull_id, Killmail.killmail_time.label('time')).join(
            attackers, attackers.c.killmail_id == Killmail.killmail_id).join(pilots, pilots.c.character_id == attackers.c.character_id).where(
            Killmail.killmail_time >= start, Killmail.killmail_time < end,
            (Killmail.victim_character_id.is_(None)) | (Killmail.victim_character_id != attackers.c.character_id),
            allowed_hull(db, attackers.c.hull_id, spec, public))
        loss = select(Killmail.killmail_id.label('mail_id'), Killmail.solar_system_id.label('system_id'),
            pilots.c.pilot_id, Killmail.victim_ship_type_id.label('hull_id'), Killmail.killmail_time.label('time')).join(
            pilots, pilots.c.character_id == Killmail.victim_character_id).where(Killmail.killmail_time >= start,
            Killmail.killmail_time < end, allowed_hull(db, Killmail.victim_ship_type_id, spec, public))
        if spec.get('system_id'):
            query = query.where(Killmail.solar_system_id == spec['system_id'])
            loss = loss.where(Killmail.solar_system_id == spec['system_id'])
        kills, losses = query.subquery('insight_kills'), loss.subquery('insight_losses')
    return dict(people=people, start=start, end=end, visits=visits, hull=hull, kills=kills, losses=losses, available=available)


def ranking(db, src, dimension, metric, limit, offset):
    h, v, k, l = (src[key] for key in ('hull', 'visits', 'kills', 'losses'))
    key = {'hulls':'hull_id', 'systems':'system_id', 'pilots':'pilot_id'}[dimension]
    # Travel and combat are aggregated independently before joining; shared
    # killmails count once per dimension, never once per attacker row.
    travel = select(h.c[key].label('id'), func.count(distinct(h.c.visit_id)).label('visits'),
        func.count().label('segments'), func.count(distinct(h.c.system_id)).label('systems'),
        func.sum(h.c.seconds).label('seconds'), func.min(h.c.first_at).label('first_at'),
        func.max(h.c.last_at).label('last_at')).group_by(h.c[key]).subquery()
    sets = [select(travel.c.id)]
    combat = []
    for rows, label in ((k, 'kills'), (l, 'losses')):
        if rows is not None:
            group = select(rows.c[key].label('id'), func.count(distinct(rows.c.mail_id)).label(label)).group_by(rows.c[key]).subquery()
            sets.append(select(group.c.id)); combat.append((group, label))
    # For unfiltered private system/pilot ranks, preserve visits without hulls.
    if dimension != 'hulls':
        visit_groups = select(v.c[key].label('id'), func.count(distinct(v.c.visit_id)).label('visits')).group_by(v.c[key]).subquery()
        sets.append(select(visit_groups.c.id))
    universe = union(*sets).subquery()
    total = db.scalar(select(func.count()).select_from(universe)) or 0
    label_table, label_key = (EveType, EveType.type_id) if dimension == 'hulls' else (
        (EveSystem, EveSystem.system_id) if dimension == 'systems' else (EveCharacter, EveCharacter.id))
    prefix = {'hulls':'Type ', 'systems':'System ', 'pilots':'Pilot '}[dimension]
    name = func.coalesce(label_table.name, case((universe.c.id.is_(None), 'Unknown hull'),
        else_=literal(prefix) + cast(universe.c.id, String)))
    query = select(universe.c.id, name.label('name'), func.coalesce(travel.c.visits, 0).label('visits'),
        func.coalesce(travel.c.segments, 0).label('segments'), func.coalesce(travel.c.systems, 0).label('systems'),
        func.coalesce(travel.c.seconds, 0).label('seconds'), travel.c.first_at, travel.c.last_at).select_from(universe).outerjoin(
        travel, travel.c.id.is_not_distinct_from(universe.c.id)).outerjoin(label_table, label_key == universe.c.id)
    if dimension != 'hulls':
        query = query.add_columns(func.coalesce(visit_groups.c.visits, 0).label('observed_visits')).outerjoin(visit_groups,
            visit_groups.c.id.is_not_distinct_from(universe.c.id))
    for group, label in combat:
        query = query.add_columns(func.coalesce(group.c[label], 0).label(label)).outerjoin(group,
            group.c.id.is_not_distinct_from(universe.c.id))
    query = query.subquery()
    column = query.c.observed_visits if metric == 'visits' and dimension != 'hulls' else (
        query.c[metric] if metric in query.c else query.c.visits)
    result = [dict(r) for r in db.execute(select(query).order_by(column.desc(), query.c.name, query.c.id).offset(offset).limit(limit)).mappings()]
    for row in result:
        row['seconds'] = float(row['seconds'])
        if dimension != 'hulls':row['visits'] = row.pop('observed_visits')
        for field in ('kills', 'losses'):
            if field not in row:row[field] = None
    return {'rows':result, 'total':total, 'offset':offset, 'limit':limit, 'truncated':offset + len(result) < total}


def build(db, user, spec, public=False):
    src = sources(db, user, spec, public)
    if spec['metric'] in ('kills', 'losses') and not src['available']:
        raise HTTPException(403, 'Combat permission required for this ranking; choose observed visits or confirmed span')
    v, h, k, l = (src[key] for key in ('visits', 'hull', 'kills', 'losses'))
    counts = db.execute(select(func.count(distinct(v.c.visit_id)), func.count(distinct(v.c.system_id)))).one()
    seconds, segments, first, last = db.execute(select(func.coalesce(func.sum(h.c.seconds), 0), func.count(),
        func.min(h.c.first_at), func.max(h.c.last_at))).one()
    summary = dict(visits=counts[0], systems=counts[1], segments=segments, seconds=float(seconds),
        kills=db.scalar(select(func.count(distinct(k.c.mail_id)))) if k is not None else None,
        losses=db.scalar(select(func.count(distinct(l.c.mail_id)))) if l is not None else None)
    result = dict(scope=dict(cohort=spec['cohort'], from_at=src['start'], to_at=src['end'],
        ship_type_id=spec.get('ship_type_id'), system_id=spec.get('system_id'), metric=spec['metric']),
        checked_at=journey.now(), summary=summary, combat_available=src['available'],
        hulls=ranking(db, src, 'hulls', spec['metric'], spec['limit'], spec['offset']),
        systems=ranking(db, src, 'systems', spec['metric'], spec['limit'], spec['offset']),
        pilots=ranking(db, src, 'pilots', spec['metric'], spec['limit'], spec['offset']),
        notices=['Counts use all stored rows in the selected scope, independently of replay and ranking limits.',
            'Confirmed hull span sums pilot observation spans; simultaneous alts overlap. It is not elapsed fleet time or flight time.',
            'Visits can include multiple hulls. Group visits and shared kill participation do not sum to distinct fleet totals.',
            'Combat hulls come from imported attacker/victim records and include hulls with no recorded travel. Unknown or conflicting hulls remain unknown.',
            'Observation gaps are not bridged; incomplete imports and fast missed stops remain possible.',
            'Ranking pages show a bounded selection; summary totals include every qualifying group. Public downloads contain only the saved visible rankings and complete summary.'])
    if not public:
        result.update(cohort=src['people'], first_at=first, last_at=last)
        result['scope'].update({key:spec.get(key) for key in ('period', 'character_ids', 'exclude_types', 'exclude_groups',
            'exclude_capitals', 'exclude_supercapitals')})
        return result
    # Explicit public allowlist: no private IDs, precise observation timestamps,
    # killmail links/rows, filter values or excluded/unknown record counts.
    fields = ('name', 'visits', 'segments', 'systems', 'seconds', 'kills', 'losses')
    for kind in ('hulls', 'systems', 'pilots'):
        if kind == 'systems' and not spec['show_systems'] or kind == 'pilots' and not spec['show_pilots']:
            result.pop(kind)
            continue
        result[kind]['rows'] = [{key:row[key] for key in fields} for row in result[kind]['rows']]
    result['scope'] = {key:result['scope'][key] for key in ('from_at', 'to_at', 'metric')}
    result['notices'].append('Snapshot of the explicitly shared, classified hull scope. No raw journeys, live positions or external killmail links are published.')
    return result


def options(db, user, search=''):
    from app.services.ship_hulls import ship_classes
    ships = select(EveType.type_id, EveType.name).join(EveGroup).where(EveGroup.category_id == 6)
    if search:ships = ships.where(EveType.name.ilike('%' + search.replace('%', r'\%').replace('_', r'\_') + '%', escape='\\'))
    return dict(groups=ship_classes(db), types=[dict(r) for r in db.execute(ships.order_by(EveType.name).limit(50)).mappings()],
        pilots=cohort(db, user, {'cohort':'account'}),
        enabled_ids=list(db.scalars(select(JourneyTracker.character_id).where(JourneyTracker.user_id == user.id, JourneyTracker.enabled.is_(True)))))
