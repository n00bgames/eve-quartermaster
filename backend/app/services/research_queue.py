from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.models import ResearchQueueItem

RESEARCH_QUEUE_ACTIVITY_NAMES = {
    3: "Time Efficiency",
    4: "Material Efficiency",
    5: "Copying",
    8: "Invention",
}
RESEARCH_QUEUE_STATUSES = {"pending", "completed"}


def clean_queue_activity(value: Any, is_copy: bool | None = None) -> int:
    try:
        activity_id = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="A research activity is required") from None
    if activity_id not in RESEARCH_QUEUE_ACTIVITY_NAMES:
        raise HTTPException(status_code=400, detail="Unsupported research activity")
    if is_copy is True and activity_id != 8:
        raise HTTPException(status_code=400, detail="BPC queue entries support invention jobs")
    if is_copy is False and activity_id == 8:
        raise HTTPException(status_code=400, detail="Invention jobs require a BPC")
    return activity_id


def clean_queue_runs(value: Any) -> int:
    try:
        runs = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Runs must be a whole number") from None
    if runs < 1 or runs > 1_000_000:
        raise HTTPException(status_code=400, detail="Runs must be between 1 and 1,000,000")
    return runs


def clean_source_hangar(value: Any) -> str | None:
    text = str(value or "").strip()
    if len(text) > 500:
        raise HTTPException(status_code=400, detail="Source hangar must be 500 characters or fewer")
    return text or None


def clean_queue_status(value: Any) -> str:
    status = str(value or "").strip().lower()
    if status not in RESEARCH_QUEUE_STATUSES:
        raise HTTPException(status_code=400, detail="Queue status must be pending or completed")
    return status


def serialize_queue_item(item: ResearchQueueItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "blueprint_id": item.blueprint_id,
        "blueprint_type_id": item.blueprint_type_id,
        "blueprint_name": item.blueprint_name,
        "blueprint_kind": item.blueprint_kind,
        "owner_name": item.owner_name,
        "material_efficiency": item.material_efficiency,
        "time_efficiency": item.time_efficiency,
        "runs_remaining": item.runs_remaining,
        "source_location_name": item.source_location_name,
        "source_hangar": item.source_hangar,
        "activity_id": item.activity_id,
        "activity_name": RESEARCH_QUEUE_ACTIVITY_NAMES.get(item.activity_id, f"Activity {item.activity_id}"),
        "runs": item.runs,
        "status": item.status,
        "sort_order": item.sort_order,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        "completed_at": item.completed_at.isoformat() if item.completed_at else None,
    }
