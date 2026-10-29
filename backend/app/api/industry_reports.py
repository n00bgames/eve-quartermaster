"""Authenticated Industry Report generation and revocable public snapshots/live links."""
from datetime import datetime, timedelta, timezone
import secrets
from fastapi import APIRouter,Depends,HTTPException,Request,Response,Query
from pydantic import Field
from typing import Annotated
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
from app.services.industry_storage import StorageIndex

router=APIRouter(prefix="/industry-reports",tags=["industry-reports"])
class IndustryInput(shared.ScanInput):
    text: str = ""
    is_private: bool = True
    dynamic: bool = False
    storage: list[Annotated[str, Field(max_length=100)]] = Field(default_factory=list, max_length=100)

def require_report(response:Response,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if not service.can_report(db,user):raise HTTPException(403,"Industry Report access is required")
    shared.public_headers(response)
    return user

@router.get("/context")
def context(user:User=Depends(require_report),db:Session=Depends(get_db)):
    return {"retentions":list(RETENTIONS),"creator_name":report_identity(db,user)[0]}

@router.get("/storage")
async def storage(user:User=Depends(require_report),db:Session=Depends(get_db)):
    scope=await service.permitted_scope(db,user)
    return {"storage":StorageIndex(db,scope["stock"]).options(scope["stock"])}


@router.post("",status_code=201)
async def generate(payload:IndustryInput,request:Request,user:User=Depends(require_report),db:Session=Depends(get_db)):
    return await create_report(payload,request,user,db)


async def create_report(payload,request,user,db,inventory=False):
    if user.id in shared._generating or len(shared._generating)>=4:raise HTTPException(429,"Report generation is busy; retry shortly")
    if (db.scalar(select(func.count()).select_from(LocalScanReport).where(LocalScanReport.created_by_user_id==user.id,LocalScanReport.created_at>now()-timedelta(minutes=1))) or 0)>=10:
        raise HTTPException(429,"Generate at most 10 reports per minute")
    shared._generating.add(user.id)
    try:
        scope=inventory_scope(db,user) if inventory else await service.permitted_scope(db,user)
        storage=[] if inventory else payload.storage
        snapshot=service.build_inventory(db,scope) if inventory else service.build(db,scope,storage)
        db.refresh(user)
        if user.deleted_at is not None or not (can_inventory(db,user) if inventory else service.can_report(db,user)):raise HTTPException(403,"Report access changed")
        scope = service.validate_scope(scope, inventory_scope(db,user) if inventory else await service.permitted_scope(db,user))
        creator,_=report_identity(db,user,payload.anonymous or not payload.is_private)
        lifetime=RETENTIONS[payload.retention];at=now()
        row=LocalScanReport(report_kind="inventory" if inventory else "industry",token=secrets.token_urlsafe(32),created_by_user_id=user.id,account_name=creator,
            is_private=payload.is_private,anonymous=payload.anonymous or not payload.is_private,dynamic=payload.dynamic,
            application_version=request.app.version,created_at=at,expires_at=at+timedelta(seconds=lifetime) if lifetime else None,
            retention=payload.retention,payload={**snapshot,"_scope":scope,"_storage":storage})
        db.add(row);db.commit()
        return service.present({**shared.metadata(row),**snapshot},public=not row.is_private,inventory=inventory)
    finally:shared._generating.discard(user.id)

def can_inventory(db,user):
    from app.services.permissions import can_view_section
    return can_view_section(user,"inventory_reports",db) and can_view_section(user,"assets",db)


def inventory_scope(db,user):
    if not can_inventory(db,user):raise HTTPException(403,"Inventory Report and Assets permissions are required")
    from app.models import OwnershipEntity
    from app.services.asset_visibility import visible_owner_clause
    return {"stock":list(db.scalars(select(OwnershipEntity.id).where(visible_owner_clause(user,db))))}


async def load(db,token,user=None,kind="industry"):
    inventory=kind=="inventory"
    if inventory:
        if user is None:raise HTTPException(404,"Report not found")
        row=db.scalar(select(LocalScanReport).where(LocalScanReport.token==token,LocalScanReport.created_by_user_id==user.id,shared.service.active_reports(kind=kind)))
        if row is None:raise HTTPException(404,"Report not found or expired")
    else:
        row=shared.public_row(db,token,kind) if user is None else shared.authenticated_row(db,token,user,kind)
    if row.dynamic and not inventory:
        creator=db.get(User,row.created_by_user_id) if row.created_by_user_id else None
        if not creator or creator.deleted_at is not None or not service.can_report(db,creator):raise HTTPException(404,"Report access is no longer available")
        current=await service.permitted_scope(db,creator)
        scope=service.validate_scope(row.payload["_scope"],current)
        try:
            data=service.build(db,scope,row.payload.get("_storage",[]))
        except HTTPException as exc:
            raise HTTPException(404,"Report storage changed; generate a new report") from exc
        db.expire_all()
        creator = db.get(User, row.created_by_user_id) if row.created_by_user_id else None
        if not creator or creator.deleted_at is not None: raise HTTPException(404, "Report access changed")
        service.validate_scope(scope, await service.permitted_scope(db,creator))
        # Expiry/deletion/private status may change while the current data is built.
        row=shared.public_row(db,token,"industry") if user is None else shared.authenticated_row(db,token,user,"industry")
    else:data={k:v for k,v in row.payload.items() if not k.startswith("_")}
    result={**shared.metadata(row),**data}
    if inventory:result.update(is_private=True,share_url=None,dynamic=False)
    return service.present(result,public=not row.is_private and not inventory,inventory=inventory)

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

async def export(db,token,format,user=None,kind="industry"):
    if format not in {"csv","pdf"}:raise HTTPException(404,"Unsupported report format")
    data=await load(db,token,user,kind)
    content=await run_in_threadpool(service.pdf_content if format=="pdf" else service.csv_content,data)
    db.expire_all()
    if user:
        db.refresh(user)
        if user.deleted_at is not None or not (can_inventory(db,user) if kind=="inventory" else service.can_report(db,user)):raise HTTPException(403,"Report access changed")
    # Recheck current rights as well as expiry after export rendering.
    await load(db,token,user,kind)
    response=Response(content,media_type="application/pdf" if format=="pdf" else "text/csv; charset=utf-8",
        headers={"Content-Disposition":f'attachment; filename="eqm-{kind}-report.{format}"'})
    shared.public_headers(response)
    return response

@router.get("/reports/{token}/export/{format}")
async def saved_export(token:str,format:str,user:User=Depends(require_report),db:Session=Depends(get_db)):
    return await export(db,token,format,user)

@router.get("/public/{token}/export/{format}")
async def public_export(token:str,format:str,db:Session=Depends(get_db)):
    return await export(db,token,format)
