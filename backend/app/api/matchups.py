from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Query,Response
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy.orm import Session
from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import User
from app.services import matchups
from app.services.permissions import can_view_section

def access(response:Response,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    response.headers['Cache-Control']='private, no-store'
    if not can_view_section(user,'matchups',db):raise HTTPException(403,'Matchups permission is required')
    return user

router=APIRouter(prefix='/matchups',tags=['matchups'],dependencies=[Depends(access)])
Context=Literal['small_gang','fleet']

class ScanInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    text:str=Field(min_length=1,max_length=500000)

@router.get('/catalog')
def catalog(db:Session=Depends(get_db)):
    return matchups.catalog(db)

@router.get('/ships')
def search(q:str=Query(min_length=2,max_length=100),db:Session=Depends(get_db)):
    if len(q.strip())<2:raise HTTPException(422,'Enter at least two characters')
    return matchups.search(db,q.strip())

@router.get('/ships/{type_id}')
def card(type_id:int,context:Context='small_gang',db:Session=Depends(get_db)):
    return matchups.card(db,type_id,context)

@router.post('/analyze')
def analyze(payload:ScanInput,db:Session=Depends(get_db)):
    try:return matchups.analyze(db,payload.text)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc

@router.get('/scans/{token}')
def scan(token:str,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    from app.api.local_scan import authenticated_row
    if not can_view_section(user,'dscan',db):raise HTTPException(403,'D-Scan permission is required to open a saved scan')
    row=authenticated_row(db,token,user,'dscan')
    return matchups.project(row.payload)
