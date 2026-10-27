"""Durable, leased public-intel collector. All cursors live in the database."""
from __future__ import annotations
import asyncio
from copy import deepcopy
from collections import Counter
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.domain.intel import utc
from app.models import Killmail, KillmailAttacker, EveType, EveSystem, KillboardEntityName, KillmailDiscovery
from app.models.intel import IntelSubject, IntelCollection, IntelSourceCache
from app.services.intel_sources import PublicSource, IntelSourceError
from app.services.intel_reports import observe
from app.services.killboard_sync import discovery_identity, upsert_killmail, ensure_discovery, upsert_enrichment, parse_killmail_time

LEASE_SECONDS=600
_worker_task=None


def now(): return datetime.now(timezone.utc)


def cache_get(db: Session,key: str):
    row=db.get(IntelSourceCache,key)
    return row.payload if row and utc(row.expires_at)>now() else None


def cache_put(db: Session,key: str,payload: dict,seconds: int):
    row=db.get(IntelSourceCache,key)
    if row is None:db.add(IntelSourceCache(key=key,payload=payload,expires_at=now()+timedelta(seconds=seconds)))
    else:row.payload=payload;row.expires_at=now()+timedelta(seconds=seconds)


def claim(db: Session,job_id: str,token: str) -> bool:
    result=db.execute(update(IntelCollection).where(IntelCollection.id==job_id,IntelCollection.status.in_(["queued","running"]),
        or_(IntelCollection.available_at.is_(None),IntelCollection.available_at<=now()),or_(IntelCollection.lease_until.is_(None),IntelCollection.lease_until<now()))
        .values(status="running",lease_token=token,lease_until=now()+timedelta(seconds=LEASE_SECONDS),updated_at=now()))
    db.commit();return result.rowcount==1


def owned_job(db: Session,job_id: str,token: str):
    # Lock the checkpoint until commit. A recovering worker or cancellation
    # cannot change ownership between this check and its database writes.
    row=db.scalar(select(IntelCollection).where(IntelCollection.id==job_id,
        IntelCollection.status=="running",IntelCollection.lease_token==token).with_for_update())
    if row is None:return None
    row.lease_until=now()+timedelta(seconds=LEASE_SECONDS);row.updated_at=now()
    return row


def note_failure(db: Session,job_id: str,token: str,error: Exception):
    row=owned_job(db,job_id,token)
    if row is None:return
    row.retry_count+=1;row.failed_count+=1
    row.errors=[*row.errors[-9:],{"stage":row.stage,"page":row.page,"message":"Upstream data unavailable or invalid; collection has a gap","at":now().isoformat()}]
    if row.retry_count>=3:
        row.status="partial" if row.imported_count+row.reused_count else "failed";row.finished_at=now()
    else:
        row.status="queued";row.available_at=now()+timedelta(seconds=getattr(error,"retry_after",30)*row.retry_count)
    row.lease_token=None;row.lease_until=None;db.commit()


async def profile_stage(job_id: str,token: str,source,factory):
    with factory() as db:
        row=owned_job(db,job_id,token)
        if row is None:return
        subject=db.get(IntelSubject,row.subject_id);kind,eve_id=subject.kind,subject.eve_id
        stored=deepcopy(subject.public_data);db.commit()
    results={}
    for source_name,ttl,fetch in [("esi",3600 if kind=="character" else 86400,source.profile),("zkill",600,source.stats)]:
        existing=stored.get(source_name,{})
        if existing.get("fetched_at") and utc(existing["fetched_at"])+timedelta(seconds=ttl)>now():continue
        try:
            payload=await fetch(kind,eve_id)
            results[source_name]={"state":"available","fetched_at":now().isoformat(),"data":payload}
        except IntelSourceError as error:
            if "rate limit" in str(error).lower(): raise
            results[source_name]={**existing,"state":"unavailable","last_attempt_at":now().isoformat(),"notice":"Public source unavailable; any retained data may be stale"}
        except Exception:
            results[source_name]={**existing,"state":"unavailable","last_attempt_at":now().isoformat(),"notice":"Public source unavailable; any retained data may be stale"}
    with factory() as db:
        row=owned_job(db,job_id,token)
        if row is None:return
        subject=db.get(IntelSubject,row.subject_id);data=deepcopy(subject.public_data)
        for source_name,result in results.items():
            data[source_name]=result
            if result["state"]=="available":
                stable=deepcopy(result["data"])
                stable.pop("source_errors",None)
                if source_name=="zkill":stable={"badges":stable.get("badges",[])}
                observe(db,subject,source_name,stable)
        subject.public_data=data
        if data.get("esi",{}).get("data",{}).get("name"):subject.name=data["esi"]["data"]["name"]
        row.stage="kills";row.page=1;row.retry_count=0;db.commit()


