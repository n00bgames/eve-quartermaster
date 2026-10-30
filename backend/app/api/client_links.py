"""Explicit in-client drafts: no mail-send permission or endpoint is used."""
from html import escape, unescape
import re
from typing import Literal
import asyncio
import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import Asset, Blueprint, EsiToken, EveCharacter, EveType, User
from app.services.esi_scope_policy import effective_token_scopes
from app.services.asset_visibility import can_view_owner_records
from app.services.permissions import can_view_section
from app.services.esi_client import EsiClient

router=APIRouter(prefix="/client-links",tags=["client-links"])
UI_SCOPE="esi-ui.open_window.v1"
CREATOR_ID=502978494

class LinkInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    kind:Literal["item","support"]="item"
    type_id:int|None=Field(default=None,gt=0,strict=True)
    name:str|None=Field(default=None,max_length=255)
    blueprint_id:int|None=Field(default=None,gt=0,strict=True)
    asset_id:int|None=Field(default=None,gt=0,strict=True)

class DraftInput(LinkInput):
    token_id:int=Field(gt=0,strict=True)

def validate_ui_consent_character(db,user_id,mode,eve_id):
    try:expected=int(mode.removeprefix("client_ui_"))
    except ValueError as exc:raise HTTPException(400,"Invalid in-game window authorization") from exc
    linked=db.scalar(select(EveCharacter).where(EveCharacter.character_id==expected))
    if eve_id!=expected or linked is None or linked.owner_user_id!=user_id:
        raise HTTPException(403,"Authorize the same linked character selected in EQM")

def own_token(db,user,token_id):
    token=db.get(EsiToken,token_id,populate_existing=True)
    character=db.get(EveCharacter,token.character_id,populate_existing=True) if token else None
    if not token or token.revoked_at or not character:
        raise HTTPException(404,"Character authorization is unavailable")
    if token.user_id!=user.id or character.owner_user_id!=user.id:
        raise HTTPException(403,"Choose one of your own linked characters")
    return token,character

