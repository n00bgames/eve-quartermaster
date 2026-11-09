"""Public combat report projection; internal sightings are queried separately."""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from sqlalchemy import func, literal, or_, select, union_all
from app.domain.intel import utc
from app.models import EveSystem, EveType, ZkillEnrichment
from app.models.intel import IntelSubject, IntelSighting, LocalScanSighting
from app.models.intel_activity import IntelActivitySample
from app.services.intel_reports import evidence_facts, name_map

def now(): return datetime.now(timezone.utc)
def hour(at): return utc(at).replace(minute=0,second=0,microsecond=0)

def build_public(db, target, start, end):
    """Construct a fresh allowlisted public response, never a stripped staff dossier."""
    end=min(utc(end),now());start=utc(start)
    subject=SimpleNamespace(**target)
    facts,types,limited=evidence_facts(db,subject,start,end)
    systems=Counter();hours=Counter();hulls=Counter();pilots=defaultdict(lambda:{"killmails":set(),"days":set(),"last_seen":None})
    time_series=Counter();pods=Counter();kills=losses=npc_count=unknown_hulls=0
    for fact in facts:
        if fact['npc_only']: npc_count+=1;continue
        at=utc(fact['time']);systems[(fact['system_id'],fact['system_name'])]+=1;hours[at.hour]+=1;time_series[hour(at)]+=1
        victim=fact['victim'];attacker_match=False
        def matches(p):return target['kind']=='system' or p.get(target['kind']+'_id')==target['eve_id']
        attacker_match=any(matches(p) for p in fact['attackers'])
        victim_match=matches(victim)
        kills+=int(attacker_match);losses+=int(victim_match)
        if types.get(victim.get('ship_type_id'),{}).get('group_id')==29:pods[hour(at)]+=1
        elif not types.get(victim.get('ship_type_id'),{}).get('group_id'):unknown_hulls+=1
        appearances=set()
        for participant in [victim,*fact['attackers']]:
            if not matches(participant) or not participant.get('character_id'):continue
            pid=participant['character_id'];entry=pilots[pid]
            entry['killmails'].add(fact['id']);entry['days'].add(at.date());entry['last_seen']=max(entry['last_seen'] or at,at)
            appearances.add((pid,participant.get('ship_type_id')))
        for pid,tid in appearances:
            if tid:hulls[tid]+=1
    names=name_map(db,'character',set(pilots)|{f['victim'].get('character_id') for f in facts if f['victim'].get('character_id')})
    def hull_name(tid):return types.get(tid,{}).get('name') or f'Type {tid}' if tid else 'Unknown hull'
    ranking=[dict(character_id=pid,name=names.get(pid,f'Character {pid}'),appearances=len(row['killmails']),distinct_days=len(row['days']),last_seen=row['last_seen'].isoformat()) for pid,row in pilots.items()]
    ranking.sort(key=lambda p:(-p['appearances'],p['name'].casefold(),p['character_id']))
    top_systems=[dict(system_id=sid,name=name,killmails=count) for (sid,name),count in sorted(systems.items(),key=lambda pair:(-pair[1],pair[0][1].casefold(),pair[0][0]))[:50]]
    top_hulls=[dict(type_id=tid,name=hull_name(tid),appearances=count) for tid,count in sorted(hulls.items(),key=lambda pair:(-pair[1],hull_name(pair[0]).casefold(),pair[0]))[:50]]
    enrichments={}
    ids=[f['id'] for f in facts[:25]]
    if ids:
        enrichments={r.killmail_id:r for r in db.scalars(select(ZkillEnrichment).where(ZkillEnrichment.killmail_id.in_(ids)))}
    recent=[]
    for fact in facts[:25]:
        victim=fact['victim'];pid=victim.get('character_id');meta=enrichments.get(fact['id'])
        recent.append(dict(killmail_id=fact['id'],time=utc(fact['time']).isoformat(),system_id=fact['system_id'],system_name=fact['system_name'],
            victim_id=pid,victim_name=names.get(pid,f'Character {pid}') if pid else 'No character identified',
            hull_id=victim.get('ship_type_id'),hull_name=hull_name(victim.get('ship_type_id')),
            attackers=len(fact['attackers']),npc_only=fact['npc_only'],value=float(meta.estimated_total_value) if meta and meta.estimated_total_value is not None else None,
            url=f"https://zkillboard.com/kill/{fact['id']}/"))
    series=[];cursor=hour(start)
    while cursor<end:
        series.append(dict(hour=cursor.isoformat(),killmails=time_series[cursor],pod_killmails=pods[cursor],jumps=None,ship_kills=None,pod_kills=None,npc_kills=None))
        cursor+=timedelta(hours=1)
    activity={'available':False,'samples':0,'notice':'Hourly ESI totals apply to a system, not to individual pilots or organizations.'}
    if target['kind']=='system':
        samples=db.scalars(select(IntelActivitySample).where(IntelActivitySample.system_id==target['eve_id'],
            IntelActivitySample.observed_at>start,IntelActivitySample.observed_at<=end+timedelta(hours=1)).order_by(IntelActivitySample.observed_at)).all()
        lookup={row['hour']:row for row in series}
        for sample in samples:
            bucket=hour(utc(sample.observed_at)-timedelta(hours=1)).isoformat()
            item=lookup.get(bucket)
            if item:
                for key in ('jumps','ship_kills','pod_kills','npc_kills'):
                    value=getattr(sample,key)
                    if value is not None:item[key]=value
                item['jumps_reported_at' if sample.feed=='jumps' else 'kills_reported_at']=utc(sample.observed_at).isoformat()
        activity=dict(available=any(row['jumps'] is not None or row['ship_kills'] is not None for row in series),samples=len(samples),
            latest_reported_at=max((utc(row.observed_at).isoformat() for row in samples),default=None),
            notice='ESI counts cover the hour ending at the upstream Last-Modified time. Missing feed/history stays unknown; ESI has no historical backfill here. Wormhole totals are not published. Counts are sampled when reports run or activity is refreshed.')
    return dict(schema_version='eqm.intel-report.v1',target=dict(target),window={'from_at':start.isoformat(),'to_at':end.isoformat()},generated_at=now().isoformat(),
        summary=dict(killmails=len(facts),pvp_killmails=len(facts)-npc_count,npc_killmails=npc_count,kills=kills,losses=losses,combat_pilots=len(pilots),systems=len(systems)),
        active_systems=top_systems,common_hulls=top_hulls,combat_pilots=ranking[:50],utc_hours=[dict(hour=h,killmails=hours[h]) for h in range(24)],hourly=series,
        recent_killmails=recent,esi_activity=activity,
        coverage=dict(analysis_limited=limited,killmail_limit=10000,pilot_limit=50,ranking_limit=50,recent_limit=25,unknown_victim_hulls=unknown_hulls,
            notice='Imported public killmails only; source coverage can be incomplete. Sightings are separate from combat appearances. Killmail hours are not online hours, and combat appearances are not complete visit counts. Rankings exclude NPC-only killmails. All limits are display/analysis limits, not claims of complete traffic.'))