async def page_stage(job_id: str,token: str,source,factory):
    with factory() as db:
        row=owned_job(db,job_id,token)
        if row is None:return
        subject=db.get(IntelSubject,row.subject_id)
        kind,eve_id,feed,page,cutoff,to_at=subject.kind,subject.eve_id,row.stage,row.page,utc(row.from_at),utc(row.to_at)
        key=f"page:{kind}:{eve_id}:{feed}:{page}"
        cached=cache_get(db,key);db.commit()
    raw_by_id={}
    if cached is not None:entries=cached["entries"]
    else:
        raw=await source.page(kind,eve_id,feed,page)
        entries=[]
        for item in raw:
            kid,kill_hash=discovery_identity(item)
            entries.append({"killmail_id":kid,"killmail_hash":kill_hash,"killmail_time":item.get("killmail_time"), "zkb":{key:value for key,value in (item.get("zkb") or {}).items() if key in {"totalValue","points","solo","npc","awox","labels"}}})
            raw_by_id[kid]=item
        with factory() as db:
            if owned_job(db,job_id,token) is None:return
            cache_put(db,key,{"entries":entries},3600);db.commit()
    oldest=None
    for entry in entries:
        kid,kill_hash=discovery_identity(entry)
        with factory() as db:
            row=owned_job(db,job_id,token)
            if row is None:return
            existing=db.get(Killmail,kid)
            existing_time=utc(existing.killmail_time) if existing else None
            db.commit()
        at=existing_time or (parse_killmail_time(entry["killmail_time"]) if entry.get("killmail_time") else None)
        if at and at<cutoff:
            oldest=min(oldest,at) if oldest else at
            continue
        if at and at>=to_at:continue
        if existing is None:
            canonical=await source.killmail(kid,kill_hash)
            if canonical.get("killmail_id") is not None and int(canonical["killmail_id"])!=kid:raise IntelSourceError("Killmail identity mismatch")
            at=parse_killmail_time(canonical.get("killmail_time"))
        else:canonical=None
        oldest=min(oldest,at) if oldest else at
        if not (cutoff<=at<to_at):continue
        with factory() as db:
            row=owned_job(db,job_id,token)
            if row is None:return
            # Discovery identity deduplicates retries, overlapping subjects, and
            # kills/losses feeds. Existing canonical killmails are never copied.
            discovery_exists=db.scalar(select(KillmailDiscovery.id).where(
                KillmailDiscovery.killmail_id==kid,
                KillmailDiscovery.owner_type==kind,
                KillmailDiscovery.owner_id==eve_id,
                KillmailDiscovery.feed==feed))
            if db.get(Killmail,kid) is None:
                upsert_killmail(db,killmail_id=kid,killmail_hash=kill_hash,esi_payload=canonical,zkill_payload=raw_by_id.get(kid,entry),owner_type=kind,owner_id=eve_id,feed=feed)
                row.imported_count+=1
            else:
                ensure_discovery(db,kid,kind,eve_id,feed)
                enrichment=raw_by_id.get(kid,entry)
                if enrichment.get("zkb"):upsert_enrichment(db,kid,enrichment)
                if not discovery_exists:row.reused_count+=1
            db.commit()
    with factory() as db:
        row=owned_job(db,job_id,token)
        if row is None:return
        coverage=deepcopy(row.coverage)
        state=coverage.setdefault(feed,{"pages":0,"status":"collecting"})
        state["pages"]=page;state["checked_at"]=now().isoformat()
        if oldest:state["oldest_seen"]=min(state.get("oldest_seen",oldest.isoformat()),oldest.isoformat())
        done=not entries or (oldest is not None and oldest<cutoff) or page>=row.max_pages
        if done:
            state["status"]="feed_exhausted" if not entries else "reached_date" if oldest and oldest<cutoff else "page_cap"
            row.stage="losses" if feed=="kills" else "metadata";row.page=1
        else:row.page+=1
        row.coverage=coverage;row.retry_count=0;db.commit()


