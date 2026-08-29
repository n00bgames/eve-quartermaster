from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SrpRequest, SrpRequestEvent
from app.services.srp import money_string
from app.services.srp_analytics_engine import evaluate_srp_analytics_with_engine

METRIC_VERSION = "srp.analytics.v1"
EXCLUDED_DISPOSITIONS = {"duplicate", "invalid", "test", "cancelled"}
BREAKDOWN_FIELDS = {
    "doctrines": ("doctrine_id", "doctrine_name_snapshot"),
    "fits": ("fitting_id", "fitting_name_snapshot"),
    "ship_types": ("ship_type_id", "ship_name_snapshot"),
    "ship_groups": ("ship_group_id", "ship_group_name_snapshot"),
    "characters": ("character_id", "character_name_snapshot"),
    "operations": ("operation_id", "operation_name_snapshot"),
    "corporations": ("corporation_id", "corporation_name_snapshot"),
    "alliances": ("alliance_id", "alliance_name_snapshot"),
    "systems": ("system_id", "system_name_snapshot"),
    "regions": ("region_id", "region_name_snapshot"),
    "statuses": ("status", "status"),
    "security_classes": ("security_class", "security_class"),
}


def _utc_boundary(value: date, reporting_timezone: str, *, next_day: bool = False) -> datetime:
    try:
        zone = ZoneInfo(reporting_timezone)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=400, detail="Unknown reporting timezone") from exc
    target = value + timedelta(days=1) if next_day else value
    return datetime.combine(target, time.min, zone).astimezone(timezone.utc)


def filtered_rows(db: Session, *, user_id: int, manager: bool, date_from: date | None = None,
                  date_to: date | None = None, reporting_timezone: str = "UTC",
                  doctrine_id: int | None = None, doctrine_priority: str | None = None,
                  fitting_id: int | None = None, ship_type_id: int | None = None,
                  ship_group_id: int | None = None, character_id: int | None = None,
                  corporation_id: int | None = None, alliance_id: int | None = None,
                  operation_id: int | None = None, system_id: int | None = None,
                  region_id: int | None = None, security_class: str | None = None,
                  status: str | None = None, valuation_status: str | None = None,
                  data_source: str | None = None, include_excluded: bool = False) -> list[SrpRequest]:
    statement = select(SrpRequest).where(SrpRequest.archived_at.is_(None), SrpRequest.status != "draft")
    if not manager:
        statement = statement.where(SrpRequest.requesting_user_id == user_id)
    if not include_excluded:
        statement = statement.where(SrpRequest.record_disposition == "operational")
    if date_from:
        statement = statement.where(SrpRequest.loss_occurred_at >= _utc_boundary(date_from, reporting_timezone))
    if date_to:
        statement = statement.where(SrpRequest.loss_occurred_at < _utc_boundary(date_to, reporting_timezone, next_day=True))
    filters = {
        SrpRequest.doctrine_id: doctrine_id, SrpRequest.doctrine_priority_code_snapshot: doctrine_priority,
        SrpRequest.fitting_id: fitting_id, SrpRequest.ship_type_id: ship_type_id,
        SrpRequest.ship_group_id: ship_group_id, SrpRequest.character_id: character_id,
        SrpRequest.corporation_id: corporation_id, SrpRequest.alliance_id: alliance_id,
        SrpRequest.operation_id: operation_id, SrpRequest.system_id: system_id,
        SrpRequest.region_id: region_id, SrpRequest.security_class: security_class,
        SrpRequest.status: status, SrpRequest.valuation_status: valuation_status,
        SrpRequest.data_source: data_source,
    }
    for column, value in filters.items():
        if value is not None and value != "":
            statement = statement.where(column == value)
    return list(db.scalars(statement.order_by(SrpRequest.loss_occurred_at)).all())


def _bucket_key(value: datetime, granularity: str, zone: ZoneInfo) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    local = value.astimezone(zone)
    if granularity == "month": return local.strftime("%Y-%m")
    if granularity == "week":
        start = local.date() - timedelta(days=local.weekday())
        return start.isoformat()
    return local.date().isoformat()


def _money_cents(value: Any) -> int | None:
    if value is None:
        return None
    return int((Decimal(value) * 100).quantize(Decimal("1")))


def _average_cents(total: int, count: int) -> int | None:
    return int((Decimal(total) / Decimal(count)).quantize(Decimal("1"))) if count else None


def _python_srp_reduction(payload: dict[str, Any]) -> dict[str, Any]:
    rows = payload["rows"]
    total = sum((row["authoritative_loss_cents"] or 0 for row in rows), 0)
    valued_count = sum(row["authoritative_loss_cents"] is not None for row in rows)
    requested = sum((row["requested_cents"] or 0 for row in rows), 0)
    approved = sum((row["approved_cents"] or 0 for row in rows), 0)
    paid = sum((row["paid_cents"] or 0 for row in rows), 0)
    rejected = sum((row["requested_cents"] or 0 for row in rows if row["status"] == "rejected"), 0)
    buckets: dict[str, dict[str, Any]] = {}
    groups: dict[str, dict[tuple[str, str], dict[str, Any]]] = {key: {} for key in BREAKDOWN_FIELDS}
    for row in rows:
        bucket = buckets.setdefault(row["bucket"], {"bucket": row["bucket"], "loss_count": 0, "valued_count": 0, "total_isk_cents": 0, "request_ids": []})
        bucket["loss_count"] += 1
        bucket["request_ids"].append(row["request_id"])
        if row["authoritative_loss_cents"] is not None:
            bucket["valued_count"] += 1
            bucket["total_isk_cents"] += row["authoritative_loss_cents"]
        for section, dimension in row["dimensions"].items():
            key = (repr(dimension["id"]), dimension["label"])
            group = groups[section].setdefault(key, {"id": dimension["id"], "label": dimension["label"], "loss_count": 0, "valued_count": 0, "total_isk_cents": 0, "average_isk_cents": None, "request_ids": []})
            group["loss_count"] += 1
            group["request_ids"].append(row["request_id"])
            if row["authoritative_loss_cents"] is not None:
                group["valued_count"] += 1
                group["total_isk_cents"] += row["authoritative_loss_cents"]
    breakdowns: dict[str, list[dict[str, Any]]] = {}
    for section, section_groups in groups.items():
        output = list(section_groups.values())
        for group in output:
            group["average_isk_cents"] = _average_cents(group["total_isk_cents"], group["valued_count"])
        breakdowns[section] = sorted(output, key=lambda item: (-item["total_isk_cents"], -item["loss_count"], item["label"]))
    doctrines = breakdowns["doctrines"]
    ship_types = breakdowns["ship_types"]
    loss_count = len(rows)
    unvalued = loss_count - valued_count
    return {
        "schema_version": "eqm.srp-analytics-output.v1",
        "summary": {
            "loss_count": loss_count, "valued_loss_count": valued_count, "total_isk_lost_cents": total,
            "average_isk_per_loss_cents": _average_cents(total, loss_count),
            "average_isk_per_calendar_day_cents": _average_cents(total, payload["calendar_days"]),
            "average_isk_per_active_loss_day_cents": _average_cents(total, payload["active_loss_days"]),
            "calendar_days": payload["calendar_days"], "active_loss_days": payload["active_loss_days"],
            "requested_reimbursement_cents": requested, "approved_reimbursement_cents": approved,
            "rejected_reimbursement_cents": rejected, "paid_reimbursement_cents": paid,
            "loss_less_approved_cents": total - approved, "loss_less_paid_cents": total - paid,
        },
        "time_series": [buckets[key] for key in sorted(buckets)],
        "granularity": payload["granularity"],
        "breakdowns": breakdowns,
        "top": {
            "doctrines_by_isk": doctrines[:10],
            "doctrines_by_losses": sorted(doctrines, key=lambda item: (-item["loss_count"], item["label"]))[:10],
            "ships_by_losses": sorted(ship_types, key=lambda item: (-item["loss_count"], item["label"]))[:10],
        },
        "quality": {
            "unvalued_count": unvalued,
            "unvalued_percentage_units": int((Decimal(unvalued * 10_000) / Decimal(loss_count)).quantize(Decimal("1"))) if loss_count else 0,
            "missing_doctrine_count": sum(row["dimensions"]["doctrines"]["id"] is None for row in rows),
            "missing_ship_type_count": sum(row["dimensions"]["ship_types"]["id"] is None for row in rows),
            "manual_count": sum(row["data_source"] == "manual" for row in rows),
            "imported_count": sum(row["data_source"] != "manual" for row in rows),
        },
    }


def _money_from_cents(value: int | None) -> str | None:
    return money_string(Decimal(value) / 100) if value is not None else None


def _breakdown_from_contract(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"], "label": row["label"], "loss_count": row["loss_count"], "valued_count": row["valued_count"],
        "total_isk": _money_from_cents(row["total_isk_cents"]), "average_isk": _money_from_cents(row["average_isk_cents"]),
        "request_ids": row["request_ids"],
    }


def build_analytics(db: Session, rows: list[SrpRequest], *, date_from: date | None, date_to: date | None,
                    reporting_timezone: str, applied_filters: dict[str, Any], user_id: int, manager: bool) -> dict[str, Any]:
    try: zone = ZoneInfo(reporting_timezone)
    except ZoneInfoNotFoundError as exc: raise HTTPException(status_code=400, detail="Unknown reporting timezone") from exc
    if date_from and date_to:
        calendar_days = max((date_to - date_from).days + 1, 1)
    elif rows:
        local_dates = [(row.loss_occurred_at if row.loss_occurred_at.tzinfo else row.loss_occurred_at.replace(tzinfo=timezone.utc)).astimezone(zone).date() for row in rows]
        calendar_days = (max(local_dates) - min(local_dates)).days + 1
    else:
        calendar_days = 0
    active_days = len({(row.loss_occurred_at if row.loss_occurred_at.tzinfo else row.loss_occurred_at.replace(tzinfo=timezone.utc)).astimezone(zone).date() for row in rows})
    granularity = "day" if calendar_days <= 45 else "week" if calendar_days <= 180 else "month"
    normalized_rows = [{
        "request_id": row.id,
        "bucket": _bucket_key(row.loss_occurred_at, granularity, zone),
        "authoritative_loss_cents": _money_cents(row.authoritative_loss_value),
        "requested_cents": _money_cents(row.requested_reimbursement_amount),
        "approved_cents": _money_cents(row.approved_reimbursement_amount),
        "paid_cents": _money_cents(row.paid_reimbursement_amount),
        "status": row.status,
        "data_source": row.data_source,
        "dimensions": {
            section: {"id": getattr(row, id_field), "label": getattr(row, label_field) or "Unknown"}
            for section, (id_field, label_field) in BREAKDOWN_FIELDS.items()
        },
    } for row in rows]
    engine_payload = {
        "schema_version": "eqm.srp-analytics-input.v1",
        "calendar_days": calendar_days,
        "active_loss_days": active_days,
        "granularity": granularity,
        "rows": normalized_rows,
    }
    reduction = evaluate_srp_analytics_with_engine(
        payload=engine_payload,
        python_result=lambda: _python_srp_reduction(engine_payload),
    )
    all_visible_statement = select(SrpRequest).where(SrpRequest.archived_at.is_(None), SrpRequest.status != "draft", SrpRequest.record_disposition.in_(EXCLUDED_DISPOSITIONS))
    if not manager: all_visible_statement = all_visible_statement.where(SrpRequest.requesting_user_id == user_id)
    if date_from: all_visible_statement = all_visible_statement.where(SrpRequest.loss_occurred_at >= _utc_boundary(date_from, reporting_timezone))
    if date_to: all_visible_statement = all_visible_statement.where(SrpRequest.loss_occurred_at < _utc_boundary(date_to, reporting_timezone, next_day=True))
    excluded_count = len(db.scalars(all_visible_statement).all())
    event_statement = select(SrpRequestEvent.event_type, SrpRequestEvent.occurred_at).join(SrpRequest).where(SrpRequest.id.in_([row.id for row in rows])) if rows else None
    workflow_counts: dict[str, int] = defaultdict(int)
    if event_statement is not None:
        for event_type, _ in db.execute(event_statement): workflow_counts[event_type] += 1
    core_summary = reduction["summary"]
    summary = {
        "loss_count": core_summary["loss_count"], "valued_loss_count": core_summary["valued_loss_count"],
        "total_isk_lost": _money_from_cents(core_summary["total_isk_lost_cents"]),
        "average_isk_per_loss": _money_from_cents(core_summary["average_isk_per_loss_cents"]),
        "average_isk_per_calendar_day": _money_from_cents(core_summary["average_isk_per_calendar_day_cents"]),
        "average_isk_per_active_loss_day": _money_from_cents(core_summary["average_isk_per_active_loss_day_cents"]),
        "calendar_days": core_summary["calendar_days"], "active_loss_days": core_summary["active_loss_days"],
        "requested_reimbursement": _money_from_cents(core_summary["requested_reimbursement_cents"]),
        "approved_reimbursement": _money_from_cents(core_summary["approved_reimbursement_cents"]),
        "rejected_reimbursement": _money_from_cents(core_summary["rejected_reimbursement_cents"]),
        "paid_reimbursement": _money_from_cents(core_summary["paid_reimbursement_cents"]),
        "loss_less_approved": _money_from_cents(core_summary["loss_less_approved_cents"]),
        "loss_less_paid": _money_from_cents(core_summary["loss_less_paid_cents"]),
    }
    time_series = [{
        "bucket": row["bucket"], "loss_count": row["loss_count"], "valued_count": row["valued_count"],
        "total_isk": _money_from_cents(row["total_isk_cents"]), "request_ids": row["request_ids"],
    } for row in reduction["time_series"]]
    breakdowns = {
        section: [_breakdown_from_contract(row) for row in members]
        for section, members in reduction["breakdowns"].items()
    }
    top = {
        section: [_breakdown_from_contract(row) for row in members]
        for section, members in reduction["top"].items()
    }
    core_quality = reduction["quality"]
    generated = datetime.now(timezone.utc)
    return {
        "summary": summary, "time_series": time_series, "granularity": granularity, "breakdowns": breakdowns,
        "top": top,
        "quality": {"unvalued_count": core_quality["unvalued_count"],
                    "unvalued_percentage": core_quality["unvalued_percentage_units"] / 100,
                    "missing_doctrine_count": core_quality["missing_doctrine_count"],
                    "missing_ship_type_count": core_quality["missing_ship_type_count"],
                    "manual_count": core_quality["manual_count"],
                    "imported_count": core_quality["imported_count"],
                    "excluded_record_count": excluded_count,
                    "latest_included_loss": rows[-1].loss_occurred_at.isoformat() if rows else None,
                    "generated_at": generated.isoformat()},
        "engine_used": reduction.get("engine_used", "python"),
        "engine_requested": reduction.get("engine_requested", "python"),
        "engine_shadow_match": reduction.get("engine_shadow_match"),
        "engine_fallback_reason": reduction.get("engine_fallback_reason"),
        "workflow_event_counts": dict(workflow_counts), "applied_filters": applied_filters,
        "metric_definitions": {"version": METRIC_VERSION, "reporting_timezone": reporting_timezone,
            "ships_lost": "Distinct non-draft operational SRP loss records; duplicate, invalid, test, and cancelled records are excluded by default.",
            "total_isk_lost": "Sum of non-null authoritative loss values. Unknown values are reported separately and never converted to zero.",
            "average_isk_per_loss": "Total authoritative loss divided by all included loss records; unknown valuations remain in the denominator and are reported separately.",
            "authoritative_value_precedence": ["manual valuation override", "verified valuation", "verified killmail total", "submission-time estimate", "unknown"],
            "calendar_day_average": "Total authoritative loss divided by inclusive calendar days in the reporting range.",
            "active_day_average": "Total authoritative loss divided by distinct local reporting dates containing a loss."},
    }


def detailed_csv(rows: list[SrpRequest]) -> str:
    buffer = io.StringIO(); writer = csv.writer(buffer)
    fields = ["request_id", "loss_occurred_at_utc", "entered_timezone", "character", "corporation", "alliance", "operation", "loss_reason", "doctrine", "doctrine_priority", "fitting", "ship_type", "ship_group", "solar_system", "region", "security_class", "status", "disposition", "data_source", "valuation_status", "authoritative_loss_isk", "estimated_loss_isk", "requested_isk", "approved_isk", "paid_isk", "killmail_id"]
    writer.writerow(fields)
    for row in rows:
        writer.writerow([row.id, row.loss_occurred_at.isoformat(), row.entered_timezone, row.character_name_snapshot,
            row.corporation_name_snapshot, row.alliance_name_snapshot, row.operation_name_snapshot, row.loss_reason_name_snapshot,
            row.doctrine_name_snapshot, row.doctrine_priority_code_snapshot, row.fitting_name_snapshot, row.ship_name_snapshot,
            row.ship_group_name_snapshot, row.system_name_snapshot, row.region_name_snapshot, row.security_class, row.status,
            row.record_disposition, row.data_source, row.valuation_status, money_string(row.authoritative_loss_value),
            money_string(row.submission_estimated_loss_value), money_string(row.requested_reimbursement_amount),
            money_string(row.approved_reimbursement_amount), money_string(row.paid_reimbursement_amount), row.killmail_id])
    return buffer.getvalue()


def aggregate_csv(analytics: dict[str, Any]) -> str:
    buffer = io.StringIO(); writer = csv.writer(buffer)
    writer.writerow(["section", "key", "label", "loss_count", "valued_count", "total_isk", "average_isk"])
    for key, value in analytics["summary"].items(): writer.writerow(["summary", key, "", "", "", value, ""])
    for section, members in analytics["breakdowns"].items():
        for row in members: writer.writerow([section, row["id"], row["label"], row["loss_count"], row["valued_count"], row["total_isk"], row["average_isk"]])
    return buffer.getvalue()
