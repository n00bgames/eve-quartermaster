"""Private ship history. Capital visibility is enforced before querying metrics."""
from fastapi import APIRouter,Depends,Query,Response
from sqlalchemy.orm import Session
from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import User
from app.services import ship_analytics as service

router=APIRouter(prefix='/analytics/ships',tags=['ship analytics'])


@router.get('')
def ships(response:Response,days:int=Query(30,ge=0,le=3660),scope:str='all',corporation_id:int|None=None,
          alliance_id:int|None=None,type_id:int|None=Query(None,gt=0),
          user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    response.headers.update({'Cache-Control':'no-store','X-Robots-Tag':'noindex, nofollow'})
    return service.history(db,user,days,scope=scope,corporation_id=corporation_id,alliance_id=alliance_id,type_id=type_id)