async def metadata_stage(job_id: str,token: str,source,factory):
    from app.services.intel_reports import evidence_facts
    with factory() as db:
        row=owned_job(db,job_id,token)
        if row is None:return
        subject=db.get(IntelSubject,row.subject_id)
        facts,types,limited=evidence_facts(db,subject,row.from_at,row.to_at)
        weapons={p.get("weapon_type_id") for f in facts for p in f["attackers"] if p.get(f"{subject.kind}_id")==subject.eve_id}
        ships={p.get("ship_type_id") for f in facts for p in [f["victim"],*f["attackers"]] if p.get(f"{subject.kind}_id")==subject.eve_id}
        missing_types=sorted({v for v in weapons|ships if v and not types.get(v,{}).get("group_id")})
        missing_systems=sorted({f["system_id"] for f in facts if f["system_name"].startswith("System ") or f.get("region_id") is None})
        profile=(subject.public_data.get("esi",{}) or {}).get("data",{})
        profile_names={profile.get(key) for key in ("corporation_id","alliance_id","ceo_id","executor_corporation_id") if profile.get(key)}
        for entry in profile.get("history",[]):
            profile_names.update(entry[key] for key in ("corporation_id","alliance_id") if entry.get(key))
        profile_names.update(profile.get("corporation_ids",[]))
        names=set(profile_names);name_counts=Counter()
        for f in facts:
            name_counts.update({p.get(f"{kind}_id") for p in [f["victim"],*f["attackers"]] for kind in ("character","corporation","alliance") if p.get(f"{kind}_id")})
            for p in [f["victim"],*f["attackers"]]:
                for kind in ("character","corporation","alliance"):
                    if p.get(f"{kind}_id"):names.add(p[f"{kind}_id"])
        db.commit()
    metadata_errors=0
    for namespace,ids,fetch in [("type",missing_types[:150],source.type_info),("system",missing_systems[:50],source.system_info)]:
        for eve_id in ids:
            with factory() as db:
                if owned_job(db,job_id,token) is None:return
                cached=cache_get(db,f"{namespace}:{eve_id}");db.commit()
            if cached is not None:continue
            try:payload=await fetch(eve_id)
            except Exception:metadata_errors+=1;continue
            with factory() as db:
                if owned_job(db,job_id,token) is None:return
                cache_put(db,f"{namespace}:{eve_id}",payload,2592000);db.commit()
    # Targeted resolver, never a global scan of all killboard entities.
    names=sorted(profile_names)+sorted(names-profile_names,key=lambda value:(-name_counts[value],value))
    names=names[:900]
    if names:
        try:
            resolved=await source.names(names)
            with factory() as db:
                if owned_job(db,job_id,token) is None:return
                for item in resolved:
                    if item.get("category") not in {"character","corporation","alliance"}:continue
                    existing=db.get(KillboardEntityName,item["id"])
                    if existing is None:
                        existing=KillboardEntityName(eve_id=item["id"],category=item["category"]);db.add(existing)
                    existing.name=item["name"];existing.resolution_status="resolved";existing.last_attempt_at=now();existing.resolved_at=now()
                db.commit()
        except Exception:metadata_errors+=1
    with factory() as db:
        row=owned_job(db,job_id,token)
        if row is None:return
        data=deepcopy(row.coverage)
        data["metadata"]={"errors":metadata_errors,"type_cap_reached":len(missing_types)>150,"system_cap_reached":len(missing_systems)>50,"name_cap_reached":len(names)>=900,"analysis_limited":limited}
        row.coverage=data
        capped=any(data.get(feed,{}).get("status")=="page_cap" for feed in ("kills","losses"))
        row.status="partial" if capped else "completed";row.stage="finished";row.finished_at=now();row.lease_token=None;row.lease_until=None
        db.execute(delete(IntelSourceCache).where(IntelSourceCache.key.like("page:%"),IntelSourceCache.expires_at<now()-timedelta(days=1)))
        db.commit()


async def run_collection(job_id: str,source=None,factory=SessionLocal):
    token=str(uuid4())
    with factory() as db:
        if not claim(db,job_id,token):return
    owns=source is None;source=source or PublicSource()
    try:
        while True:
            with factory() as db:
                row=owned_job(db,job_id,token)
                if row is None:return
                stage=row.stage;db.commit()
            if stage=="profile":await profile_stage(job_id,token,source,factory)
            elif stage in {"kills","losses"}:await page_stage(job_id,token,source,factory)
            elif stage=="metadata":await metadata_stage(job_id,token,source,factory)
            else:raise IntelSourceError("Unknown collection stage")
    except asyncio.CancelledError:
        with factory() as db:
            row=owned_job(db,job_id,token)
            if row:row.status="queued";row.lease_token=None;row.lease_until=None;db.commit()
        raise
    except Exception as error:
        import logging
        logging.getLogger(__name__).warning("Intel collection %s interrupted (%s); checkpoint retained", job_id, type(error).__name__)
        with factory() as db:note_failure(db,job_id,token,error)
    finally:
        if owns:await source.close()


async def worker_loop():
    while True:
        try:
            with SessionLocal() as db:
                job_id=db.scalar(select(IntelCollection.id).where(IntelCollection.status.in_(["queued","running"]),
                    or_(IntelCollection.available_at.is_(None),IntelCollection.available_at<=now()),or_(IntelCollection.lease_until.is_(None),IntelCollection.lease_until<now())).order_by(IntelCollection.created_at).limit(1))
            if job_id:await run_collection(job_id)
            else:await asyncio.sleep(2)
        except asyncio.CancelledError:raise
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Intel collection worker failed; retrying")
            await asyncio.sleep(5)


def start_worker():
    global _worker_task
    if _worker_task is None or _worker_task.done():_worker_task=asyncio.create_task(worker_loop())


async def stop_worker():
    global _worker_task
    if _worker_task:
        _worker_task.cancel()
        try:await _worker_task
        except asyncio.CancelledError:pass
        _worker_task=None
