from __future__ import annotations
from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib,json
from fastapi import HTTPException
from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session
from app.domain.intel import SCHEMA_VERSION, summarize_evidence, utc
from app.models import EveAlliance, EveCharacter, EveConstellation, EveCorporation, EveRegion, EveSystem, EveType, Killmail, KillmailAttacker, KillboardEntityName, User, ZkillEnrichment
from app.models.intel import IntelSubject, IntelCollection, IntelObservation, IntelSourceCache
from app.services.permissions import assigned_base_roles, can_view_section, can_view_at_least

FACT_LIMIT=10000
PARTICIPANT_LIMIT=250000


def require_intel(user: User, db: Session):
    from app.services.recruiting import is_recruiter
    if user.deleted_at or user.role=="applicant" or not can_view_section(user,"intel_reports",db) or not (can_view_at_least(user,"officer",db) or "intel_analyst" in assigned_base_roles(user,db) or is_recruiter(db,user)):
        raise HTTPException(403,"Intel Reports requires section access and an Intel Analyst/Officer role or Recruiter capability")


def subject_or_404(db: Session, subject_id: int):
    row=db.get(IntelSubject,subject_id)
    if row is None: raise HTTPException(404,"Intel subject not found")
    return row


def observe(db: Session, subject: IntelSubject, source: str, payload: dict):
    fingerprint=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    last=db.scalar(select(IntelObservation).where(IntelObservation.subject_id==subject.id,IntelObservation.source==source).order_by(IntelObservation.id.desc()).limit(1))
    if last is None or last.fingerprint!=fingerprint:
        db.add(IntelObservation(subject_id=subject.id,source=source,fingerprint=fingerprint,payload=payload))


def collection_payload(row: IntelCollection):
    return {key:getattr(row,key) for key in ("id","subject_id","status","from_at","to_at","max_pages","stage","page","imported_count","reused_count","failed_count","coverage","errors","retry_count","available_at","created_at","updated_at","finished_at")}


def subject_payload(row: IntelSubject):
    return {"id":row.id,"kind":row.kind,"eve_id":row.eve_id,"name":row.name,"public_data":row.public_data,"updated_at":row.updated_at}


def read_metadata(db: Session, namespace: str, ids: set[int]) -> dict[int,dict]:
    if not ids: return {}
    result={}
    for offset in range(0,len(ids),800):
        batch=list(ids)[offset:offset+800]
        rows=db.scalars(select(IntelSourceCache).where(IntelSourceCache.key.in_([f"{namespace}:{key}" for key in batch]))).all()
        result.update({int(row.key.split(':')[1]):row.payload for row in rows})
    return result


def name_map(db: Session, kind: str, ids: set[int]):
    result={}
    if not ids:return result
    model,column={"character":(EveCharacter,EveCharacter.character_id),"corporation":(EveCorporation,EveCorporation.corporation_id),"alliance":(EveAlliance,EveAlliance.alliance_id)}[kind]
    for offset in range(0,len(ids),800):
        batch=list(ids)[offset:offset+800]
        result.update({row.eve_id:row.name for row in db.scalars(select(KillboardEntityName).where(KillboardEntityName.eve_id.in_(batch),KillboardEntityName.category==kind)).all() if row.name})
        result.update({key:name for key,name in db.execute(select(column,model.name).where(column.in_(batch))).all()})
        result.update({row.eve_id:row.name for row in db.scalars(select(IntelSubject).where(IntelSubject.kind==kind,IntelSubject.eve_id.in_(batch))).all()})
    return result


