"""Presentation only: stored layouts never grant access to a module or data."""
import base64
import binascii
from io import BytesIO
import warnings
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.auth import get_current_user
from app.db.session import get_db
from app.core.config import get_settings
from app.models import User, AuditEvent
from app.models.appearance import UserAppearance, SiteBranding
from app.services.permissions import role_rank, ROLE_RANK

router=APIRouter(prefix="/appearance",tags=["appearance"])
MODULES=set("overview navigation characters skills fittings jump_clones roster esi local_scan dscan intel_reports local_threat market exchange hypernet plex bounty_analytics notes inventory_reports industry_reports quartermaster manufacturing research_projects mining planetary_industry corporations ownership assets industry contracts analytics fleet_assignments doctrines srp killboard battle_reports calendar_events recruiting profile settings audit".split())
Key=Annotated[str,Field(pattern=r"^[a-zA-Z0-9_.:-]{1,100}$")]
Color=Annotated[str,Field(pattern=r"^#[0-9a-fA-F]{6}$")]

class Strict(BaseModel):
    model_config=ConfigDict(extra="forbid")

class Theme(Strict):
    background: Color
    panel: Color
    text: Color
    muted: Color
    accent: Color
    border: Color

    @model_validator(mode="after")
    def readable(self):
        def luminance(c):
            rgb=[int(c[i:i+2],16)/255 for i in (1,3,5)]
            rgb=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in rgb]
            return sum(a*b for a,b in zip(rgb,(.2126,.7152,.0722)))
        def contrast(a,b):
            a,b=sorted([luminance(a),luminance(b)])
            return (b+.05)/(a+.05)
        if min(contrast(self.text,self.background),contrast(self.text,self.panel))<4.5:
            raise ValueError("Text needs at least 4.5:1 contrast against the page and panels.")
        if min(contrast(self.muted,self.background),contrast(self.muted,self.panel))<3:
            raise ValueError("Secondary text needs at least 3:1 contrast against the page and panels.")
        return self

class NavGroup(Strict):
    id: Key
    name: str=Field(max_length=48)
    modules: list[str]=Field(max_length=60)

class PreferencesPatch(Strict):
    revision: int=Field(ge=0)
    theme: Theme | None=None
    navigation: list[NavGroup] | None=Field(default=None,max_length=20)
    layouts: dict[Key,list[Key]] | None=None

    @model_validator(mode="after")
    def validate_layout(self):
        if self.navigation is not None:
            groups=[g.id for g in self.navigation];modules=[m for g in self.navigation for m in g.modules]
            if len(groups)!=len(set(groups)) or len(modules)!=len(set(modules)) or set(modules)-MODULES:
                raise ValueError("Navigation groups and modules must be unique known entries.")
        if self.layouts is not None and (len(self.layouts)>150 or any(len(v)>100 or len(v)!=len(set(v)) for v in self.layouts.values())):
            raise ValueError("Layout lists must be unique and bounded.")
        return self

class ImageInput(Strict):
    revision: int=Field(ge=0)
    image: str | None=Field(default=None,max_length=7_000_000)

def normalized_image(encoded):
    if encoded is None:return None
    try:
        raw=base64.b64decode(encoded,validate=True)
        if len(raw)>5*1024*1024:raise ValueError("Image must be 5 MB or smaller.")
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as source:
                if source.format not in {"PNG","JPEG","WEBP"}:raise ValueError("Choose a PNG, JPEG or WebP image.")
                if source.width*source.height>20_000_000 or min(source.size)<1:raise ValueError("Image exceeds 20 megapixels.")
                source.load()
                picture=ImageOps.exif_transpose(source).convert("RGBA")
                picture.thumbnail((2560,1440))
                out=BytesIO();picture.save(out,format="WEBP",quality=85,method=4)
                return out.getvalue()
    except (ValueError,binascii.Error,UnidentifiedImageError,OSError,Image.DecompressionBombError,Image.DecompressionBombWarning) as exc:
        raise HTTPException(422,"Invalid image. Use a PNG/JPEG/WebP up to 5 MB and 20 megapixels.") from exc

