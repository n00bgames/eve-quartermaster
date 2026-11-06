from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Query,Response
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import User
from app.services import matchups
from app.services import matchup_examples
from app.services.killboard_settings import killboard_settings
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


def fit_research_access(db: Session, user_id: int, type_id: int) -> dict:
    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None or not can_view_section(user, 'matchups', db):
        raise HTTPException(403, 'Matchups permission is required')
    if db.execute(matchups.ships().where(matchups.EveType.type_id == type_id)).first() is None:
        raise HTTPException(404, 'Published ship hull not found in imported SDE')
    settings = killboard_settings(db)
    if not settings['enabled']:
        raise HTTPException(409, 'The Killboard data source is disabled')
    return settings


@router.get('/ships/{type_id}/examples')
async def examples(type_id: int, context: Context = 'small_gang',
                   user: User = Depends(access), db: Session = Depends(get_db)):
    user_id = user.id
    settings = await run_in_threadpool(fit_research_access, db, user_id, type_id)
    # The public request can wait on upstream I/O. Release the read transaction first.
    await run_in_threadpool(db.rollback)
    sample = await matchup_examples.source.sample(type_id, settings['request_delay_seconds'])

    def render():
        fit_research_access(db, user_id, type_id)
        return matchup_examples.render_examples(db, type_id, context, sample)

    return await run_in_threadpool(render)


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
