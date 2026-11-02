"""Personal purchase/hauling receipts with explicit revocable public snapshots."""
from copy import deepcopy
from datetime import timedelta
import secrets
from threading import BoundedSemaphore
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select, func, delete
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from app.api.auth import get_current_user
from app.api.market import require_market
from app.api import local_scan as shared
from app.core.config import get_settings
from app.db.session import get_db
from app.domain import receipts as service
from app.models import User, EveType
from app.models.local_scan import LocalScanReport
from app.schemas.receipts import PasteInput, ReceiptInput, RouteInput
from app.services.local_scan import now, RETENTIONS, active_reports, utc
from app.services.report_identity import report_identity
from app.services.permissions import can_view_section
from app.services.audit import record_audit_event
from app.services import receipt_exports

router=APIRouter(prefix="/receipts",tags=["receipts"])
_exports=BoundedSemaphore(2)


def protected(response:Response,user:User=Depends(require_market)):
    shared.public_headers(response)
    return user


def build(db,payload):
    try:result=service.build(payload.model_dump(mode="json"))
    except (ValueError,ArithmeticError) as error:raise HTTPException(422,str(error)) from error
    names=[row["item"].casefold() for row in result["groups"]]
    types={row.name.casefold():row.type_id for row in db.scalars(select(EveType).where(func.lower(EveType.name).in_(names)))}
    for row in result["groups"]:row["type_id"]=types.get(row["item"].casefold())
    return result


def present(db,row,draft=False):
    creator=db.get(User,row.created_by_user_id) if row.created_by_user_id else None
    name=report_identity(db,creator,row.anonymous)[0] if creator and creator.deleted_at is None else "Anonymous"
    result={**deepcopy(row.payload["receipt"]),"token":row.token,"report_kind":"receipt","is_private":row.is_private,
            "anonymous":row.anonymous,"creator_name":name,"application_version":row.application_version,
            "created_at":utc(row.created_at).isoformat(),"expires_at":utc(row.expires_at).isoformat() if row.expires_at else None,
            "retention":row.retention,"share_url":None if row.is_private else f"{get_settings().frontend_url.rstrip('/')}/#receipt/{row.token}"}
    if draft:result["draft"]=deepcopy(row.payload["_input"])
    return result


def owned(db,token,user):
    row=db.scalar(select(LocalScanReport).where(LocalScanReport.token==token,LocalScanReport.created_by_user_id==user.id,active_reports(kind="receipt")))
    if row is None:raise HTTPException(404,"Receipt not found or expired")
    return row


@router.get("/context")
def context(user:User=Depends(protected),db:Session=Depends(get_db)):
    return {"retentions":list(RETENTIONS),"creator_name":report_identity(db,user)[0],"can_plan_route":can_view_section(user,"navigation",db),"max_lines":service.MAX_LINES}


@router.post("/parse")
def parse(payload:PasteInput,user:User=Depends(protected)):
    try:return service.parse(payload.text)
    except (ValueError,ArithmeticError) as error:raise HTTPException(422,str(error)) from error


@router.post("/preview")
def preview(payload:ReceiptInput,request:Request,user:User=Depends(protected),db:Session=Depends(get_db)):
    return {**build(db,payload),"creator_name":report_identity(db,user,payload.anonymous)[0],"application_version":request.app.version,"created_at":now().isoformat()}


@router.post("/route")
def route(payload:RouteInput,user:User=Depends(protected),db:Session=Depends(get_db)):
    if not can_view_section(user,"navigation",db):raise HTTPException(403,"Navigation permission is required to plan a route")
    from app.services.navigation import plan_gate_route
    names=[payload.origin,*payload.via,payload.destination];systems=[];jumps=0
    try:
        for origin,destination in zip(names,names[1:]):
            leg=plan_gate_route(db,origin,destination,highsec_only=payload.preference=="highsec",prefer_safer=payload.preference=="safer",context_gate_hops=0)
            systems.extend([row["name"] for row in leg["systems"]][1:] if systems else [row["name"] for row in leg["systems"]]);jumps+=leg["jump_count"]
            if len(systems)>500:raise ValueError("Keep the receipt route within 500 systems")
    except ValueError as error:raise HTTPException(422,str(error)) from error
    return {"mode":"gate","origin":systems[0],"destination":systems[-1],"systems":systems,"jump_count":jumps,"source":"planned"}


