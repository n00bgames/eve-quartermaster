"""Bounded public affiliation metadata; never enrolls outside pilots or uses tokens."""
import asyncio
from datetime import datetime,timedelta,timezone
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.domain.intel import utc
from app.models import EveCorporation,EveAlliance
from app.models.intel import IntelSubject,IntelSourceCache
from app.services.intel_sources import PublicSource

def identities(subject):
    profile=((subject.public_data or {}).get('esi') or {}).get('data') or {}
    if subject.kind!='character':return []
    return [(kind,int(profile[f'{kind}_id'])) for kind in ('corporation','alliance')
        if isinstance(profile.get(f'{kind}_id'),int) and profile[f'{kind}_id']>0]

def key(kind,eid):return f'organization:{kind}:{eid}'

def read(db,subject):
    profile=((subject.public_data or {}).get('esi') or {}).get('data') or {}
    result=[]
    for kind,eid in identities(subject):
        model,column=(EveCorporation,EveCorporation.corporation_id) if kind=='corporation' else (EveAlliance,EveAlliance.alliance_id)
        local=db.scalar(select(model).where(column==eid))
        cache=db.get(IntelSourceCache,key(kind,eid));metadata=cache.payload if cache else {}
        result.append({'kind':kind,'eve_id':eid,'name':metadata.get('name') or (local.name if local else None) or profile.get(f'{kind}_name') or f'{kind.title()} {eid}',
            'ticker':metadata.get('ticker') or (local.ticker if local else None) or profile.get(f'{kind}_ticker'),
            'metadata_available':bool(metadata.get('name') and metadata.get('ticker')),
            'stale':bool(cache and (cache.payload.get('unavailable') or utc(cache.expires_at)<=datetime.now(timezone.utc)))})
    return result

async def load(db,subject):
    sid=subject.id;now=datetime.now(timezone.utc);pending=[]
    for kind,eid in identities(subject):
        cached=db.get(IntelSourceCache,key(kind,eid))
        if cached is None or utc(cached.expires_at)<=now:pending.append((kind,eid))
    if not pending:return read(db,subject)
    # Keep network waits out of the database connection pool.
    db.rollback()
    source=PublicSource()
    try:
        results=await asyncio.gather(*(asyncio.wait_for(source.organization(kind,eid),15) for kind,eid in pending),return_exceptions=True)
    finally:await source.close()
    for (kind,eid),value in zip(pending,results):
        cache=db.get(IntelSourceCache,key(kind,eid))
        valid=isinstance(value,dict) and bool(value.get('name'))
        if not valid and cache is not None and utc(cache.expires_at)>now:continue
        data={'name':value['name'],'ticker':value.get('ticker')} if valid else {**(cache.payload if cache else {}),'unavailable':True}
        expires=now+timedelta(seconds=86400 if valid else 60)
        try:
            with db.begin_nested():
                if cache is None:
                    cache=IntelSourceCache(key=key(kind,eid),payload=data,expires_at=expires);db.add(cache)
                else:cache.payload=data;cache.expires_at=expires
                db.flush()
        except IntegrityError:
            # Another report may have filled the same organization cache meanwhile.
            cache=db.get(IntelSourceCache,key(kind,eid))
            if cache is None:raise
            if valid:cache.payload=data;cache.expires_at=expires
    db.commit()
    current=db.get(IntelSubject,sid)
    return read(db,current)
