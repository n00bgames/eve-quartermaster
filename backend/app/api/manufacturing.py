from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import EveType, ManufacturingJob, ManufacturingJobItem, User
from app.services.market import DEFAULT_HUB_KEYS, appraise_market
from app.services.permissions import can_view_section

router = APIRouter(prefix="/manufacturing", tags=["manufacturing"])

MANUFACTURING_CATEGORIES = [
    {"key": "blueprint", "label": "BPC/BPO"},
    {"key": "decryptor", "label": "Decryptors"},
    {"key": "datacore", "label": "Datacores"},
    {"key": "component", "label": "Components"},
    {"key": "mineral", "label": "Minerals"},
    {"key": "pi", "label": "PI Materials"},
    {"key": "ship", "label": "Ships Required"},
    {"key": "item", "label": "Items Required"},
    {"key": "reaction", "label": "Reaction Materials"},
    {"key": "fee", "label": "Fees"},
    {"key": "other", "label": "Other"},
]
CATEGORY_KEYS = {row["key"] for row in MANUFACTURING_CATEGORIES}
JOB_STATUSES = {"draft", "running", "completed"}
OUTPUT_DISPOSITIONS = {"pending", "sold", "kept"}
ACTIVITY_FLAGS = {"manufacturing", "me", "te", "invention", "copy", "reaction"}


def require_manufacturing(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if not can_view_section(current_user, "manufacturing", db):
        raise HTTPException(status_code=403, detail="manufacturing section access is required")
    return current_user


def as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)



def clean_status(value: Any) -> str:
    status = str(value or "draft").strip().lower()
    if status not in JOB_STATUSES:
        raise HTTPException(status_code=400, detail="status must be draft, running, or completed")
    return status


def clean_disposition(value: Any) -> str:
    disposition = str(value or "pending").strip().lower()
    if disposition not in OUTPUT_DISPOSITIONS:
        raise HTTPException(status_code=400, detail="output_disposition must be pending, sold, or kept")
    return disposition



def as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def clean_activity_flags(value: Any) -> str:
    raw_flags = value if isinstance(value, list) else str(value or "manufacturing").split(",")
    flags = []
    for raw in raw_flags:
        flag = str(raw).strip().lower()
        if flag and flag not in flags:
            flags.append(flag)
    invalid = [flag for flag in flags if flag not in ACTIVITY_FLAGS]
    if invalid:
        raise HTTPException(status_code=400, detail="activity_flags contains an unsupported activity")
    return ",".join(flags or ["manufacturing"])


def split_activity_flags(value: str | None) -> list[str]:
    flags = [flag for flag in str(value or "manufacturing").split(",") if flag]
    return flags or ["manufacturing"]

def parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="date_started must use YYYY-MM-DD") from exc


def parse_time(value: Any) -> time | None:
    if not value:
        return None
    if isinstance(value, time):
        return value
    try:
        return time.fromisoformat(str(value))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="time_started must use HH:MM or HH:MM:SS") from exc


def resolve_type(db: Session, name: str, type_id: int | None = None) -> EveType | None:
    if type_id:
        return db.get(EveType, int(type_id))
    clean = " ".join(name.strip().split())
    if not clean:
        return None
    item = db.scalar(select(EveType).where(EveType.name.ilike(clean)).limit(1))
    if item is None:
        item = db.scalar(select(EveType).where(EveType.name.ilike(f"%{clean}%")).limit(1))
    return item


def serialize_item(row: ManufacturingJobItem) -> dict[str, Any]:
    return {
        "id": row.id,
        "category": row.category,
        "item_type_id": row.item_type_id,
        "item_name": row.item_name,
        "type_name": row.item_type.name if row.item_type else row.item_name,
        "quantity": as_float(row.quantity) or 0,
        "unit_price": as_float(row.unit_price),
        "price_paid": as_float(row.price_paid),
        "notes": row.notes,
    }


