"""Authenticated Industry Report generation and revocable public snapshots/live links."""
from datetime import datetime, timedelta, timezone
import secrets
from fastapi import APIRouter,Depends,HTTPException,Request,Response,Query
from pydantic import Field
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from app.api.auth import get_current_user
from app.api import local_scan as shared
from app.db.session import get_db
from app.models import User
from app.models.local_scan import LocalScanReport
from app.services import industry_reports as service
from app.services.local_scan import RETENTIONS,now
from app.services.report_identity import report_identity

router=APIRouter(prefix="/industry-reports",tags=["industry-reports"])
class IndustryInput(shared.ScanInput):
    text: str = ""
    is_private: bool = True
    dynamic: bool = False

def require_report(response:Response,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if not service.can_report(db,user):raise HTTPException(403,"Industry Report access is required")
    shared.public_headers(response)
    return user

@router.get("/context")
def context(user:User=Depends(require_report),db:Session=Depends(get_db)):
    return {"retentions":list(RETENTIONS),"creator_name":report_identity(db,user)[0]}

@router.post("",status_code=201)
async def generate(payload:IndustryInput,request:Request,user:User=Depends(require_report),db:Session=Depends(get_db)):
    if user.id in shared._generating or len(shared._generating)>=4:raise HTTPException(429,"Report generation is busy; retry shortly")
    if (db.scalar(select(func.count()).select_from(LocalScanReport).where(LocalScanReport.created_by_user_id==user.id,LocalScanReport.created_at>now()-timedelta(minutes=1))) or 0)>=10:
        raise HTTPException(429,"Generate at most 10 reports per minute")
    shared._generating.add(user.id)
    try:
        scope=await service.permitted_scope(db,user)
        snapshot=service.build(db,scope)
        db.refresh(user)
        if user.deleted_at is not None or not service.can_report(db,user):raise HTTPException(403,"Industry Report access changed")
        scope = service.validate_scope(scope, await service.permitted_scope(db,user))
        creator,_=report_identity(db,user,payload.anonymous)
        lifetime=RETENTIONS[payload.retention];at=now()
        row=LocalScanReport(report_kind="industry",token=secrets.token_urlsafe(32),created_by_user_id=user.id,account_name=creator,
            is_private=payload.is_private,anonymous=payload.anonymous,dynamic=payload.dynamic,
            application_version=request.app.version,created_at=at,expires_at=at+timedelta(seconds=lifetime) if lifetime else None,
            retention=payload.retention,payload={**snapshot,"_scope":scope})
        db.add(row);db.commit()
        return {**shared.metadata(row),**snapshot}
    finally:shared._generating.discard(user.id)

async def load(db,token,user=None):
    row=shared.public_row(db,token,"industry") if user is None else shared.authenticated_row(db,token,user,"industry")
    if row.dynamic:
        creator=db.get(User,row.created_by_user_id) if row.created_by_user_id else None
        if not creator or creator.deleted_at is not None or not service.can_report(db,creator):raise HTTPException(404,"Report access is no longer available")
        current=await service.permitted_scope(db,creator)
        scope=service.validate_scope(row.payload["_scope"],current)
        data=service.build(db,scope)
        db.expire_all()
        creator = db.get(User, row.created_by_user_id) if row.created_by_user_id else None
        if not creator or creator.deleted_at is not None: raise HTTPException(404, "Report access changed")
        service.validate_scope(scope, await service.permitted_scope(db,creator))
        # Expiry/deletion/private status may change while the current data is built.
        row=shared.public_row(db,token,"industry") if user is None else shared.authenticated_row(db,token,user,"industry")
    else:data={k:v for k,v in row.payload.items() if not k.startswith("_")}
    return {**shared.metadata(row),**data}

@router.get("/reports")
def listing(user:User=Depends(require_report),db:Session=Depends(get_db),offset:int=Query(0,ge=0),limit:int=Query(25,ge=1,le=100)):
    return shared.report_listing(user,db,offset=offset,limit=limit,kind="industry")

@router.post("/reports/delete")
def delete_reports(payload:shared.DeleteInput,user:User=Depends(require_report),db:Session=Depends(get_db)):
    return shared.delete_scoped_reports(payload,user,db,"industry")

@router.get("/reports/{token}")
async def saved(token:str,user:User=Depends(require_report),db:Session=Depends(get_db)):
    return await load(db,token,user)

@router.get("/public/{token}")
async def public(token:str,response:Response,db:Session=Depends(get_db)):
    shared.public_headers(response)
    return await load(db,token)

async def export(db,token,format,user=None):
    if format not in {"csv","pdf"}:raise HTTPException(404,"Unsupported report format")
    data=await load(db,token,user)
    content=await run_in_threadpool(service.pdf_content if format=="pdf" else service.csv_content,data)
    db.expire_all()
    if user:
        db.refresh(user)
        if user.deleted_at is not None or not service.can_report(db,user):raise HTTPException(403,"Industry Report access changed")
    # Recheck current rights as well as expiry after export rendering.
    await load(db,token,user)
    response=Response(content,media_type="application/pdf" if format=="pdf" else "text/csv; charset=utf-8",
        headers={"Content-Disposition":f'attachment; filename="eqm-industry-report.{format}"'})
    shared.public_headers(response)
    return response

@router.get("/reports/{token}/export/{format}")
async def saved_export(token:str,format:str,user:User=Depends(require_report),db:Session=Depends(get_db)):
    return await export(db,token,format,user)

@router.get("/public/{token}/export/{format}")
async def public_export(token:str,format:str,db:Session=Depends(get_db)):
    return await export(db,token,format)
