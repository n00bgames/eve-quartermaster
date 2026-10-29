"""Creator-only inventory snapshots. No public generation or read/export routes."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query
from pydantic import BaseModel, ConfigDict
from typing import Literal
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.api.auth import get_current_user
from app.api import industry_reports as reports, local_scan as shared
from app.db.session import get_db
from app.models import User
from app.models.local_scan import LocalScanReport

router=APIRouter(prefix="/inventory-reports",tags=["inventory-reports"])

class InventoryInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    retention: Literal["30m","1h","2h","12h","24h","3days","7days","30days","permanent"] = "24h"

def require_inventory(response:Response,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if not reports.can_inventory(db,user):raise HTTPException(403,"Inventory Report and Assets permissions are required")
    shared.public_headers(response)
    return user

@router.get("/context")
def context(user:User=Depends(require_inventory),db:Session=Depends(get_db)):
    return {"retentions":list(reports.RETENTIONS),"creator_name":reports.report_identity(db,user)[0]}

@router.post("",status_code=201)
async def generate(payload:InventoryInput,request:Request,user:User=Depends(require_inventory),db:Session=Depends(get_db)):
    return await reports.create_report(reports.IndustryInput(retention=payload.retention,is_private=True),request,user,db,inventory=True)

@router.get("/reports")
def listing(user:User=Depends(require_inventory),db:Session=Depends(get_db),offset:int=Query(0,ge=0),limit:int=Query(25,ge=1,le=100)):
    filters=[LocalScanReport.created_by_user_id==user.id,shared.service.active_reports(kind="inventory")]
    rows=db.scalars(select(LocalScanReport).where(*filters).order_by(LocalScanReport.created_at.desc(),LocalScanReport.token).offset(offset).limit(limit))
    return {"reports":[{**shared.metadata(row),"is_private":True,"share_url":None} for row in rows],
        "total":db.scalar(select(func.count()).select_from(LocalScanReport).where(*filters))}

@router.post("/reports/delete")
def delete_reports(payload:shared.DeleteInput,user:User=Depends(require_inventory),db:Session=Depends(get_db)):
    # Stored inventory rows are always private; add an explicit owner condition as defense in depth.
    from sqlalchemy import delete
    from app.services.audit import record_audit_event
    filters=[LocalScanReport.report_kind=="inventory",LocalScanReport.created_by_user_id==user.id]
    if payload.tokens:filters.append(LocalScanReport.token.in_(payload.tokens))
    elif payload.from_at is not None:filters.extend([LocalScanReport.created_at>=shared.service.utc(payload.from_at),LocalScanReport.created_at<shared.service.utc(payload.to_at)])
    count=db.execute(delete(LocalScanReport).where(*filters).execution_options(synchronize_session="fetch")).rowcount
    record_audit_event(db,event_kind="intel",title="Inventory reports deleted",actor_user=user,body=f"count={count}")
    db.commit();return {"deleted":count}

@router.get("/reports/{token}")
async def saved(token:str,user:User=Depends(require_inventory),db:Session=Depends(get_db)):
    return await reports.load(db,token,user,"inventory")

@router.get("/reports/{token}/export/{format}")
async def export(token:str,format:str,user:User=Depends(require_inventory),db:Session=Depends(get_db)):
    return await reports.export(db,token,format,user,"inventory")
