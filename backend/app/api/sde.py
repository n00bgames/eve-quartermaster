from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user, require_role
from app.core.config import get_settings
from app.db.session import get_db
from app.models import EveAgent, EveSystemObject, EveCategory, EveConstellation, EveDogmaAttribute, EveDogmaEffect, EveGroup, EvePlanetSchematic, EvePlanetSchematicInput, EveRegion, EveStargate, EveStation, EveSystem, EveType, EveTypeDogmaAttribute, EveTypeDogmaEffect, IndustryActivity, IndustryActivityInput, User
from pydantic import BaseModel, ConfigDict, Field
from app.services import sde_maintenance as maintenance

class DownloadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    import_after_download: bool = False

class ImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_path: str | None = Field(default=None,max_length=4096)
    sections: list[str] | None = None


router = APIRouter(prefix="/sde", tags=["sde"])

def require_admin(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    require_role(current_user, "admin", db)
    return current_user


@router.get("/status")
def sde_status(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    return {
        "default_source_path": get_settings().sde_source_path,
        "agents": db.scalar(select(func.count()).select_from(EveAgent)) or 0,
        "celestials": db.scalar(select(func.count()).select_from(EveSystemObject).where(EveSystemObject.kind.in_(["planet", "moon", "belt"]))) or 0,
        "celestial_planets": db.scalar(select(func.count()).select_from(EveSystemObject).where(EveSystemObject.kind == "planet")) or 0,
        "celestial_moons": db.scalar(select(func.count()).select_from(EveSystemObject).where(EveSystemObject.kind == "moon")) or 0,
        "celestial_belts": db.scalar(select(func.count()).select_from(EveSystemObject).where(EveSystemObject.kind == "belt")) or 0,
        "dogma_modifiers": sum(len(value or []) for value in db.scalars(select(EveDogmaEffect.modifier_info))),
        "type_dogma_default_effects": db.scalar(select(func.count()).select_from(EveTypeDogmaEffect).where(EveTypeDogmaEffect.is_default.is_(True))) or 0,
        "blueprint_products": db.scalar(select(func.count()).select_from(IndustryActivity).where(IndustryActivity.product_type_id.is_not(None))) or 0,
        "planet_schematic_outputs": db.scalar(select(func.count()).select_from(EvePlanetSchematic).where(EvePlanetSchematic.output_type_id.is_not(None))) or 0,
        "categories": db.scalar(select(func.count()).select_from(EveCategory)) or 0,
        "groups": db.scalar(select(func.count()).select_from(EveGroup)) or 0,
        "types": db.scalar(select(func.count()).select_from(EveType)) or 0,
        "regions": db.scalar(select(func.count()).select_from(EveRegion)) or 0,
        "constellations": db.scalar(select(func.count()).select_from(EveConstellation)) or 0,
        "systems": db.scalar(select(func.count()).select_from(EveSystem)) or 0,
        "stargates": db.scalar(select(func.count()).select_from(EveStargate)) or 0,
        "stations": db.scalar(select(func.count()).select_from(EveStation)) or 0,
        "dogma_attributes": db.scalar(select(func.count()).select_from(EveDogmaAttribute)) or 0,
        "dogma_effects": db.scalar(select(func.count()).select_from(EveDogmaEffect)) or 0,
        "type_dogma_attributes": db.scalar(select(func.count()).select_from(EveTypeDogmaAttribute)) or 0,
        "type_dogma_effects": db.scalar(select(func.count()).select_from(EveTypeDogmaEffect)) or 0,
        "planet_schematics": db.scalar(select(func.count()).select_from(EvePlanetSchematic)) or 0,
        "planet_schematic_inputs": db.scalar(select(func.count()).select_from(EvePlanetSchematicInput)) or 0,
        "blueprint_activities": db.scalar(select(func.count()).select_from(IndustryActivity)) or 0,
        "activity_inputs": db.scalar(select(func.count()).select_from(IndustryActivityInput)) or 0,
    }


@router.get("/import-status")
def sde_import_status(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    return maintenance.serialize(maintenance.latest(db))


@router.post("/download", status_code=202)
def download_static_data(payload: DownloadRequest, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return maintenance.submit(db,user,"download",import_after_download=payload.import_after_download)


@router.post("/import", status_code=202)
def import_static_data(payload: ImportRequest, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    if payload.sections is not None and payload.sections != ["agents"]:
        raise HTTPException(400,"Supported partial import: sections = ['agents']")
    source_path=(payload.source_path or get_settings().sde_source_path).strip()
    if not source_path:
        raise HTTPException(400,"An SDE source path is required")
    return maintenance.submit(db,user,"import",source_path=source_path,sections=payload.sections)