def serialize_job(job: ManufacturingJob) -> dict[str, Any]:
    items = [serialize_item(item) for item in job.items]
    run_cost = as_float(job.cost_to_run) or 0
    entered_total = sum((item["quantity"] or 0) * (item["unit_price"] or 0) for item in items) + run_cost
    paid_total = sum((item["quantity"] or 0) * (item["price_paid"] or 0) for item in items) + run_cost
    category_totals: dict[str, float] = {}
    category_paid_totals: dict[str, float] = {}
    for item in items:
        category_totals[item["category"]] = category_totals.get(item["category"], 0) + (item["quantity"] or 0) * (item["unit_price"] or 0)
        category_paid_totals[item["category"]] = category_paid_totals.get(item["category"], 0) + (item["quantity"] or 0) * (item["price_paid"] or 0)
    return {
        "id": job.id,
        "name": job.name,
        "output_type_id": job.output_type_id,
        "output_type_name": job.output_type.name if job.output_type else None,
        "output_quantity": job.output_quantity,
        "activity_flags": split_activity_flags(job.activity_flags),
        "research_runs": job.research_runs,
        "me_start": job.me_start,
        "me_target": job.me_target,
        "te_start": job.te_start,
        "te_target": job.te_target,
        "copy_runs": job.copy_runs,
        "invention_runs": job.invention_runs,
        "invention_successes": job.invention_successes,
        "status": job.status,
        "output_disposition": job.output_disposition,
        "output_sale_price": as_float(job.output_sale_price),
        "output_sale_notes": job.output_sale_notes,
        "cost_to_run": as_float(job.cost_to_run),
        "time_to_run": job.time_to_run,
        "date_started": job.date_started.isoformat() if job.date_started else None,
        "time_started": job.time_started.isoformat(timespec="minutes") if job.time_started else None,
        "notes": job.notes,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "items": items,
        "entered_total": entered_total,
        "paid_total": paid_total,
        "savings_total": entered_total - paid_total,
        "category_totals": category_totals,
        "category_paid_totals": category_paid_totals,
    }


def job_query():
    return select(ManufacturingJob).options(
        selectinload(ManufacturingJob.output_type),
        selectinload(ManufacturingJob.items).selectinload(ManufacturingJobItem.item_type),
    )


@router.get("/categories")
def manufacturing_categories(_: User = Depends(require_manufacturing)) -> dict[str, Any]:
    return {"categories": MANUFACTURING_CATEGORIES}


@router.get("/jobs")
def list_manufacturing_jobs(_: User = Depends(require_manufacturing), db: Session = Depends(get_db)) -> dict[str, Any]:
    jobs = db.scalars(job_query().order_by(ManufacturingJob.created_at.desc(), ManufacturingJob.id.desc()).limit(100)).all()
    return {"categories": MANUFACTURING_CATEGORIES, "jobs": [serialize_job(job) for job in jobs]}


