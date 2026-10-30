from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.auth import get_current_user
from app.db.session import get_db
from app.domain.intel import parse_entities, utc
from app.models import User, EveCharacter, EveCorporation, EveAlliance, KillboardEntityName
from app.models.intel import IntelSubject, IntelCollection, IntelNote
from app.schemas.intel import ResolveInput, SubjectInput, CollectInput, NoteInput, NoteEditInput, NoteDeleteInput, SightingInput, AuthorizedRefreshInput
from app.services.intel_sources import PublicSource
from app.services.intel_reports import require_intel, subject_or_404, subject_payload, collection_payload, observe, build_report, name_map
from app.services.intel_authorized import private_enrichment, refresh_authorized
from app.services.audit import record_audit_event
from app.services import intel_sightings


def access(response: Response,user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    require_intel(user,db);response.headers["Cache-Control"]="private, no-store"
    return user

router=APIRouter(prefix="/intel",tags=["intel"],dependencies=[Depends(access)])


def source_factory(): return PublicSource()


@router.post("/resolve")
async def resolve(payload: ResolveInput,user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    try:inputs=parse_entities(payload.text)
    except ValueError as error:raise HTTPException(422,str(error)) from error
    names=[row["input"] for row in inputs if "eve_id" not in row]
    candidates={};warnings=[]
    if names:
        lowered=[name.casefold() for name in names]
        for kind,model,idcolumn in [("character",EveCharacter,EveCharacter.character_id),("corporation",EveCorporation,EveCorporation.corporation_id),("alliance",EveAlliance,EveAlliance.alliance_id)]:
            for eid,name in db.execute(select(idcolumn,model.name).where(func.lower(model.name).in_(lowered))).all():
                candidates[(kind,eid)]={"kind":kind,"eve_id":eid,"name":name}
        for row in db.scalars(select(IntelSubject).where(func.lower(IntelSubject.name).in_(lowered))).all():candidates[(row.kind,row.eve_id)]={"kind":row.kind,"eve_id":row.eve_id,"name":row.name}
        source=source_factory()
        try:
            found=await source.resolve(names)
            for kind in ("character","corporation","alliance"):
                for row in found.get(kind+"s",[]):
                    if row["name"].casefold() in lowered:candidates[(kind,int(row["id"]))]={"kind":kind,"eve_id":int(row["id"]),"name":row["name"]}
        except Exception:warnings.append("Public name lookup is unavailable; only locally cached exact matches are shown")
        finally:await source.close()
    result=[]
    for row in inputs:
        matches=[value for value in candidates.values() if value["name"].casefold()==row["input"].casefold()] if "eve_id" not in row else [{"kind":row["kind"],"eve_id":row["eve_id"],"name":f"{row['kind'].title()} {row['eve_id']}"}]
        result.append({"input":row["input"],"state":"resolved" if len(matches)==1 else "ambiguous" if matches else "unresolved","candidates":matches})
    return {"rows":result,"warnings":warnings}


@router.get("/subjects")
def subjects(q: str=Query(default="",max_length=255),kind: str=Query(default="",max_length=16),user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    query=select(IntelSubject).order_by(IntelSubject.updated_at.desc()).limit(200)
    if q:query=query.where(IntelSubject.name.ilike(f"%{q}%"))
    if kind:query=query.where(IntelSubject.kind==kind)
    rows=db.scalars(query).all()
    result=[]
    for row in rows:
        latest=db.scalar(select(IntelCollection).where(IntelCollection.subject_id==row.id).order_by(IntelCollection.created_at.desc()).limit(1))
        result.append({"id":row.id,"kind":row.kind,"eve_id":row.eve_id,"name":row.name,"updated_at":row.updated_at,"latest_collection":collection_payload(latest) if latest else None})
    return result


@router.post("/subjects",status_code=201)
async def create_subject(payload: SubjectInput,user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    at=datetime.now(timezone.utc)
    if payload.sighting:intel_sightings.validate(db,payload.sighting,payload.kind)
    existing=db.scalar(select(IntelSubject).where(IntelSubject.kind==payload.kind,IntelSubject.eve_id==payload.eve_id))
    if existing:
        if payload.sighting:intel_sightings.record(db,existing,payload.sighting,user,at);db.commit()
        return subject_payload(existing)
    source=source_factory()
    try:
        profile=await source.profile(payload.kind,payload.eve_id)
        data={"esi":{"state":"available","fetched_at":datetime.now(timezone.utc).isoformat(),"data":profile}}
        name=profile["name"]
    except Exception as error:
        cached=name_map(db,payload.kind,{payload.eve_id})
        if payload.eve_id not in cached:raise HTTPException(502,"Public ESI identity lookup failed; retry before adding this subject") from error
        name=cached[payload.eve_id];data={"esi":{"state":"unavailable","data":{"name":name},"notice":"Identity from local public cache; public ESI unavailable"}}
    finally:await source.close()
    row=IntelSubject(kind=payload.kind,eve_id=payload.eve_id,name=name,public_data=data,created_by_user_id=user.id)
    db.add(row)
    try:db.flush()
    except IntegrityError:
        db.rollback()
        row=db.scalar(select(IntelSubject).where(IntelSubject.kind==payload.kind,IntelSubject.eve_id==payload.eve_id))
        if payload.sighting:intel_sightings.record(db,row,payload.sighting,user,at);db.commit()
        return subject_payload(row)
    stable={key:value for key,value in profile.items() if key!="source_errors"} if data["esi"]["state"]=="available" else {"name":name}
    observe(db,row,"esi",stable)
    if payload.sighting:intel_sightings.record(db,row,payload.sighting,user,at)
    record_audit_event(db,event_kind="intel",title=f"Intel subject added: {name}"[:255],actor_user=user,body=f"{payload.kind}:{payload.eve_id}")
    db.commit();return subject_payload(row)


@router.post("/subjects/{subject_id}/collect",status_code=202)
def collect(subject_id: int,payload: CollectInput,user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    subject_or_404(db,subject_id)
    active=db.scalar(select(IntelCollection).where(IntelCollection.subject_id==subject_id,IntelCollection.status.in_(["queued","running"])))
    if active:return collection_payload(active)
    if (db.scalar(select(func.count()).select_from(IntelCollection).where(IntelCollection.status.in_(["queued","running"]))) or 0)>=100:raise HTTPException(409,"The intel queue is full; allow existing collections to finish")
    at=datetime.now(timezone.utc)
    row=IntelCollection(id=str(uuid4()),subject_id=subject_id,requested_by_user_id=user.id,status="queued",from_at=at-timedelta(days=payload.days),to_at=at,max_pages=payload.max_pages)
    db.add(row)
    try:db.flush()
    except IntegrityError:
        db.rollback();return collection_payload(db.scalar(select(IntelCollection).where(IntelCollection.subject_id==subject_id,IntelCollection.status.in_(["queued","running"]))))
    record_audit_event(db,event_kind="intel",title="Public intel collection queued",actor_user=user,body=f"subject={subject_id}; days={payload.days}; pages_per_feed={payload.max_pages}")
    db.commit();return collection_payload(row)


@router.get("/collections/{job_id}")
def collection(job_id: str,user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    row=db.get(IntelCollection,job_id)
    if row is None:raise HTTPException(404,"Collection not found")
    return collection_payload(row)


@router.post("/collections/{job_id}/cancel")
def cancel(job_id: str,user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    row=db.get(IntelCollection,job_id)
    if row is None:raise HTTPException(404,"Collection not found")
    db.execute(update(IntelCollection).where(IntelCollection.id==job_id,IntelCollection.status.in_(["queued","running"])).values(status="cancelled",finished_at=datetime.now(timezone.utc),lease_token=None,lease_until=None))
    record_audit_event(db,event_kind="intel",title="Intel collection cancelled",actor_user=user,body=job_id)
    db.commit();db.refresh(row);return collection_payload(row)


@router.post("/collections/{job_id}/retry",status_code=202)
def retry(job_id: str,user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    row=db.get(IntelCollection,job_id)
    if row is None:raise HTTPException(404,"Collection not found")
    if row.status not in {"failed","partial","cancelled"} or row.stage=="finished":raise HTTPException(409,"Start a new collection to deepen a finished report; only interrupted collections can resume")
    active=db.scalar(select(IntelCollection.id).where(IntelCollection.subject_id==row.subject_id,IntelCollection.status.in_(["queued","running"])))
    if active:raise HTTPException(409,"Another collection for this subject is active")
    row.status="queued";row.available_at=datetime.now(timezone.utc);row.retry_count=0;row.lease_token=None;row.lease_until=None;row.finished_at=None
    try:db.commit()
    except IntegrityError:db.rollback();raise HTTPException(409,"Another collection for this subject became active")
    return collection_payload(row)


@router.get("/subjects/{subject_id}/report")
def report(subject_id: int,from_at: datetime|None=None,to_at: datetime|None=None,user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    subject=subject_or_404(db,subject_id)
    end=utc(to_at) if to_at else datetime.now(timezone.utc);start=utc(from_at) if from_at else end-timedelta(days=90)
    if start>=end or end-start>timedelta(days=20000):raise HTTPException(422,"Choose a positive report window of at most 20,000 days")
    return build_report(db,subject,start,end)


@router.get("/subjects/{subject_id}/authorized")
def authorized(subject_id: int,user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    subject=subject_or_404(db,subject_id)
    result=private_enrichment(db,user,subject)
    if result["state"]=="authorized":
        record_audit_event(db,event_kind="intel",title="Authorized intel enrichment viewed",actor_user=user,body=f"subject={subject_id}");db.commit()
    return result


@router.post("/subjects/{subject_id}/authorized/refresh")
async def authorized_refresh(subject_id: int,payload: AuthorizedRefreshInput,user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    subject=subject_or_404(db,subject_id)
    result=await refresh_authorized(db,user,subject,payload.dataset)
    record_audit_event(db,event_kind="intel",title="Authorized intel enrichment refreshed",actor_user=user,body=f"subject={subject_id}; dataset={payload.dataset}");db.commit()
    return result


@router.get("/subjects/{subject_id}/notes")
def notes(subject_id: int,user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    subject_or_404(db,subject_id)
    rows=db.execute(select(IntelNote,User.display_name).join(User,User.id==IntelNote.author_user_id).where(IntelNote.subject_id==subject_id).order_by(IntelNote.id.desc()).limit(100)).all()
    from app.services.permissions import can_view_at_least
    moderate=can_view_at_least(user,"admin",db)
    return [note_payload(row,name,user,db,moderate) for row,name in rows]


@router.post("/subjects/{subject_id}/notes",status_code=201)
def add_note(subject_id: int,payload: NoteInput,user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    subject_or_404(db,subject_id)
    if not payload.body.strip():raise HTTPException(422,"Write a note before saving")
    row=IntelNote(subject_id=subject_id,author_user_id=user.id,body=payload.body.strip());db.add(row)
    record_audit_event(db,event_kind="intel",title="Intel analyst note added",actor_user=user,body=f"subject={subject_id}");db.commit()
    return note_payload(row,user.display_name,user,db)

def can_manage_note(row,user,db):
    from app.services.permissions import can_view_at_least
    return row.author_user_id==user.id or can_view_at_least(user,"admin",db)


def note_payload(row,author,user,db,moderate=None):
    allowed=can_manage_note(row,user,db) if moderate is None else row.author_user_id==user.id or moderate
    return {"id":row.id,"body":row.body,"author":author,"created_at":row.created_at,"can_edit":allowed,"can_delete":allowed}


def managed_note(db,subject_id,note_id,user):
    subject_or_404(db,subject_id)
    row=db.scalar(select(IntelNote).where(IntelNote.id==note_id,IntelNote.subject_id==subject_id))
    if row is None:raise HTTPException(404,"Intel note not found")
    if not can_manage_note(row,user,db):raise HTTPException(403,"Only the note author or an administrator can change this note")
    return row


@router.patch("/subjects/{subject_id}/notes/{note_id}")
def edit_note(subject_id:int,note_id:int,payload:NoteEditInput,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    row=managed_note(db,subject_id,note_id,user)
    if not payload.body.strip():raise HTTPException(422,"Write a note before saving")
    author=db.get(User,row.author_user_id).display_name
    changed=db.execute(update(IntelNote).where(IntelNote.id==row.id,IntelNote.subject_id==subject_id,IntelNote.body==payload.expected_body)
        .values(body=payload.body.strip()).execution_options(synchronize_session=False)).rowcount
    if changed!=1:raise HTTPException(409,"This note changed or was deleted. Reload the notes before trying again.")
    record_audit_event(db,event_kind="intel",title="Intel analyst note edited",actor_user=user,body=f"subject={subject_id}; note={note_id}")
    db.commit();db.refresh(row)
    return note_payload(row,author,user,db)


@router.delete("/subjects/{subject_id}/notes/{note_id}")
def delete_note(subject_id:int,note_id:int,payload:NoteDeleteInput,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    row=managed_note(db,subject_id,note_id,user)
    changed=db.execute(delete(IntelNote).where(IntelNote.id==row.id,IntelNote.subject_id==subject_id,IntelNote.body==payload.expected_body)
        .execution_options(synchronize_session=False)).rowcount
    if changed!=1:raise HTTPException(409,"This note changed or was deleted. Reload the notes before trying again.")
    record_audit_event(db,event_kind="intel",title="Intel analyst note deleted",actor_user=user,body=f"subject={subject_id}; note={note_id}")
    db.commit()
    return {"deleted":True,"id":note_id}

@router.get('/sighting-lookups')
def sighting_lookups(kind:Literal['system','ship'],q:str=Query('',max_length=120),user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return intel_sightings.lookup(db,kind,q)


@router.post('/subjects/{subject_id}/sightings',status_code=201)
def record_sighting(subject_id:int,payload:SightingInput,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    subject=subject_or_404(db,subject_id)
    row=intel_sightings.record(db,subject,payload,user)
    db.commit()
    return intel_sightings.payload(row,user.display_name)