def evidence_facts(db: Session, subject: IntelSubject, from_at: datetime, to_at: datetime):
    victim_column=getattr(Killmail,f"victim_{subject.kind}_id")
    attacker_column=getattr(KillmailAttacker,f"{subject.kind}_id")
    relevant=or_(victim_column==subject.eve_id,exists().where(KillmailAttacker.killmail_id==Killmail.killmail_id,attacker_column==subject.eve_id))
    query=select(Killmail.killmail_id,Killmail.killmail_time,Killmail.solar_system_id,Killmail.victim_character_id,Killmail.victim_corporation_id,Killmail.victim_alliance_id,Killmail.victim_ship_type_id,ZkillEnrichment.npc,ZkillEnrichment.solo).outerjoin(ZkillEnrichment,ZkillEnrichment.killmail_id==Killmail.killmail_id).where(relevant,Killmail.killmail_time>=from_at,Killmail.killmail_time<to_at).order_by(Killmail.killmail_time.desc(),Killmail.killmail_id.desc()).limit(FACT_LIMIT+1)
    rows=db.execute(query).all(); limited=len(rows)>FACT_LIMIT; rows=rows[:FACT_LIMIT]
    facts={row.killmail_id:{"id":row.killmail_id,"time":utc(row.killmail_time),"system_id":row.solar_system_id,"npc_only":row.npc is True,"solo":row.solo is True,
        "victim":{"character_id":row.victim_character_id,"corporation_id":row.victim_corporation_id,"alliance_id":row.victim_alliance_id,"ship_type_id":row.victim_ship_type_id},"attackers":[]} for row in rows}
    participants=0; missing_kills=set()
    for offset in range(0,len(rows),800):
        batch=[row.killmail_id for row in rows[offset:offset+800]]
        attacker_rows=db.execute(select(KillmailAttacker.killmail_id,KillmailAttacker.character_id,KillmailAttacker.corporation_id,KillmailAttacker.alliance_id,KillmailAttacker.ship_type_id,KillmailAttacker.weapon_type_id).where(KillmailAttacker.killmail_id.in_(batch)).limit(PARTICIPANT_LIMIT-participants+1)).all()
        if len(attacker_rows)>PARTICIPANT_LIMIT-participants:
            # Never analyze a half-loaded battle as a complete participant list.
            limited=True; missing_kills.update(batch); missing_kills.update(row.killmail_id for row in rows[offset+800:]);break
        for row in attacker_rows:
            facts[row.killmail_id]["attackers"].append({"character_id":row.character_id,"corporation_id":row.corporation_id,"alliance_id":row.alliance_id,"ship_type_id":row.ship_type_id,"weapon_type_id":row.weapon_type_id})
        participants+=len(attacker_rows)
    for kid in missing_kills:facts.pop(kid,None)
    type_ids={p.get("ship_type_id") for f in facts.values() for p in [f["victim"],*f["attackers"]]}|{p.get("weapon_type_id") for f in facts.values() for p in f["attackers"]}
    type_ids.discard(None)
    types=read_metadata(db,"type",type_ids)
    for offset in range(0,len(type_ids),800):
        for row in db.scalars(select(EveType).where(EveType.type_id.in_(list(type_ids)[offset:offset+800]))).all():types[row.type_id]={"id":row.type_id,"name":row.name,"group_id":row.group_id}
    system_ids={f["system_id"] for f in facts.values()}; systems=read_metadata(db,"system",system_ids)
    for offset in range(0,len(system_ids),800):
        srows=db.execute(select(EveSystem.system_id,EveSystem.name,EveRegion.region_id,EveRegion.name.label("region_name")).outerjoin(EveConstellation,EveConstellation.constellation_id==EveSystem.constellation_id).outerjoin(EveRegion,EveRegion.region_id==EveConstellation.region_id).where(EveSystem.system_id.in_(list(system_ids)[offset:offset+800]))).all()
        systems.update({row.system_id:{"name":row.name,"region_id":row.region_id,"region_name":row.region_name} for row in srows})
    for fact in facts.values():
        meta=systems.get(fact["system_id"],{})
        fact.update(system_name=meta.get("name") or f"System {fact['system_id']}",region_id=meta.get("region_id"),region_name=meta.get("region_name"))
        if fact["attackers"] and not any(p.get("character_id") for p in fact["attackers"]):fact["npc_only"]=True
        for attacker in fact["attackers"]:
            weapon=types.get(attacker.get("weapon_type_id"),{})
            attacker["weapon_known"]=bool(weapon.get("group_id"))
            attacker["smartbomb"]=weapon.get("group_id")==72
    return list(facts.values()),types,limited


