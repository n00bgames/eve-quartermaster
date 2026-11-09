"""Bounded explicit public refreshes, with shared cache leases and ESI provenance."""
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select
from app.domain.intel import utc
from app.models import Killmail, KillboardEntityName
from app.models.intel import IntelSourceCache
from app.models.intel_activity import IntelActivitySample
from app.services.character_notes import conflict_insert
from app.services.intel_sources import PublicSource, ENTITY_MODIFIER
from app.services.killboard_sync import upsert_killmail, ensure_discovery, upsert_enrichment

def now():return datetime.now(timezone.utc)
def key(kind,eid):return f'intel-report-refresh:{kind}:{eid}'
def status(db,kind,eid):
    row=db.get(IntelSourceCache,key(kind,eid))
    data=row.payload if row else {}
    return {k:data.get(k) for k in ('status','finished_at','imported','reused','failed','notice')} | {'next_refresh_at':utc(row.expires_at).isoformat() if row else None}

def claim(db,kind,eid):
    at=now();token=str(uuid4())
    statement=conflict_insert(db,IntelSourceCache).values(key=key(kind,eid),payload={'status':'running','lease':token},expires_at=at+timedelta(minutes=2))
    claimed=db.scalar(statement.on_conflict_do_update(index_elements=['key'],set_={'payload':statement.excluded.payload,'expires_at':statement.excluded.expires_at},where=IntelSourceCache.expires_at<=at).returning(IntelSourceCache.key))
    db.commit()
    return token if claimed else None

def matches(kind,eid,payload):
    if kind=='system':return payload.get('solar_system_id')==eid
    field=kind+'_id'
    return payload.get('victim',{}).get(field)==eid or any(p.get(field)==eid for p in payload.get('attackers',[]) if isinstance(p,dict))

async def fetch(source,kind,eid,known):
    modifier='solarSystemID' if kind=='system' else ENTITY_MODIFIER[kind]
    rows=await asyncio.wait_for(source.zget(f'{modifier}/{eid}/page/1'),timeout=15)
    if not isinstance(rows,list) or len(rows)>200:raise ValueError('Invalid public killmail page')
    refs={}
    for row in rows:
        if not isinstance(row,dict):continue
        kid=row.get('killmail_id');hash_value=(row.get('zkb') or {}).get('hash')
        if type(kid) is int and kid>0 and isinstance(hash_value,str) and 1<=len(hash_value)<=128:refs.setdefault(kid,row)
    chosen=list(refs.items())[:25]
    gate=asyncio.Semaphore(4)
    async def one(kid,row):
        if kid in known:return kid,row,None,None
        async with gate:
            try:
                payload=await source.killmail(kid,row['zkb']['hash'])
                if not isinstance(payload,dict) or payload.get('killmail_id')!=kid or not matches(kind,eid,payload):raise ValueError('Source scope mismatch')
                return kid,row,payload,None
            except Exception:return kid,row,None,'Public ESI killmail unavailable or outside target scope'
    tasks=[asyncio.create_task(one(kid,row)) for kid,row in chosen]
    try:
        done,pending=await asyncio.wait(tasks,timeout=30) if tasks else (set(),set())
        for task in pending:task.cancel()
        await asyncio.gather(*pending,return_exceptions=True)
        results=[task.result() if task in done else (kid,row,None,'Public ESI killmail timeout') for task,(kid,row) in zip(tasks,chosen)]
    finally:
        for task in tasks:
            if not task.done():task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
    # Metadata requests are bounded and public; no tracked EVE enrollment.
    names=set();types=set()
    for _,_,payload,_ in results:
        if not payload:continue
        for p in [payload.get('victim',{}),*payload.get('attackers',[])]:
            for kind_name in ('character','corporation','alliance'):
                if type(p.get(kind_name+'_id')) is int:names.add(p[kind_name+'_id'])
            if type(p.get('ship_type_id')) is int:types.add(p['ship_type_id'])
    resolved=[];metadata=[]
    if names:
        try:
            value=await asyncio.wait_for(source.names(sorted(names)[:200]),timeout=3)
            resolved=value if isinstance(value,list) else []
        except Exception:pass
    async def type_meta(tid):
        async with gate:
            try:
                value=await asyncio.wait_for(source.type_info(tid),timeout=1)
                return {key:value[key] for key in ('id','name','group_id') if key in value} if isinstance(value,dict) and value.get('id')==tid else None
            except Exception:return None
    try:metadata=[p for p in await asyncio.wait_for(asyncio.gather(*(type_meta(tid) for tid in sorted(types)[:25])),timeout=5) if p]
    except asyncio.TimeoutError:metadata=[]
    return results,resolved,metadata,len(refs)

