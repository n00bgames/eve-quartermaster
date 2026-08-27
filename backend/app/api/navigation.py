from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.session import SessionLocal, get_db
from app.models import EveStargate, EveStation, EveSystem, User
from app.services.gatecheck import LOCAL_THREAT_JOB_MAX_PILOTS, gatecheck_route, local_threat_analysis, local_threat_names, system_industrial_threat, system_pvp_intel
from app.services.jump_freighter import JUMP_FREIGHTERS, jump_activity_summary, plan_jump_freighter_route, refresh_system_jump_observations
from app.services.navigation import plan_gate_route, resolve_system, search_systems
from app.services.twitch import uedama_scout_status
from app.services.permissions import can_view_section

router = APIRouter(prefix="/navigation", tags=["navigation"])

LOCAL_THREAT_JOB_BATCH_SIZE = 20
LOCAL_THREAT_JOB_TOP_LIMIT = 250
LOCAL_THREAT_JOBS: dict[str, dict[str, Any]] = {}


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def top_local_threat_pilots(pilots: list[dict[str, Any]], limit: int = LOCAL_THREAT_JOB_TOP_LIMIT) -> list[dict[str, Any]]:
    return sorted(
        pilots,
        key=lambda pilot: (int(pilot.get("danger_score") or 0), int(pilot.get("recent_kills") or 0), float(pilot.get("isk_destroyed") or 0)),
        reverse=True,
    )[:limit]


def serialize_local_threat_job(job: dict[str, Any]) -> dict[str, Any]:
    analysis = {
        "generated_at": job.get("updated_at") or job["created_at"],
        "days": job["days"],
        "input_count": job["total_count"],
        "resolved_count": job["resolved_count"],
        "zkill_analyzed_count": job["zkill_analyzed_count"],
        "max_pilots": job["total_count"],
        "zkill_detail_limit": job["total_count"],
        "errors": list(dict.fromkeys(job["errors"])),
        "pilots": top_local_threat_pilots(job["pilots"]),
    }
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "created_at": job["created_at"],
        "updated_at": job.get("updated_at"),
        "completed_at": job.get("completed_at"),
        "total_count": job["total_count"],
        "processed_count": job["processed_count"],
        "batch": job["batch"],
        "total_batches": job["total_batches"],
        "visible_limit": LOCAL_THREAT_JOB_TOP_LIMIT,
        "analysis": analysis,
    }