def build_report(db: Session, subject: IntelSubject, from_at: datetime, to_at: datetime):
    facts,types,limited=evidence_facts(db,subject,from_at,to_at)
    summary=summarize_evidence(subject.kind,subject.eve_id,facts,from_at,to_at)
    for row in summary["ships"]:row["name"]=types.get(row["id"],{}).get("name") or f"Type {row['id']}"
    for kind in ("character","corporation","alliance"):
        ids={row["id"] for row in summary["associates"] if row["kind"]==kind}
        names=name_map(db,kind,ids)
        for row in summary["associates"]:
            if row["kind"]==kind:row["name"]=names.get(row["id"],f"{kind.title()} {row['id']}")
    from app.services.intel_sightings import merge
    sightings=merge(db,subject,summary,from_at,to_at)
    region_totals={}
    for row in summary["systems"]:
        if row["region_id"] is None:continue
        entry=region_totals.setdefault(row["region_id"],{"id":row["region_id"],"name":row["region_name"],"kills":0,"losses":0,"sightings":0})
        entry["kills"]+=row["kills"];entry["losses"]+=row["losses"];entry["sightings"]+=row.get("sightings",0)
    summary["regions"]=sorted(region_totals.values(),key=lambda row:-(row["kills"]+row["losses"]))
    latest=db.scalar(select(IntelCollection).where(IntelCollection.subject_id==subject.id).order_by(IntelCollection.created_at.desc()).limit(1))
    collection_rows=db.scalars(select(IntelCollection).where(IntelCollection.subject_id==subject.id).order_by(IntelCollection.created_at.desc()).limit(20)).all()
    coverage={"requested_from":from_at.isoformat(),"requested_to":to_at.isoformat(),"loaded_killmails":len(facts),"analysis_limited":limited,"analysis_limit":FACT_LIMIT,
              "observed_from":min((utc(f["time"]).isoformat() for f in facts),default=None),"observed_to":max((utc(f["time"]).isoformat() for f in facts),default=None),
              "notice":"Recorded public combat only. No record, missing data, and collection gaps do not establish safety, intent, current location, or fleet membership.",
              "collections":[collection_payload(row) for row in collection_rows]}
    history=db.scalars(select(IntelObservation).where(IntelObservation.subject_id==subject.id).order_by(IntelObservation.id.desc()).limit(30)).all()
    total_associates=len(summary["associates"])
    summary["associates"]=[row for kind in ("character","corporation","alliance") for row in [r for r in summary["associates"] if r["kind"]==kind][:50]]
    summary["systems"]=summary["systems"][:100];summary["ships"]=summary["ships"][:100];summary["evidence"]=summary["evidence"][:200]
    subject_info=subject_payload(subject)
    subject_info["public_data"]=deepcopy(subject.public_data)
    profile=(subject_info["public_data"].get("esi",{}) or {}).get("data",{})
    for kind in ("corporation","alliance"):
        ids={profile.get(f"{kind}_id")} | {entry.get(f"{kind}_id") for entry in profile.get("history",[])}
        ids.discard(None);names=name_map(db,kind,ids)
        if profile.get(f"{kind}_id") in names:profile[f"{kind}_name"]=names[profile[f"{kind}_id"]]
        for entry in profile.get("history",[]):
            if entry.get(f"{kind}_id") in names:entry[f"{kind}_name"]=names[entry[f"{kind}_id"]]
    if profile.get("corporation_ids"):
        corporations=name_map(db,"corporation",set(profile["corporation_ids"]))
        profile["corporations"]=[{"id":eid,"name":corporations.get(eid,f"Corporation {eid}")} for eid in profile["corporation_ids"]]
    return {"schema_version":SCHEMA_VERSION,"subject":subject_info,"window":{"from_at":from_at,"to_at":to_at},"summary":summary,"sightings":sightings,"coverage":coverage,"total_associates":total_associates,
            "latest_collection":collection_payload(latest) if latest else None,"observations":[{"source":row.source,"observed_at":row.observed_at,"payload":row.payload} for row in history],
            "definitions":{"associates":"Shared attacker appearances; not proof of same fleet or intent. Engagements use same-system gaps of at most 30 minutes.","smartbomb":"Subject's own attacker weapon is a smartbomb (SDE group 72). Confirmed share uses all observed PvP kills; missing weapon metadata remains unknown. Frequent means at least five confirmed kills and at least 20% of observed kills.","badges":"Upstream badges keep their own rolling windows and are not recalculated for the selected report dates.","evidence":"Up to 200 recent records; ranking evidence links are samples (up to 10 per row)."}}