@router.post("/jobs")
def create_manufacturing_job(payload: dict[str, Any], current_user: User = Depends(require_manufacturing), db: Session = Depends(get_db)) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Build name is required.")
    raw_items = payload.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise HTTPException(status_code=400, detail="Add at least one manufacturing line item.")

    output_type = resolve_type(db, str(payload.get("output_type_name") or name), payload.get("output_type_id"))
    job = ManufacturingJob(
        name=name,
        output_type_id=output_type.type_id if output_type else None,
        output_quantity=max(1, int(payload.get("output_quantity") or 1)),
        activity_flags=clean_activity_flags(payload.get("activity_flags")),
        research_runs=as_int(payload.get("research_runs")),
        me_start=as_int(payload.get("me_start")),
        me_target=as_int(payload.get("me_target")),
        te_start=as_int(payload.get("te_start")),
        te_target=as_int(payload.get("te_target")),
        copy_runs=as_int(payload.get("copy_runs")),
        invention_runs=as_int(payload.get("invention_runs")),
        invention_successes=as_int(payload.get("invention_successes")),
        output_disposition=clean_disposition(payload.get("output_disposition")),
        output_sale_price=as_float(payload.get("output_sale_price")),
        output_sale_notes=str(payload.get("output_sale_notes") or "").strip() or None,
        status=clean_status(payload.get("status")),
        cost_to_run=as_float(payload.get("cost_to_run")),
        time_to_run=str(payload.get("time_to_run") or "").strip() or None,
        date_started=parse_date(payload.get("date_started")),
        time_started=parse_time(payload.get("time_started")),
        notes=str(payload.get("notes") or "").strip() or None,
        created_by_user_id=current_user.id,
    )
    db.add(job)

    for raw in raw_items[:250]:
        if not isinstance(raw, dict):
            continue
        category = str(raw.get("category") or "other")
        if category not in CATEGORY_KEYS:
            category = "other"
        item_name = str(raw.get("item_name") or raw.get("type_name") or "").strip()
        if not item_name:
            continue
        quantity = as_float(raw.get("quantity")) or 0
        if quantity <= 0:
            continue
        item_type = resolve_type(db, item_name, raw.get("item_type_id"))
        db.add(ManufacturingJobItem(
            job=job,
            category=category,
            item_type_id=item_type.type_id if item_type else None,
            item_name=item_type.name if item_type else item_name,
            quantity=quantity,
            unit_price=as_float(raw.get("unit_price")),
            price_paid=as_float(raw.get("price_paid")),
            notes=str(raw.get("notes") or "").strip() or None,
        ))

    if not job.items:
        raise HTTPException(status_code=400, detail="Add at least one valid manufacturing line item.")
    db.commit()
    job = db.scalar(job_query().where(ManufacturingJob.id == job.id))
    return serialize_job(job)



@router.patch("/jobs/{job_id}")
def update_manufacturing_job(job_id: int, payload: dict[str, Any], _: User = Depends(require_manufacturing), db: Session = Depends(get_db)) -> dict[str, Any]:
    job = db.scalar(job_query().where(ManufacturingJob.id == job_id))
    if job is None:
        raise HTTPException(status_code=404, detail="Manufacturing job not found.")
    if "status" in payload:
        job.status = clean_status(payload.get("status"))
    if "activity_flags" in payload:
        job.activity_flags = clean_activity_flags(payload.get("activity_flags"))
    for field in ["research_runs", "me_start", "me_target", "te_start", "te_target", "copy_runs", "invention_runs", "invention_successes"]:
        if field in payload:
            setattr(job, field, as_int(payload.get(field)))
    if "output_disposition" in payload:
        job.output_disposition = clean_disposition(payload.get("output_disposition"))
    if "output_sale_price" in payload:
        job.output_sale_price = as_float(payload.get("output_sale_price"))
    if "output_sale_notes" in payload:
        job.output_sale_notes = str(payload.get("output_sale_notes") or "").strip() or None
    db.commit()
    job = db.scalar(job_query().where(ManufacturingJob.id == job_id))
    return serialize_job(job)

@router.delete("/jobs/{job_id}")
def delete_manufacturing_job(job_id: int, _: User = Depends(require_manufacturing), db: Session = Depends(get_db)) -> dict[str, Any]:
    job = db.get(ManufacturingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Manufacturing job not found.")
    db.delete(job)
    db.commit()
    return {"status": "deleted", "id": job_id}


@router.post("/appraise")
async def appraise_manufacturing_items(payload: dict[str, Any], _: User = Depends(require_manufacturing), db: Session = Depends(get_db)) -> dict[str, Any]:
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raw_items = []
    lines: list[str] = []
    for raw in raw_items[:250]:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("item_name") or raw.get("type_name") or "").strip()
        quantity = as_float(raw.get("quantity")) or 0
        if name and quantity > 0:
            lines.append(f"{int(quantity) if quantity.is_integer() else quantity} {name}")
    if not lines:
        raise HTTPException(status_code=400, detail="Add at least one item to price.")
    hubs = payload.get("hub_keys")
    hub_keys = [str(key) for key in hubs] if isinstance(hubs, list) and hubs else DEFAULT_HUB_KEYS
    return await appraise_market(db, "\n".join(lines), hub_keys)