def internal_sightings(db,system_id,start,end,viewer_id):
    manual=select(IntelSubject.eve_id.label('character_id'),IntelSighting.observed_at.label('at'),
        IntelSighting.ship_type_id.label('type_id'),IntelSighting.ship_type_name.label('hull'),literal('manual').label('source')).join(IntelSubject,IntelSubject.id==IntelSighting.subject_id).where(
        IntelSubject.kind=='character',IntelSubject.archived.is_(False),IntelSighting.system_id==system_id,IntelSighting.observed_at>=start,IntelSighting.observed_at<end)
    scans=select(LocalScanSighting.character_eve_id,LocalScanSighting.observed_at,literal(None),literal('Unknown hull'),literal('scan')).where(
        LocalScanSighting.system_id==system_id,LocalScanSighting.observed_at>=start,LocalScanSighting.observed_at<end,
        or_(LocalScanSighting.is_private.is_(False),LocalScanSighting.created_by_user_id==viewer_id))
    visible=union_all(manual,scans).subquery();c=visible.c
    day=func.date(func.timezone('UTC',c.at)) if db.get_bind().dialect.name=='postgresql' else func.date(c.at)
    rows=db.execute(select(c.character_id,func.count().label('sightings'),func.count(func.distinct(day)).label('days'),func.max(c.at).label('last_seen'))
        .group_by(c.character_id).order_by(func.count().desc(),c.character_id).limit(50)).all()
    names=name_map(db,'character',{row.character_id for row in rows})
    total=db.scalar(select(func.count()).select_from(visible)) or 0
    pilots=db.scalar(select(func.count(func.distinct(c.character_id)))) or 0
    hulls=db.execute(select(c.type_id,func.max(c.hull).label('name'),func.count().label('sightings')).group_by(c.type_id).order_by(func.count().desc(),c.type_id).limit(50)).all()
    days=max(1,(utc(end)-utc(start)).total_seconds()/86400)
    return dict(total_sightings=total,distinct_pilots=pilots,limit=50,rows=[dict(character_id=row.character_id,name=names.get(row.character_id,f'Character {row.character_id}'),
        sightings=row.sightings,distinct_days=row.days,sightings_per_day=round(row.sightings/days,2),last_seen=utc(row.last_seen).isoformat()) for row in rows],
        hulls=[dict(type_id=row.type_id,name=row.name or 'Unknown hull',sightings=row.sightings) for row in hulls],
        notice='Internal EQM observations, not confirmed arrivals or distinct visits. Repeated scans can observe the same stay. Local Scan hulls are unknown; manual sightings may supply a hull. Public observations plus your own private scans only. Excluded from shared snapshots. Journey data and notes are not read.')
