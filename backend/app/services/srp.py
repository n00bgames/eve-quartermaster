from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException


SRP_TRANSITIONS = {
    "draft": {"submitted"},
    "submitted": {"under_review", "rejected"},
    "under_review": {"approved", "rejected"},
    "approved": {"paid", "rejected"},
    "rejected": {"submitted"},
    "paid": set(),
}


def normalize_loss_datetime(loss_date: date, loss_time: time, entered_timezone: str = "UTC") -> datetime:
    normalized_time = loss_time.replace(tzinfo=None)
    try:
        source_zone = ZoneInfo(entered_timezone)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=400, detail="Unknown loss timezone") from exc
    return datetime.combine(loss_date, normalized_time, tzinfo=source_zone).astimezone(timezone.utc)


def validate_srp_transition(current: str, target: str, manager: bool) -> None:
    if target not in SRP_TRANSITIONS.get(current, set()):
        raise HTTPException(status_code=400, detail=f"Cannot move SRP from {current} to {target}")
    if current != "draft" and not manager:
        raise HTTPException(status_code=403, detail="An officer or director is required for SRP review decisions")


def money_string(value: Decimal | None) -> str | None:
    return format(value, ".2f") if value is not None else None


def authoritative_loss_value(row: Any) -> Decimal | None:
    """Use immutable review values in descending order of authority; unknown remains null."""
    if row.manual_valuation_override is not None:
        return Decimal(row.manual_valuation_override)
    if row.verified_loss_value is not None:
        return Decimal(row.verified_loss_value)
    if row.killmail_total_loss_value is not None and row.valuation_status == "verified":
        return Decimal(row.killmail_total_loss_value)
    if row.submission_estimated_loss_value is not None:
        return Decimal(row.submission_estimated_loss_value)
    return None


def refresh_authoritative_value(row: Any) -> None:
    row.authoritative_loss_value = authoritative_loss_value(row)


def fitting_snapshot(fitting: Any) -> dict[str, Any]:
    return {
        "fitting_id": fitting.id,
        "name": fitting.name,
        "ship_type_id": fitting.ship_type_id,
        "ship_name": fitting.ship_type.name if fitting.ship_type else None,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "items": [
            {"type_id": item.type_id, "charge_type_id": item.charge_type_id, "flag": item.flag,
             "quantity": item.quantity, "simulation_state": item.simulation_state}
            for item in sorted(fitting.items, key=lambda value: (value.flag, value.id))
        ],
    }


def audit_event(db: Any, row: Any, event_type: str, actor_user_id: int | None, *,
                old_values: dict[str, Any] | None = None, new_values: dict[str, Any] | None = None,
                metadata: dict[str, Any] | None = None, reason: str | None = None) -> None:
    from app.models import SrpRequestEvent
    db.add(SrpRequestEvent(request=row, event_type=event_type, actor_user_id=actor_user_id,
                           old_values=old_values, new_values=new_values, event_metadata=metadata, reason=reason))
