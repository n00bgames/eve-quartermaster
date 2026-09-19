"""Navigation-scoped public atlas and owner-only LP lookups."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.navigation import require_navigation
from app.api.esi import get_linked_token, refresh_access_token, require_scope, token_scopes
from app.db.session import get_db
from app.models import EsiToken, EveCharacter, EveStation, EveSystem, User
from app.services import mission_atlas as atlas
from app.services.atlas_esi import activity_snapshot, public_snapshot
from app.services.esi_client import EsiClient

router = APIRouter(prefix="/navigation/atlas", tags=["mission-atlas"])
LP_SCOPE = "esi-characters.read_loyalty.v1"


@router.get("/catalog")
def catalog(_: User = Depends(require_navigation), db: Session = Depends(get_db)):
    return atlas.catalog(db)


@router.get("/activity")
async def activity(_: User = Depends(require_navigation)):
    return await activity_snapshot()


@router.get("/systems/{system_id}")
def system(system_id: int, _: User = Depends(require_navigation), db: Session = Depends(get_db)):
    result = atlas.system_detail(db, system_id)
    if result is None:
        raise HTTPException(404, "System not found in the imported SDE")
    return result


@router.get("/agents")
def agents(q: str = Query("", max_length=100), level: int | None = Query(None, ge=1, le=5),
           division_id: int | None = None, corporation_id: int | None = None, system_id: int | None = None,
           highsec_only: bool = False, origin_id: int | None = None, max_jumps: int | None = Query(None, ge=0, le=100),
           offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200),
           _: User = Depends(require_navigation), db: Session = Depends(get_db)):
    if origin_id is not None and db.get(EveSystem, origin_id) is None:
        raise HTTPException(404, "Origin system not found")
    if max_jumps is not None and origin_id is None:
        raise HTTPException(400, "Choose an origin before filtering by jumps")
    return atlas.find_agents(db, q, level, division_id, corporation_id, system_id,
        highsec_only, origin_id, max_jumps, offset, limit)


@router.get("/corporations")
def corporations(q: str = Query("", max_length=100), _: User = Depends(require_navigation), db: Session = Depends(get_db)):
    return atlas.corporation_directory(db, q)


@router.get("/stores/{corporation_id}/stations")
def store_stations(corporation_id: int, origin_id: int | None = None,
                   _: User = Depends(require_navigation), db: Session = Depends(get_db)):
    if origin_id is not None and db.get(EveSystem, origin_id) is None:
        raise HTTPException(404, "Origin system not found")
    distances = atlas.gate_distances(origin_id, atlas.edges(db)) if origin_id is not None else {}
    result = [dict(station_id=station.station_id, name=station.name, system_id=system.system_id,
        system_name=system.name, security_status=system.security_status, jumps=distances.get(system.system_id))
        for station, system in db.execute(select(EveStation, EveSystem).join(EveSystem)
            .where(EveStation.owner_id == corporation_id))]
    return sorted(result, key=lambda row:(row["jumps"] is None, row["jumps"] or 0, row["name"] or ""))


@router.get("/stores/{corporation_id}/offers")
async def offers(corporation_id: int, _: User = Depends(require_navigation), db: Session = Depends(get_db)):
    if not 1000000 <= corporation_id < 2000000:
        raise HTTPException(400, "Select an NPC corporation")
    snapshot = await public_snapshot(f"/loyalty/stores/{corporation_id}/offers/")
    if snapshot["data"] is None:
        raise HTTPException(502, "LP offers unavailable from ESI. Please retry.")
    return {**snapshot, "expires_at": snapshot["expires_at"].isoformat(),
        "data": atlas.decorate_offers(db, snapshot["data"]), "corporation_id": corporation_id}


@router.get("/characters")
def characters(response: Response, user: User = Depends(require_navigation), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    return [dict(token_id=t.id, character_id=c.character_id, name=c.name,
        has_lp_scope=LP_SCOPE in token_scopes(t), sync_opt_out=c.sync_opt_out)
        for t,c in db.execute(select(EsiToken, EveCharacter).join(EveCharacter, EsiToken.character_id == EveCharacter.id)
            .where(EsiToken.user_id == user.id, EsiToken.revoked_at.is_(None)).order_by(EveCharacter.name))]


def owned_lp_token(db, token_id, user):
    token, character = get_linked_token(db, token_id)
    if token.user_id != user.id:
        raise HTTPException(403, "Loyalty points are private to the character's linked account")
    if character.sync_opt_out:
        raise HTTPException(403, "This character has opted out of ESI collection")
    require_scope(token, LP_SCOPE, "Reading loyalty points")
    return token, character


@router.get("/characters/{token_id}/loyalty")
async def loyalty(token_id: int, response: Response, user: User = Depends(require_navigation), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    token, character = owned_lp_token(db, token_id, user)
    access_token = await refresh_access_token(token)
    db.commit()  # Preserve refresh-token rotation even if the following ESI read fails.
    rows, headers = await EsiClient(access_token).get_with_headers(f"/characters/{character.character_id}/loyalty/points/")
    names = {row["corporation_id"]: row["name"] for row in atlas.corporation_directory(db)}
    return dict(character_id=character.character_id, checked_at=datetime.now(timezone.utc).isoformat(),
        observed_at=headers.get("Last-Modified"), expires_at=headers.get("Expires"),
        balances=[{**row, "corporation_name": names.get(row["corporation_id"], f"Corporation {row['corporation_id']}")} for row in rows])