def persist(db,kind,eid,token,result,error=None):
    row=db.scalar(select(IntelSourceCache).where(IntelSourceCache.key==key(kind,eid)).with_for_update().execution_options(populate_existing=True))
    if row is None or row.payload.get('lease')!=token or utc(row.expires_at)<=now():raise HTTPException(409,'Refresh lease expired; reload the report')
    imported=reused=failed=0;at=now()
    if result:
        results,names,types,discovered=result
        for kid,reference,payload,issue in results:
            if issue:failed+=1;continue
            try:
                with db.begin_nested():
                    existing=db.get(Killmail,kid)
                    if existing:
                        if not matches(kind,eid,existing.canonical_esi_payload):raise ValueError('Cached killmail scope mismatch')
                        ensure_discovery(db,kid,'system' if kind=='system' else kind,eid,'intel_report')
                        upsert_enrichment(db,kid,reference['zkb'],at)
                    else:
                        upsert_killmail(db,killmail_id=kid,killmail_hash=reference['zkb']['hash'],esi_payload=payload,
                            zkill_payload=reference['zkb'],owner_type='system' if kind=='system' else kind,owner_id=eid,feed='intel_report')
                if existing:reused+=1
                else:imported+=1
            except Exception:failed+=1
        for item in names:
            if not isinstance(item,dict) or item.get('category') not in ('character','corporation','alliance') or type(item.get('id')) is not int or item['id']<=0 or not isinstance(item.get('name'),str) or not 1<=len(item['name'])<=255:continue
            value=conflict_insert(db,KillboardEntityName).values(eve_id=item['id'],category=item['category'],name=item['name'],last_attempt_at=at,resolved_at=at)
            db.execute(value.on_conflict_do_update(index_elements=['eve_id'],set_={'name':value.excluded.name,'category':value.excluded.category,'last_attempt_at':at,'resolved_at':at,'resolution_status':'resolved'}))
        for item in types:
            if type(item.get('id')) is not int:continue
            cache_key=f"type:{item['id']}";cached=db.get(IntelSourceCache,cache_key)
            if cached:cached.payload=item;cached.expires_at=at+timedelta(days=30)
            else:db.add(IntelSourceCache(key=cache_key,payload=item,expires_at=at+timedelta(days=30)))
    row.payload=dict(status='error' if error else 'partial' if failed else 'completed',finished_at=at.isoformat(),imported=imported,reused=reused,failed=failed,
        notice='Public source refresh failed; retained evidence was kept.' if error else 'Newest page sampled: at most 25 killmails per pull. zKill can omit recent/missing records; a page is not complete system or entity history.')
    row.expires_at=at+timedelta(seconds=max(60,getattr(error,'retry_after',60)) if error else 3600)
    db.commit();return status(db,kind,eid)

def save_activity(db,eid,snapshot):
    """Only successful supported feeds with upstream timestamps become samples."""
    if not 30000000<=eid<31000000:return {'saved':0,'notice':'ESI activity totals are not published for this space; unknown, not zero.'}
    written=0;notices=[];at=now()
    for feed,fields in [('jumps',{'ship_jumps':'jumps'}),('kills',{'ship_kills':'ship_kills','pod_kills':'pod_kills','npc_kills':'npc_kills'})]:
        part=snapshot.get(feed,{})
        try:observed=utc(part['observed_at'])
        except (ValueError,TypeError,KeyError,AttributeError):notices.append(feed+' timestamp unavailable');continue
        if part.get('stale') or not isinstance(part.get('data'),dict) or observed>at+timedelta(minutes=5):notices.append(feed+' feed stale/unavailable');continue
        values=part['data'].get(str(eid),{})
        counts={dest:values.get(src,0) for src,dest in fields.items()}
        if any(type(value) is not int or value<0 for value in counts.values()):notices.append(feed+' invalid counts');continue
        statement=conflict_insert(db,IntelActivitySample).values(system_id=eid,feed=feed,observed_at=observed,fetched_at=at,**counts)
        db.execute(statement.on_conflict_do_update(index_elements=['system_id','feed','observed_at'],set_={**counts,'fetched_at':at}))
        written+=1
    db.commit()
    return {'saved':written,'notice':'; '.join(notices) or 'Latest available upstream reported-hour totals saved. Historical gaps cannot be backfilled through ESI.'}