def no_store(response):
    response.headers.update({"Cache-Control":"no-store","X-Content-Type-Options":"nosniff"})

def personal_payload(row):
    return {"revision":row.revision if row else 0,"preferences":row.preferences if row else {},
        "banner":("data:image/webp;base64,"+base64.b64encode(row.banner).decode()) if row and row.banner else None}

def save_personal(db,user,revision,**values):
    row=db.get(UserAppearance,user.id)
    if row is None:
        if revision!=0:raise HTTPException(409,"Appearance changed in another session. Reload before saving.")
        row=UserAppearance(user_id=user.id,preferences={},revision=1,**values) if "preferences" not in values else UserAppearance(user_id=user.id,revision=1,**values)
        db.add(row)
    else:
        result=db.execute(update(UserAppearance).where(UserAppearance.user_id==user.id,UserAppearance.revision==revision)
            .values(**values,revision=revision+1).execution_options(synchronize_session=False))
        if result.rowcount!=1:raise HTTPException(409,"Appearance changed in another session. Reload before saving.")
    try:db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,"Appearance changed in another session. Reload before saving.")
    db.expire_all();return personal_payload(db.get(UserAppearance,user.id))

@router.get("/me")
def mine(response:Response,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    no_store(response);return personal_payload(db.get(UserAppearance,user.id))

@router.patch("/me")
def update_mine(payload:PreferencesPatch,response:Response,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    no_store(response);row=db.get(UserAppearance,user.id);prefs=dict(row.preferences) if row else {}
    for key in payload.model_fields_set-{"revision"}:
        value=payload.model_dump()[key]
        if value is None:prefs.pop(key,None)
        else:prefs[key]=value
    return save_personal(db,user,payload.revision,preferences=prefs)

@router.put("/me/banner")
def my_banner(payload:ImageInput,response:Response,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    no_store(response);return save_personal(db,user,payload.revision,banner=normalized_image(payload.image))

def branding_payload(row):
    revision=row.revision if row else 0
    return {"revision":revision,**{k:f"{get_settings().api_prefix}/appearance/branding/{k}?v={revision}" if row and getattr(row,k) else None for k in ("banner","login_background")}}

@router.get("/branding")
def branding(response:Response,db:Session=Depends(get_db)):
    no_store(response);return branding_payload(db.get(SiteBranding,1))

@router.get("/branding/{slot}")
def branding_image(slot:Literal["banner","login_background"],db:Session=Depends(get_db)):
    row=db.get(SiteBranding,1);content=getattr(row,slot) if row else None
    if not content:raise HTTPException(404,"No custom branding image")
    response=Response(content,media_type="image/webp");no_store(response);return response

@router.put("/branding/{slot}")
def set_branding(slot:Literal["banner","login_background"],payload:ImageInput,response:Response,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if role_rank(user,db)<ROLE_RANK["admin"]:raise HTTPException(403,"Administrator access required for site branding")
    content=normalized_image(payload.image);row=db.get(SiteBranding,1)
    if row is None:
        if payload.revision!=0:raise HTTPException(409,"Site branding changed. Reload before saving.")
        row=SiteBranding(id=1,revision=1,**{slot:content});db.add(row)
    else:
        result=db.execute(update(SiteBranding).where(SiteBranding.id==1,SiteBranding.revision==payload.revision)
            .values(**{slot:content},revision=payload.revision+1).execution_options(synchronize_session=False))
        if result.rowcount!=1:raise HTTPException(409,"Site branding changed. Reload before saving.")
    db.add(AuditEvent(event_kind="site_branding_updated",title=f"Site {slot.replace('_',' ')} updated",body="Custom image uploaded" if content else "Default image restored",actor_user_id=user.id))
    try:db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,"Site branding changed. Reload before saving.")
    db.expire_all();no_store(response);return branding_payload(db.get(SiteBranding,1))