@router.get("/characters")
def characters(response:Response,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    response.headers["Cache-Control"]="private, no-store"
    rows=db.execute(select(EsiToken,EveCharacter).join(EveCharacter,EveCharacter.id==EsiToken.character_id).where(
        EsiToken.user_id==user.id,EveCharacter.owner_user_id==user.id,EsiToken.revoked_at.is_(None)).order_by(EveCharacter.name)).all()
    return {"characters":[{"token_id":t.id,"name":c.name,"can_open":UI_SCOPE in effective_token_scopes(t,db)} for t,c in rows]}

@router.get("/characters/{token_id}/auth-url")
def consent(token_id:int,response:Response,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    from app.api.esi import build_auth_url
    response.headers["Cache-Control"]="private, no-store"
    token,character=own_token(db,user,token_id)
    # Preserve already granted, currently permitted integrations. Never add private scopes.
    scopes=sorted(effective_token_scopes(token,db)|{"publicData",UI_SCOPE})
    return build_auth_url(scopes,user,f"client_ui_{character.character_id}")

async def instance_visible(db,user,owner):
    if can_view_section(user,"assets",db) or can_view_section(user,"industry",db):
        if can_view_owner_records(owner,user,db):return True
    if can_view_section(user,"quartermaster",db):
        from app.services.quartermaster_access import oversight_scope
        scope=await oversight_scope(db)
        return bool(owner and (owner.character_id in scope.characters["blueprints"] if owner.character_id else owner.corporation_id in scope.corporations["blueprints"]))
    return False

async def item_body(db,user,data):
    bp=None;asset=None
    if data.blueprint_id is not None:
        bp=db.get(Blueprint,data.blueprint_id)
        if not bp or not await instance_visible(db,user,bp.ownership_entity):
            raise HTTPException(404,"Blueprint is unavailable within your current permissions")
        asset=bp.asset
    elif data.asset_id is not None:
        asset=db.get(Asset,data.asset_id)
        if not asset or not await instance_visible(db,user,asset.ownership_entity):
            raise HTTPException(404,"Asset is unavailable within your current permissions")
        bp=db.scalar(select(Blueprint).where(Blueprint.asset_id==asset.id))
    tid=bp.blueprint_type_id if bp else asset.type_id if asset else data.type_id
    item=db.get(EveType,tid) if tid else db.scalar(select(EveType).where(func.lower(EveType.name)==(data.name or "").strip().lower()))
    if not item:raise HTTPException(404,"Item type is not in the imported SDE")
    # Instance identifiers never come from the request or public report payloads.
    singleton=asset.eve_item_id if asset and asset.type_id==item.type_id and (bp or asset.is_singleton) else None
    link=f"showinfo:{item.type_id}"+(f"//{singleton}" if singleton else "")
    name=escape(item.name,quote=False)
    body=f'<url={link}>{name}</url>'
    if bp:
        body+=f'<br>{"BPC" if bp.is_copy else "BPO"} · ME {bp.material_efficiency} · TE {bp.time_efficiency}'
        if bp.is_copy:body+=f' · Runs remaining: {bp.runs_remaining if bp.runs_remaining is not None else "unknown"}'
        body+='<br>ME/TE and runs are from the latest EQM sync. The client controls access to instance details.'
    elif not singleton:body+='<br>Blueprint research and copy details, if applicable, belong to an owned instance.'
    body+='<br><br>Opened with EVE Quartermaster. This is an unsent draft; close it when finished.'
    return item.name,body,bool(singleton)

@router.post("/preview")
async def preview(data:LinkInput,response:Response,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    response.headers["Cache-Control"]="private, no-store"
    if data.kind=="support":return {"name":"Steihl Lianul","details":"Creator reference · Character Info link · optional ISK donations with the reason EQM","instance_link":False}
    title,body,exact=await item_body(db,user,data)
    lines=body.split("<br>")[:2]
    return {"name":title,"details":unescape(re.sub(r"<[^>]*>",""," · ".join(lines))),"instance_link":exact}

@router.post("/draft")
async def draft(data:DraftInput,response:Response,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    from app.api.esi import refresh_access_token
    response.headers["Cache-Control"]="private, no-store"
    token,character=own_token(db,user,data.token_id)
    if UI_SCOPE not in effective_token_scopes(token,db):raise HTTPException(409,"Enable in-game windows for this character first")
    if data.kind=="support":
        title="EVE Quartermaster · creator"
        body=f'<font size="24" color="#ff00ff00"><b><url=showinfo:1377//{CREATOR_ID}>Steihl Lianul</url></b></font><br><br>EVE Quartermaster is free software for capsuleers, built by a 20-year veteran capsuleer and his wittle AI agent.<br><br>If EQM has earned a place in your Neocom, optional ISK donations to Steihl Lianul with the reason EQM are always appreciated.<br><br>Thank you, and fly dangerously! o7<br><br>This is an unsent reference draft. Clicking the name opens Character Info; no ISK is transferred.'
        exact=False
    else:title,body,exact=await item_body(db,user,data)
    recipient=character.character_id
    access=await refresh_access_token(token)
    db.commit()
    token,character=own_token(db,user,data.token_id)
    if UI_SCOPE not in effective_token_scopes(token,db):raise HTTPException(403,"In-game windows are no longer permitted")
    if data.kind=="item":title,body,exact=await item_body(db,user,data)
    db.rollback()  # Do not hold a database transaction while waiting on ESI.
    client=EsiClient(access_token=access)
    try:
        await asyncio.wait_for(client.post("/ui/openwindow/newmail/",{"recipients":[recipient],"subject":("EQM · "+title)[:1000],"body":body}),timeout=35)
    except (asyncio.TimeoutError,HTTPException,httpx.RequestError) as exc:
        raise HTTPException(502,"EVE could not confirm opening the draft. Keep the selected character logged in; check the client before retrying.") from exc
    finally:await client.close()
    return {"opened":True,"instance_link":exact,"message":"Draft opened in EVE. Nothing was sent."}
