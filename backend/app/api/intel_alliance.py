from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.api.auth import get_current_user
from app.api.intel import access
from app.db.session import get_db
from app.models import User
from app.services.intel_reports import subject_or_404
from app.services.intel_membership import now
from app.services.intel_alliance_cache import roster
from app.services.intel_alliance_details import details
from app.domain.intel import utc

router = APIRouter(prefix="/intel", tags=["intel"], dependencies=[Depends(access)])


def alliance(db, sid):
    subject = subject_or_404(db, sid)
    if subject.kind != "alliance":
        raise HTTPException(422, "Member corporations require an alliance dossier")
    return subject


@router.get("/subjects/{subject_id}/corporations")
def corporations(subject_id: int, page: int = Query(1, ge=1, le=1000),
                 search: str = Query("", max_length=255), sort: str = Query("members", pattern="^(members|name)$"),
                 db: Session = Depends(get_db)):
    data = roster(db, alliance(db, subject_id))
    rows = data.pop("rows")
    query = search.casefold().strip()
    rows = [row for row in rows if not query or query in " ".join(str(row.get(k) or "") for k in ("name", "ticker", "ceo_name")).casefold()]
    rows.sort(key=lambda row: ((-(row["member_count"] if row.get("member_count") is not None else -1), row["name"].casefold()) if sort == "members" else (row["name"].casefold(),)))
    return {**data, "stale": not data["fetched_at"] or (now()-utc(data["fetched_at"])).total_seconds() > 86400,
            "rows": rows[(page-1)*50:page*50], "total": len(rows), "page": page, "page_size": 50}


@router.get("/subjects/{subject_id}/corporations/{corporation_id}")
async def corporation(subject_id: int, corporation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return await details(db, subject_id, corporation_id, user.id)


@router.post("/subjects/{subject_id}/corporations/{corporation_id}/refresh")
async def refresh(subject_id: int, corporation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return await details(db, subject_id, corporation_id, user.id, refresh=True)