async def run_local_threat_job(job_id: str, names: list[str], days: int) -> None:
    job = LOCAL_THREAT_JOBS[job_id]
    if job.get("cancel_requested"):
        job["status"] = "cancelled"
        job["completed_at"] = utc_iso()
        job["updated_at"] = job["completed_at"]
        return
    job["status"] = "running"
    try:
        for start in range(0, len(names), LOCAL_THREAT_JOB_BATCH_SIZE):
            if job.get("cancel_requested"):
                job["status"] = "cancelled"
                job["completed_at"] = utc_iso()
                job["updated_at"] = job["completed_at"]
                return
            batch = names[start:start + LOCAL_THREAT_JOB_BATCH_SIZE]
            job["batch"] = (start // LOCAL_THREAT_JOB_BATCH_SIZE) + 1
            with SessionLocal() as db:
                result = await local_threat_analysis(db, batch, days=days)
            job["processed_count"] += result["input_count"]
            job["resolved_count"] += result["resolved_count"]
            job["zkill_analyzed_count"] += result["zkill_analyzed_count"]
            job["errors"] = list(dict.fromkeys([*job["errors"], *result.get("errors", [])]))
            job["pilots"].extend(result.get("pilots", []))
            job["updated_at"] = utc_iso()
            if job.get("cancel_requested"):
                job["status"] = "cancelled"
                job["completed_at"] = utc_iso()
                job["updated_at"] = job["completed_at"]
                return
            if start + LOCAL_THREAT_JOB_BATCH_SIZE < len(names):
                await asyncio.sleep(0.4)
        job["status"] = "complete"
        job["completed_at"] = utc_iso()
        job["updated_at"] = job["completed_at"]
    except Exception as exc:
        if job.get("cancel_requested"):
            job["status"] = "cancelled"
        else:
            job["status"] = "failed"
            job["errors"] = list(dict.fromkeys([*job["errors"], str(exc)]))
        job["completed_at"] = utc_iso()
        job["updated_at"] = job["completed_at"]

def require_navigation(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if not can_view_section(current_user, "navigation", db):
        raise HTTPException(status_code=403, detail="navigation permission is required")
    return current_user


@router.get("/status")
def navigation_status(_: User = Depends(require_navigation), db: Session = Depends(get_db)) -> dict[str, Any]:
    return {
        "systems": db.scalar(select(func.count()).select_from(EveSystem)) or 0,
        "stargates": db.scalar(select(func.count()).select_from(EveStargate)) or 0,
        "stations": db.scalar(select(func.count()).select_from(EveStation)) or 0,
    }


@router.get("/systems")
def systems(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=50),
    _: User = Depends(require_navigation),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    return search_systems(db, q, limit)


def resolve_avoid_system_ids(db: Session, avoid_systems: str) -> set[int]:
    resolved: set[int] = set()
    for system_name in (part.strip() for part in avoid_systems.split(',')):
        if not system_name:
            continue
        resolved.add(resolve_system(db, system_name).system_id)
    return resolved


def attach_last_hour_jump_activity(db: Session, payload: dict[str, Any], systems: list[dict[str, Any]]) -> dict[str, Any]:
    system_ids = [int(system["system_id"]) for system in systems if system.get("system_id")]
    cache = refresh_system_jump_observations(db, system_ids)
    for system in systems:
        system_id = system.get("system_id")
        if system_id:
            system["jump_activity"] = jump_activity_summary(db, int(system_id), 1)
    payload["jump_activity"] = {"hours": 1, "cache": cache}
    return payload


@router.get("/route")
def route(
    origin: str = Query(..., min_length=1),
    destination: str = Query(..., min_length=1),
    highsec_only: bool = False,
    prefer_safer: bool = True,
    avoid_systems: str = Query(""),
    context_gate_hops: int = Query(1, ge=0, le=2),
    _: User = Depends(require_navigation),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        result = plan_gate_route(
            db,
            origin,
            destination,
            highsec_only=highsec_only,
            prefer_safer=prefer_safer,
            avoid_system_ids=resolve_avoid_system_ids(db, avoid_systems),
            context_gate_hops=context_gate_hops,
        )
        return attach_last_hour_jump_activity(db, result, result.get("systems", []))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.get("/gatecheck")
async def gatecheck(
    origin: str = Query(..., min_length=1),
    destination: str = Query(..., min_length=1),
    highsec_only: bool = False,
    prefer_safer: bool = True,
    avoid_systems: str = Query(""),
    hours: int = Query(1, ge=1, le=168),
    industrial_only: bool = True,
    _: User = Depends(require_navigation),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        result = await gatecheck_route(
            db,
            origin,
            destination,
            highsec_only=highsec_only,
            prefer_safer=prefer_safer,
            avoid_system_ids=resolve_avoid_system_ids(db, avoid_systems),
            hours=hours,
            industrial_only=industrial_only,
        )
        return attach_last_hour_jump_activity(db, result, result.get("systems", []))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.get("/industrial-threat")
async def industrial_threat(
    system: str = Query(..., min_length=1),
    refresh_hours: int = Query(24, ge=1, le=168),
    days: int = Query(90, ge=1, le=90),
    force_refresh: bool = False,
    _: User = Depends(require_navigation),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return await system_industrial_threat(db, system, refresh_hours=refresh_hours, days=days, force_refresh=force_refresh)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc



@router.get("/pvp-intel")
async def pvp_intel(
    system: str = Query(..., min_length=1),
    refresh_hours: int = Query(24, ge=1, le=168),
    days: int = Query(90, ge=1, le=90),
    force_refresh: bool = False,
    _: User = Depends(require_navigation),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        result = await system_pvp_intel(db, system, refresh_hours=refresh_hours, days=days, force_refresh=force_refresh)
        attach_last_hour_jump_activity(db, result, [result["system"]])
        result["system_jump_activity"] = result["system"].pop("jump_activity")
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/local-threat")
async def local_threat(
    payload: dict[str, Any] = Body(...),
    days: int = Query(30, ge=1, le=90),
    _: User = Depends(require_navigation),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    names = payload.get("names") or payload.get("local") or payload.get("text") or ""
    try:
        return await local_threat_analysis(db, names, days=days)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/local-threat/jobs")
async def start_local_threat_job(
    payload: dict[str, Any] = Body(...),
    days: int = Query(30, ge=1, le=90),
    _: User = Depends(require_navigation),
) -> dict[str, Any]:
    raw_names = payload.get("names") or payload.get("local") or payload.get("text") or ""
    names = local_threat_names(raw_names, max_pilots=LOCAL_THREAT_JOB_MAX_PILOTS)
    if not names:
        raise HTTPException(status_code=400, detail="Paste at least one valid pilot name.")
    job_id = uuid.uuid4().hex
    created_at = utc_iso()
    LOCAL_THREAT_JOBS[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "created_at": created_at,
        "updated_at": created_at,
        "completed_at": None,
        "days": days,
        "total_count": len(names),
        "processed_count": 0,
        "resolved_count": 0,
        "zkill_analyzed_count": 0,
        "batch": 0,
        "total_batches": (len(names) + LOCAL_THREAT_JOB_BATCH_SIZE - 1) // LOCAL_THREAT_JOB_BATCH_SIZE,
        "errors": [],
        "pilots": [],
        "cancel_requested": False,
    }
    asyncio.create_task(run_local_threat_job(job_id, names, days))
    return serialize_local_threat_job(LOCAL_THREAT_JOBS[job_id])


@router.get("/local-threat/jobs/{job_id}")
def get_local_threat_job(
    job_id: str,
    _: User = Depends(require_navigation),
) -> dict[str, Any]:
    job = LOCAL_THREAT_JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Local threat job was not found. It may have been cleared by a backend restart.")
    return serialize_local_threat_job(job)


@router.post("/local-threat/jobs/{job_id}/cancel")
def cancel_local_threat_job(
    job_id: str,
    _: User = Depends(require_navigation),
) -> dict[str, Any]:
    job = LOCAL_THREAT_JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Local threat job was not found. It may have been cleared by a backend restart.")
    if job["status"] not in {"complete", "failed", "cancelled"}:
        job["cancel_requested"] = True
        job["status"] = "cancelling"
        job["updated_at"] = utc_iso()
    return serialize_local_threat_job(job)

@router.get("/uedama-scout")
async def uedama_scout(_: User = Depends(require_navigation)) -> dict[str, Any]:
    return await uedama_scout_status()
@router.get("/jump-freighter/ships")
def jump_freighter_ships(_: User = Depends(require_navigation)) -> list[dict[str, Any]]:
    return [
        {
            "key": key,
            "name": ship.name,
            "type_id": ship.type_id,
            "fuel_type_id": ship.fuel_type_id,
            "fuel_type_name": ship.fuel_type_name,
            "base_fuel_per_light_year": ship.fuel_per_light_year,
            "base_range_ly": ship.base_range_ly,
            "ship_class": ship.ship_class,
        }
        for key, ship in JUMP_FREIGHTERS.items()
    ]


@router.get("/jump-freighter/route")
async def jump_freighter_route(
    origin: str = Query(..., min_length=1),
    destination: str = Query(..., min_length=1),
    ship: str = Query("Rhea", min_length=1),
    jump_drive_calibration: int = Query(5, ge=0, le=5),
    jump_fuel_conservation: int = Query(5, ge=0, le=5),
    context_gate_hops: int = Query(1, ge=0, le=2),
    station_safety: str = Query("any", pattern="^(any|avoid_red_only|green)$"),
    kill_filter: str = Query("industrial", pattern="^(industrial|all)$"),
    jump_activity_hours: int = Query(6, ge=1, le=24),
    avoid_systems: str = Query(""),
    waypoints: str = Query(""),
    _: User = Depends(require_navigation),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return plan_jump_freighter_route(
            db,
            origin,
            destination,
            ship_name=ship,
            jump_drive_calibration=jump_drive_calibration,
            jump_fuel_conservation=jump_fuel_conservation,
            context_gate_hops=context_gate_hops,
            station_safety=station_safety,
            kill_filter=kill_filter,
            jump_activity_hours=jump_activity_hours,
            avoid_system_queries=[system.strip() for system in avoid_systems.split(",") if system.strip()],
            waypoint_queries=[system.strip() for system in waypoints.split(",") if system.strip()],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc











