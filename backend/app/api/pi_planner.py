from __future__ import annotations

import asyncio
import logging
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.characters import visible_characters
from app.api.planetary_industry import require_planetary_view
from app.db.session import SessionLocal, get_db
from app.models import EveConstellation, EveRegion, EveSystem, PiPlanningJob, PiPlanningScenario, User
from app.schemas.pi_planner import PlanningRequest, RecipeRequest, ScenarioWrite, ScoutRequest, TemplateInspect, TemplateRequest
from app.services.esi_client import EsiClient
from app.services.pi_catalog import PLANET_TYPES
from app.services.pi_market import market_snapshot
from app.services.pi_planner import operation_slots, recipe_report, run_planner
from app.services.pi_planning_context import build_context, restore_snapshot
from app.services.pi_templates import generate_template, inspect_template

router = APIRouter(prefix="/planetary-industry/planner", tags=["planetary-planner"])
logger = logging.getLogger(__name__)
_tasks: set[asyncio.Task] = set()
_cancel: dict[str, threading.Event] = {}
_public_cache: dict[str, tuple[datetime, dict]] = {}
ACTIVE = ("queued", "pricing", "solving")


def now():
    return datetime.now(timezone.utc)


def authorize(user, db, request: PlanningRequest | None = None):
    require_planetary_view(user, db)
    chars = visible_characters(user, db)
    if request and {p.character_id for p in request.pilots} - {c.id for c in chars}:
        raise HTTPException(403, "A scenario character is no longer visible")
    return chars


def owned(model, row_id, user, db):
    require_planetary_view(user, db)
    row = db.scalar(select(model).where(model.id == row_id, model.user_id == user.id))
    if not row:
        raise HTTPException(404, "Planning record not found")
    authorize(user, db, PlanningRequest.model_validate(row.request_json))
    return row


@router.get("/context")
def context(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    value = build_context(db, authorize(user, db))
    return {k: v for k, v in value.items() if k != "pins"}


@router.post("/recipe")
def recipe(body: RecipeRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    value = build_context(db, authorize(user, db))
    targets, inventory = {}, {}
    for row in body.targets:
        targets[row.type_id] = targets.get(row.type_id, 0) + row.quantity
    for row in body.inventory:
        inventory[row.type_id] = inventory.get(row.type_id, 0) + row.quantity
    try:
        return recipe_report(value["catalog"], targets, inventory, set(body.buy_type_ids))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/validate")
def validate_request(body: PlanningRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    authorize(user, db, body)
    return body.model_dump()


def job_payload(row):
    return {"id": row.id, "status": row.status, "progress": row.progress_json, "error": row.error, "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat(), "request": row.request_json, "result": row.result_json}


def update_job(job_id: str, **values) -> bool:
    with SessionLocal() as db:
        row = db.get(PiPlanningJob, job_id)
        if not row:
            return True
        cancelled = row.cancel_requested
        if cancelled and job_id in _cancel:
            _cancel[job_id].set()
        for key, value in values.items():
            setattr(row, key, value)
        row.updated_at = now()
        db.commit()
        return cancelled


async def execute_job(job_id: str, request: PlanningRequest, snapshot_context: dict, replay_market: dict | None = None):
    event = _cancel.setdefault(job_id, threading.Event())
    try:
        if update_job(job_id, status="pricing", progress_json={"stage": "Loading ESI order depth", "fraction": 0}):
            return
        last_update = [0.0]
        def price_progress(done, total):
            if time.monotonic() - last_update[0] > 1 or done == total:
                update_job(job_id, progress_json={"stage": "Loading ESI order depth", "fraction": .5 * done / max(1, total), "loaded": done, "total": total})
                last_update[0] = time.monotonic()
        required = set()
        def dependencies(t):
            if t in required:
                return
            required.add(t)
            item = snapshot_context["catalog"][t]
            if item["recipe"]:
                for material in item["recipe"]["inputs"]:
                    dependencies(material["type_id"])
        for product in request.products:
            dependencies(product.type_id)
        market = replay_market or await market_snapshot(required, request.hub, price_progress, event.is_set)
        if update_job(job_id, status="solving", snapshot_json={"context": snapshot_context, "market": market}, progress_json={"stage": "Comparing production plans", "fraction": .5}):
            return
        def solve_progress(count, fraction):
            if time.monotonic() - last_update[0] > .5:
                update_job(job_id, progress_json={"stage": "Comparing production plans", "fraction": .5 + fraction / 2, "evaluated": count})
                last_update[0] = time.monotonic()
        result = await asyncio.to_thread(run_planner, request, snapshot_context, market, solve_progress, event.is_set)
        result["replayed_snapshot"] = replay_market is not None
        cancelled = update_job(job_id)
        update_job(job_id, status="cancelled" if cancelled or event.is_set() else "complete", result_json=result, progress_json={"stage": "Cancelled; best results retained" if cancelled else "Complete", "fraction": 1})
    except Exception as exc:
        logger.warning("PI planning job %s failed (%s)", job_id, type(exc).__name__)
        update_job(job_id, status="failed", error=str(exc) if isinstance(exc, ValueError) else "The planning job failed. Check ESI availability and retry.")
    finally:
        if event.is_set():
            with SessionLocal() as db:
                row = db.get(PiPlanningJob, job_id)
                if row and row.status in ACTIVE:
                    row.status = "cancelled"
                    row.updated_at = now()
                    db.commit()
        _cancel.pop(job_id, None)


def enqueue(request, user, db, snapshot_context, replay_market=None):
    db.execute(select(User.id).where(User.id == user.id).with_for_update()).first()
    db.execute(update(PiPlanningJob).where(PiPlanningJob.status.in_(ACTIVE), PiPlanningJob.updated_at < now() - timedelta(minutes=5)).values(status="failed", error="Worker stopped before completion. Run the scenario again."))
    active = db.scalar(select(func.count()).select_from(PiPlanningJob).where(PiPlanningJob.user_id == user.id, PiPlanningJob.status.in_(ACTIVE)))
    global_active = db.scalar(select(func.count()).select_from(PiPlanningJob).where(PiPlanningJob.status.in_(ACTIVE)))
    if active >= 2 or global_active >= 8:
        raise HTTPException(429, "Planning queue is full; wait for an active job or cancel it")
    old = db.scalars(select(PiPlanningJob.id).where(PiPlanningJob.user_id == user.id, ~PiPlanningJob.status.in_(ACTIVE)).order_by(PiPlanningJob.created_at.desc()).offset(19)).all()
    if old:
        db.execute(delete(PiPlanningJob).where(PiPlanningJob.id.in_(old)))
    row = PiPlanningJob(id=str(uuid.uuid4()), user_id=user.id, request_json=request.model_dump(), status="queued", progress_json={"stage": "Queued", "fraction": 0}, cancel_requested=False)
    db.add(row)
    db.commit()
    db.refresh(row)
    task = asyncio.create_task(execute_job(row.id, request, snapshot_context, replay_market))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return job_payload(row)


@router.post("/jobs", status_code=202)
async def start_job(body: PlanningRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    chars = authorize(user, db, body)
    selected = {p.character_id for p in body.pilots}
    value = build_context(db, [c for c in chars if c.id in selected])
    try:
        operation_slots(body, value)
        if any(p.type_id not in value["catalog"] or not value["catalog"][p.type_id]["recipe"] for p in body.products):
            raise ValueError("Select produced PI commodities from the current catalog")
        if set(body.buy_type_ids) - set(value["catalog"]):
            raise ValueError("Unknown purchased commodity")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return enqueue(body, user, db, value)


@router.get("/jobs")
def list_jobs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    chars = {c.id for c in authorize(user, db)}
    rows = db.execute(select(PiPlanningJob.id, PiPlanningJob.status, PiPlanningJob.created_at, PiPlanningJob.request_json).where(PiPlanningJob.user_id == user.id).order_by(PiPlanningJob.created_at.desc()).limit(20)).all()
    return [{"id": r.id, "status": r.status, "name": r.request_json["name"], "created_at": r.created_at.isoformat()} for r in rows if {p["character_id"] for p in r.request_json["pilots"]} <= chars]


@router.get("/jobs/{job_id}")
def get_job(job_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = owned(PiPlanningJob, job_id, user, db)
    updated = row.updated_at.replace(tzinfo=timezone.utc) if row.updated_at.tzinfo is None else row.updated_at
    if row.status in ACTIVE and updated < now() - timedelta(minutes=5):
        row.status, row.error = "failed", "Worker stopped before completion. Run the scenario again."
        db.commit()
    return job_payload(row)


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = owned(PiPlanningJob, job_id, user, db)
    if row.status in ACTIVE:
        row.cancel_requested = True
        db.commit()
        if job_id in _cancel:
            _cancel[job_id].set()
    return job_payload(row)


@router.get("/jobs/{job_id}/snapshot")
def export_snapshot(job_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = owned(PiPlanningJob, job_id, user, db)
    return {"schema_version": "eqm.pi-planning-snapshot.v1", "request": row.request_json, "snapshot": row.snapshot_json, "result": row.result_json}


@router.post("/jobs/{job_id}/replay", status_code=202)
async def replay_job(job_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = owned(PiPlanningJob, job_id, user, db)
    if not row.snapshot_json:
        raise HTTPException(409, "This job has no complete input snapshot")
    value, market = restore_snapshot(row.snapshot_json)
    return enqueue(PlanningRequest.model_validate(row.request_json), user, db, value, market)


@router.get("/scenarios")
def list_scenarios(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    chars = {c.id for c in authorize(user, db)}
    rows = db.scalars(select(PiPlanningScenario).where(PiPlanningScenario.user_id == user.id).order_by(PiPlanningScenario.updated_at.desc()).limit(100)).all()
    return [{"id": r.id, "name": r.name, "revision": r.revision, "updated_at": r.updated_at.isoformat(), "request": r.request_json} for r in rows if {p["character_id"] for p in r.request_json["pilots"]} <= chars]


@router.post("/scenarios", status_code=201)
def create_scenario(body: ScenarioWrite, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    authorize(user, db, body.request)
    db.execute(select(User.id).where(User.id == user.id).with_for_update()).first()
    if db.scalar(select(func.count()).select_from(PiPlanningScenario).where(PiPlanningScenario.user_id == user.id)) >= 100:
        raise HTTPException(409, "The 100 saved-scenario limit has been reached")
    row = PiPlanningScenario(id=str(uuid.uuid4()), user_id=user.id, name=body.request.name, revision=1, request_json=body.request.model_dump())
    db.add(row)
    db.commit()
    return {"id": row.id, "revision": row.revision}


@router.put("/scenarios/{scenario_id}")
def save_scenario(scenario_id: str, body: ScenarioWrite, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = owned(PiPlanningScenario, scenario_id, user, db)
    authorize(user, db, body.request)
    result = db.execute(update(PiPlanningScenario).where(PiPlanningScenario.id == row.id, PiPlanningScenario.revision == body.revision).values(request_json=body.request.model_dump(), name=body.request.name, revision=PiPlanningScenario.revision + 1, updated_at=now()))
    if not result.rowcount:
        db.rollback()
        raise HTTPException(409, "This scenario changed in another session. Reload it or save a copy.")
    db.commit()
    return {"id": row.id, "revision": body.revision + 1}


@router.delete("/scenarios/{scenario_id}", status_code=204)
def remove_scenario(scenario_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = owned(PiPlanningScenario, scenario_id, user, db)
    db.delete(row)
    db.commit()


@router.get("/regions")
def regions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_planetary_view(user, db)
    return [{"id": r.region_id, "name": r.name} for r in db.scalars(select(EveRegion).order_by(EveRegion.name)).all()]


@router.get("/systems")
def systems(region_id: int, q: str = "", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_planetary_view(user, db)
    query = select(EveSystem).join(EveConstellation).where(EveConstellation.region_id == region_id)
    if q:
        query = query.where(EveSystem.name.ilike(f"%{q[:80]}%"))
    return [{"id": s.system_id, "name": s.name, "security": s.security_status} for s in db.scalars(query.order_by(EveSystem.name).limit(500)).all()]


async def public_detail(client, path):
    cached = _public_cache.get(path)
    if cached and cached[0] > now():
        return cached[1]
    value = await client.get(path)
    if len(_public_cache) >= 3000:
        _public_cache.pop(next(iter(_public_cache)))
    _public_cache[path] = (now() + timedelta(days=1), value)
    return value


@router.post("/scout")
async def scout(body: ScoutRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    value = build_context(db, authorize(user, db))
    if any(t not in value["catalog"] or value["catalog"][t]["tier"] != 0 for t in body.resource_type_ids):
        raise HTTPException(422, "Scouting requires raw PI resource IDs")
    system_rows = db.scalars(select(EveSystem).where(EveSystem.system_id.in_(set(body.system_ids)))).all()
    if len(system_rows) != len(set(body.system_ids)):
        raise HTTPException(422, "Unknown system in current SDE")
    client, semaphore = EsiClient(), asyncio.Semaphore(4)
    async def one(system):
        async with semaphore:
            try:
                detail = await public_detail(client, f"/universe/systems/{system.system_id}/")
                found = []
                for ref in detail.get("planets", [])[:50]:
                    planet = await public_detail(client, f"/universe/planets/{ref['planet_id']}/")
                    kind = PLANET_TYPES.get(planet["type_id"])
                    if not kind:
                        continue
                    resources = [t for t, item in value["catalog"].items() if kind in item["planet_types"]]
                    found.append({"key": str(ref["planet_id"]), "planet_id": ref["planet_id"], "name": planet["name"], "planet_type": kind, "system_id": system.system_id, "diameter_km": planet["radius"] * 2 / 1000, "security": system.security_status or 0, "customs_percent": 10, "npc_tax_percent": 10, "yields": [], "resource_type_ids": resources})
                covered = set(t for p in found for t in p["resource_type_ids"])
                return {"system_id": system.system_id, "name": system.name, "security": system.security_status, "planets": found, "covered_resources": sorted(covered & set(body.resource_type_ids)), "missing_resources": sorted(set(body.resource_type_ids) - covered), "score": len(covered & set(body.resource_type_ids)) if body.resource_type_ids else len(found)}
            except Exception:
                return {"system_id": system.system_id, "name": system.name, "planets": [], "score": -1, "error": "ESI universe data unavailable"}
    try:
        results = await asyncio.wait_for(asyncio.gather(*(one(s) for s in system_rows)), timeout=120)
    except TimeoutError as exc:
        raise HTTPException(504, "Scouting timed out. Select fewer systems and retry.") from exc
    return {"systems": sorted(results, key=lambda s: (-s["score"], s["name"])), "as_of": now().isoformat(), "note": "Ranked by planet/resource coverage only. ESI exposes no resource-density scan, customs ownership/rate or local competition."}


@router.post("/templates/inspect")
def template_inspect(body: TemplateInspect, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    value = build_context(db, authorize(user, db))
    try:
        return inspect_template(body.text, value["catalog"], value["pins"])
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, str(exc) if isinstance(exc, ValueError) else "Malformed template fields") from exc


@router.post("/templates/generate")
def template_generate(body: TemplateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = owned(PiPlanningJob, body.job_id, user, db)
    if not row.result_json or not row.snapshot_json:
        raise HTTPException(409, "A completed planning result is required")
    try:
        colony = row.result_json["plans"][body.plan_index]["colonies"][body.colony_index]
        value, _ = restore_snapshot(row.snapshot_json)
        return generate_template(colony, value["catalog"], value["pins"])
    except (IndexError, KeyError, ValueError) as exc:
        raise HTTPException(422, "The selected colony has no exportable layout") from exc
