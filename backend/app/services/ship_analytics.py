"""Private, owner-scoped ship gauges and daily closing inventory history."""
from collections import defaultdict
from datetime import datetime, timezone
from sqlalchemy import and_, false, func, or_, select
from sqlalchemy.orm import selectinload
from app.models import Asset, EveCharacter, EveCorporation, EveGroup, EveType, OwnershipEntity, SnapshotMetric, User
from app.services.ship_hulls import capital_group_ids, hull_predicate

SHIP_METRICS = {'ships.total','ships.types','ships.subcapital_total','ships.subcapital_types','ships.by_type'}
CAPITAL_METRICS = {'ships.total','ships.types'}


def can_view_capitals(db,user):
    from app.services.permissions import role_rank,ROLE_RANK
    return role_rank(user,db)>=ROLE_RANK['fleet_commander']


def eligible_character(db,character):
    from app.services.esi_scope_policy import private_collection_enabled
    user=db.get(User,character.owner_user_id) if character.owner_user_id else None
    return bool(not character.sync_opt_out and user and user.deleted_at is None and private_collection_enabled(db,user))


def capture_owner(db,run,owner,*,retention_mode='full'):
    from app.services.analytics import add_metric,_daily_checkpoint_due,RETENTION_MODE_FULL
    if owner is None:return
    if owner.character_id:
        character=db.get(EveCharacter,owner.character_id)
        if not character or not eligible_character(db,character):return
        kind,oid,name='character',character.id,character.name
    elif owner.corporation_id:
        from app.services.analytics import analytics_corporation_ids
        if owner.corporation_id not in analytics_corporation_ids(db):return
        corp=db.get(EveCorporation,owner.corporation_id)
        kind,oid,name='corporation',corp.id,corp.name
    else:return
    rows=db.execute(select(Asset.type_id,func.sum(Asset.quantity),EveType.group_id).join(EveType,EveType.type_id==Asset.type_id)
        .join(EveGroup,EveGroup.group_id==EveType.group_id).where(Asset.ownership_entity_id==owner.id,hull_predicate())
        .group_by(Asset.type_id,EveType.group_id)).all()
    quantities={int(tid):int(qty) for tid,qty,_ in rows}
    capitals=capital_group_ids(db)
    subcaps={int(tid):int(qty) for tid,qty,gid in rows if gid not in capitals}
    mode=RETENTION_MODE_FULL if _daily_checkpoint_due(db,SnapshotMetric,run,SnapshotMetric.owner_type==kind,
        SnapshotMetric.owner_id==oid,SnapshotMetric.metric_key=='ships.total') else retention_mode
    latest_ids=select(func.max(SnapshotMetric.id)).where(SnapshotMetric.owner_type==kind,SnapshotMetric.owner_id==oid,
        SnapshotMetric.metric_key.in_(SHIP_METRICS)).group_by(SnapshotMetric.series_key)
    prior=list(db.scalars(select(SnapshotMetric).where(SnapshotMetric.id.in_(latest_ids))))
    prior_values={(r.metric_key,(r.dimensions_json or {}).get('type_id')):int(r.metric_value) for r in prior}
    def write(key,value,dimensions=None):
        if mode!=RETENTION_MODE_FULL and prior_values.get((key,(dimensions or {}).get('type_id')))==value:return
        add_metric(db,run,owner_type=kind,owner_id=oid,owner_name=name,metric_key=key,
            metric_value=value,dimensions=dimensions,retention_mode=RETENTION_MODE_FULL)
    write('ships.total',sum(quantities.values()));write('ships.types',len(quantities))
    write('ships.subcapital_total',sum(subcaps.values()));write('ships.subcapital_types',len(subcaps))
    previous={int(r.dimensions_json['type_id']) for r in prior if r.metric_key=='ships.by_type' and r.dimensions_json and r.dimensions_json.get('type_id')}
    # Explicit zero observations prevent removed hull types lingering in history.
    for tid in sorted(previous|quantities.keys()):write('ships.by_type',quantities.get(tid,0),{'type_id':tid})


def capture_global_characters(db,run,*,retention_mode='full'):
    for owner in db.scalars(select(OwnershipEntity).where(OwnershipEntity.character_id.is_not(None))):
        capture_owner(db,run,owner,retention_mode=retention_mode)


def owner_ids(db,user,scope='all',corporation_id=None,alliance_id=None):
    from app.api.industry_reports import can_ships,ship_scope
    from app.services.analytics import analytics_corporation_ids
    from app.services.analytics_scope import resolve_analytics_character_scope
    from app.services.permissions import can_view_section
    if not can_view_section(user,'analytics',db) or not can_ships(db,user):return set(),set()
    # Validate affiliation selectors using the existing Analytics access rules.
    resolve_analytics_character_scope(user,db,scope=scope,corporation_id=corporation_id,alliance_id=alliance_id)
    owners=db.scalars(select(OwnershipEntity).where(OwnershipEntity.id.in_(ship_scope(db,user)['stock']))
        .options(selectinload(OwnershipEntity.character),selectinload(OwnershipEntity.corporation)))
    allowed_corps=analytics_corporation_ids(db)
    chars,corps=set(),set()
    for owner in owners:
        char,corp=owner.character,owner.corporation
        if char and eligible_character(db,char):
            if scope=='mine' and char.owner_user_id!=user.id:continue
            if scope=='corporation' and char.corporation_id!=corporation_id:continue
            if scope=='alliance' and char.alliance_id!=alliance_id:continue
            chars.add(char.id)
        elif corp and corp.id in allowed_corps:
            if scope=='mine':continue
            if scope=='corporation' and corp.id!=corporation_id:continue
            if scope=='alliance' and corp.alliance_id!=alliance_id:continue
            corps.add(corp.id)
    return chars,corps


def metric_visibility(db,user,scope='all',corporation_id=None,alliance_id=None,*,include_subcapital_gauges=True):
    if user is None:return false()
    chars,corps=owner_ids(db,user,scope,corporation_id,alliance_id)
    owners=or_(and_(SnapshotMetric.owner_type=='character',SnapshotMetric.owner_id.in_(chars)),
               and_(SnapshotMetric.owner_type=='corporation',SnapshotMetric.owner_id.in_(corps)))
    # SDE joins fail closed for removed/unknown types below Fleet Commander.
    safe_types=select(EveType.type_id).join(EveGroup,EveGroup.group_id==EveType.group_id).where(
        EveGroup.category_id==6,EveGroup.group_id!=29,EveGroup.group_id.notin_(capital_group_ids(db)))
    if can_view_capitals(db,user):return owners
    safe_type=SnapshotMetric.dimensions_json['type_id'].as_integer().in_(safe_types)
    allowed=and_(SnapshotMetric.metric_key=='ships.by_type',safe_type)
    if include_subcapital_gauges:allowed=or_(allowed,SnapshotMetric.metric_key.in_({'ships.subcapital_total','ships.subcapital_types'}))
    return and_(owners,allowed)


def history(db,user,days,*,scope='all',corporation_id=None,alliance_id=None,type_id=None):
    from app.services.analytics_period import reporting_cutoff
    from app.services.permissions import can_view_section
    from app.api.industry_reports import can_ships
    from fastapi import HTTPException
    if not can_view_section(user,'analytics',db) or not can_ships(db,user):raise HTTPException(403,'Ship Analytics access is required')
    cutoff=reporting_cutoff(days);now=datetime.now(timezone.utc)
    visible=metric_visibility(db,user,scope,corporation_id,alliance_id)
    base=[SnapshotMetric.metric_key.in_(SHIP_METRICS),visible,SnapshotMetric.recorded_at<=now]
    ranked=select(SnapshotMetric.id.label('id'),func.row_number().over(partition_by=SnapshotMetric.series_key,
        order_by=(SnapshotMetric.recorded_at.desc(),SnapshotMetric.id.desc())).label('position')).where(
        *base,SnapshotMetric.recorded_at<cutoff).subquery()
    baseline=select(ranked.c.id).where(ranked.c.position==1)
    rows=list(db.scalars(select(SnapshotMetric).where(*base,or_(SnapshotMetric.recorded_at>=cutoff,
        SnapshotMetric.id.in_(baseline))).order_by(SnapshotMetric.recorded_at,SnapshotMetric.id)))
    quantities={};observed_types=set();baseline_seen=False;daily={}
    def utc(at):return at.replace(tzinfo=at.tzinfo or timezone.utc)
    def values():
        totals=defaultdict(int)
        for (_,_,tid),quantity in quantities.items():totals[tid]+=quantity
        return dict(totals)
    for row in rows:
        at=utc(row.recorded_at)
        if at>=cutoff and baseline_seen and not daily:
            daily[cutoff.date().isoformat()]=(cutoff.isoformat(),values())
        if row.metric_key=='ships.by_type' and row.dimensions_json:
            tid=int(row.dimensions_json['type_id']);observed_types.add(tid)
            quantities[(row.owner_type,row.owner_id,tid)]=max(0,int(row.metric_value))
        if at<cutoff:baseline_seen=True
        else:daily[at.date().isoformat()]=(at.isoformat(),values())
    if baseline_seen and not daily:daily[cutoff.date().isoformat()]=(cutoff.isoformat(),values())
    current=values()
    items={item.type_id:item for item in db.scalars(select(EveType).where(EveType.type_id.in_(observed_types)).options(selectinload(EveType.group)))}
    by_type=[{'type_id':tid,'item':items[tid].name if tid in items else f'Type {tid}',
        'ship_class':items[tid].group.name if tid in items and items[tid].group else 'Unknown',
        'quantity':current.get(tid,0)} for tid in observed_types]
    by_type.sort(key=lambda r:(-r['quantity'],r['item'].casefold()))
    points=[{'date':at,'value':sum(v.values()),'ship_types':sum(q>0 for q in v.values())} for at,v in daily.values()]
    selected=[{'date':at,'value':v.get(type_id,0)} for at,v in daily.values()] if type_id in observed_types else []
    return {'days':days,'scope':scope,'capitals_visible':can_view_capitals(db,user),
        'total_ships':sum(current.values()),'ship_types':sum(q>0 for q in current.values()),'by_type':by_type,
        'series':points,'selected_type_id':type_id if type_id in observed_types else None,'type_series':selected,
        'observed_at':utc(rows[-1].recorded_at).isoformat() if rows else None,
        'notice':'Daily closing synchronized inventory. Capsules excluded. Report class filters do not change Analytics history.'}