@router.post("",status_code=201)
def generate(payload:ReceiptInput,request:Request,user:User=Depends(protected),db:Session=Depends(get_db)):
    count=db.scalar(select(func.count()).select_from(LocalScanReport).where(LocalScanReport.created_by_user_id==user.id,LocalScanReport.report_kind=="receipt",LocalScanReport.created_at>now()-timedelta(minutes=1))) or 0
    if count>=10:raise HTTPException(429,"Save at most 10 receipts per minute")
    result=build(db,payload);at=now();lifetime=RETENTIONS[payload.retention]
    row=LocalScanReport(token=secrets.token_urlsafe(32),report_kind="receipt",created_by_user_id=user.id,
        account_name=report_identity(db,user,payload.anonymous)[0],application_version=request.app.version,is_private=payload.is_private,anonymous=payload.anonymous,dynamic=False,
        retention=payload.retention,created_at=at,expires_at=at+timedelta(seconds=lifetime) if lifetime else None,
        payload={"receipt":result,"_input":payload.model_dump(mode="json")})
    db.add(row);record_audit_event(db,event_kind="market",title="Market run receipt saved",actor_user=user,body=f"transactions={result['transaction_count']}; public={not row.is_private}")
    db.commit();return present(db,row,draft=True)


@router.get("/reports")
def listing(offset:int=Query(0,ge=0),limit:int=Query(25,ge=1,le=100),user:User=Depends(protected),db:Session=Depends(get_db)):
    filters=[LocalScanReport.created_by_user_id==user.id,active_reports(kind="receipt")]
    rows=db.scalars(select(LocalScanReport).where(*filters).order_by(LocalScanReport.created_at.desc(),LocalScanReport.token).offset(offset).limit(limit)).all()
    return {"reports":[{"token":row.token,"title":row.payload["receipt"]["title"],"recipient":row.payload["receipt"]["recipient"],
        "created_at":utc(row.created_at).isoformat(),"is_private":row.is_private,"grand_total":row.payload["receipt"]["grand_total"],
        "expires_at":utc(row.expires_at).isoformat() if row.expires_at else None} for row in rows],
        "total":db.scalar(select(func.count()).select_from(LocalScanReport).where(*filters))}


@router.post("/reports/delete")
def remove(payload:shared.DeleteInput,user:User=Depends(protected),db:Session=Depends(get_db)):
    filters=[LocalScanReport.report_kind=="receipt",LocalScanReport.created_by_user_id==user.id]
    if payload.tokens:filters.append(LocalScanReport.token.in_(payload.tokens))
    elif payload.from_at is not None:filters.extend([LocalScanReport.created_at>=utc(payload.from_at),LocalScanReport.created_at<utc(payload.to_at)])
    count=db.execute(delete(LocalScanReport).where(*filters).execution_options(synchronize_session="fetch")).rowcount
    record_audit_event(db,event_kind="market",title="Market run receipts deleted",actor_user=user,body=f"count={count}")
    db.commit();return {"deleted":count}


@router.get("/reports/{token}")
def saved(token:str,user:User=Depends(protected),db:Session=Depends(get_db)):
    return present(db,owned(db,token,user),draft=True)


@router.get("/public/{token}")
def public(token:str,response:Response,db:Session=Depends(get_db)):
    shared.public_headers(response);return present(db,shared.public_row(db,token,"receipt"))


async def export(db,token,format,user=None):
    if format not in {"pdf","csv"}:raise HTTPException(404,"Unsupported receipt format")
    row=owned(db,token,user) if user else shared.public_row(db,token,"receipt")
    data=present(db,row);uid=user.id if user else None
    db.rollback()  # No connection held during PDF/CSV rendering.
    def render():
        if not _exports.acquire(blocking=False):raise HTTPException(503,"Receipt export is busy; retry shortly")
        try:return receipt_exports.pdf_content(data) if format=="pdf" else receipt_exports.csv_content(data)
        finally:_exports.release()
    content=await run_in_threadpool(render)
    if uid:
        user=db.get(User,uid,populate_existing=True)
        if not user or user.deleted_at is not None or not can_view_section(user,"market",db):raise HTTPException(403,"Market access changed")
        owned(db,token,user)
    else:shared.public_row(db,token,"receipt")
    response=Response(content,media_type="application/pdf" if format=="pdf" else "text/csv",headers={"Content-Disposition":f'attachment; filename="eqm-receipt-{token[:10]}.{format}"'})
    shared.public_headers(response);return response


@router.get("/reports/{token}/export/{format}")
async def saved_export(token:str,format:str,user:User=Depends(protected),db:Session=Depends(get_db)):
    return await export(db,token,format,user)


@router.get("/public/{token}/export/{format}")
async def public_export(token:str,format:str,db:Session=Depends(get_db)):
    return await export(db,token,format)
