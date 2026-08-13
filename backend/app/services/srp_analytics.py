from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any, Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SrpRequest, SrpRequestEvent
from app.services.srp import money_string

ZERO = Decimal("0.00")
METRIC_VERSION = "srp.analytics.v1"
EXCLUDED_DISPOSITIONS = {"duplicate", "invalid", "test", "cancelled"}


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


def _sum(rows: Iterable[SrpRequest], field: str) -> Decimal:
    return sum((Decimal(value) for row in rows if (value := getattr(row, field)) is not None), ZERO)


def _bucket_key(value: datetime, granularity: str, zone: ZoneInfo) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    local = value.astimezone(zone)
    if granularity == "month": return local.strftime("%Y-%m")
    if granularity == "week":
        start = local.date() - timedelta(days=local.weekday())
        return start.isoformat()
    return local.date().isoformat()


def _breakdown(rows: list[SrpRequest], id_field: str, label_field: str) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, str], list[SrpRequest]] = defaultdict(list)
    for row in rows:
        label = getattr(row, label_field) or "Unknown"
        groups[(getattr(row, id_field), label)].append(row)
    output = []
    for (value_id, label), members in groups.items():
        valued = [row for row in members if row.authoritative_loss_value is not None]
        total = _sum(valued, "authoritative_loss_value")
        output.append({"id": value_id, "label": label, "loss_count": len(members), "valued_count": len(valued),
                       "total_isk": money_string(total), "average_isk": money_string(total / len(valued)) if valued else None,
                       "request_ids": [row.id for row in members]})
    return sorted(output, key=lambda item: (-Decimal(item["total_isk"] or "0"), -item["loss_count"], item["label"]))


def build_analytics(db: Session, rows: list[SrpRequest], *, date_from: date | None, date_to: date | None,
                    reporting_timezone: str, applied_filters: dict[str, Any], user_id: int, manager: bool) -> dict[str, Any]:
    try: zone = ZoneInfo(reporting_timezone)
    except ZoneInfoNotFoundError as exc: raise HTTPException(status_code=400, detail="Unknown reporting timezone") from exc
    valued = [row for row in rows if row.authoritative_loss_value is not None]
    total = _sum(valued, "authoritative_loss_value")
    if date_from and date_to:
        calendar_days = max((date_to - date_from).days + 1, 1)
    elif rows:
        local_dates = [(row.loss_occurred_at if row.loss_occurred_at.tzinfo else row.loss_occurred_at.replace(tzinfo=timezone.utc)).astimezone(zone).date() for row in rows]
        calendar_days = (max(local_dates) - min(local_dates)).days + 1
    else:
        calendar_days = 0
    active_days = len({(row.loss_occurred_at if row.loss_occurred_at.tzinfo else row.loss_occurred_at.replace(tzinfo=timezone.utc)).astimezone(zone).date() for row in rows})
    granularity = "day" if calendar_days <= 45 else "week" if calendar_days <= 180 else "month"
    buckets: dict[str, list[SrpRequest]] = defaultdict(list)
    for row in rows: buckets[_bucket_key(row.loss_occurred_at, granularity, zone)].append(row)
    time_series = [{"bucket": key, "loss_count": len(members), "valued_count": sum(r.authoritative_loss_value is not None for r in members),
                    "total_isk": money_string(_sum(members, "authoritative_loss_value")), "request_ids": [r.id for r in members]}
                   for key, members in sorted(buckets.items())]
    all_visible_statement = select(SrpRequest).where(SrpRequest.archived_at.is_(None), SrpRequest.status != "draft", SrpRequest.record_disposition.in_(EXCLUDED_DISPOSITIONS))
    if not manager: all_visible_statement = all_visible_statement.where(SrpRequest.requesting_user_id == user_id)
    if date_from: all_visible_statement = all_visible_statement.where(SrpRequest.loss_occurred_at >= _utc_boundary(date_from, reporting_timezone))
    if date_to: all_visible_statement = all_visible_statement.where(SrpRequest.loss_occurred_at < _utc_boundary(date_to, reporting_timezone, next_day=True))
    excluded_count = len(db.scalars(all_visible_statement).all())
    event_statement = select(SrpRequestEvent.event_type, SrpRequestEvent.occurred_at).join(SrpRequest).where(SrpRequest.id.in_([row.id for row in rows])) if rows else None
    workflow_counts: dict[str, int] = defaultdict(int)
    if event_statement is not None:
        for event_type, _ in db.execute(event_statement): workflow_counts[event_type] += 1
    requested = _sum(rows, "requested_reimbursement_amount")
    approved = _sum(rows, "approved_reimbursement_amount")
    paid = _sum(rows, "paid_reimbursement_amount")
    rejected = _sum([row for row in rows if row.status == "rejected"], "requested_reimbursement_amount")
    unvalued = len(rows) - len(valued)
    summary = {
        "loss_count": len(rows), "valued_loss_count": len(valued), "total_isk_lost": money_string(total),
        "average_isk_per_loss": money_string(total / len(rows)) if rows else None,
        "average_isk_per_calendar_day": money_string(total / calendar_days) if calendar_days else None,
        "average_isk_per_active_loss_day": money_string(total / active_days) if active_days else None,
        "calendar_days": calendar_days, "active_loss_days": active_days,
        "requested_reimbursement": money_string(requested), "approved_reimbursement": money_string(approved),
        "rejected_reimbursement": money_string(rejected), "paid_reimbursement": money_string(paid),
        "loss_less_approved": money_string(total - approved), "loss_less_paid": money_string(total - paid),
    }
    breakdowns = {
        "doctrines": _breakdown(rows, "doctrine_id", "doctrine_name_snapshot"),
        "fits": _breakdown(rows, "fitting_id", "fitting_name_snapshot"),
        "ship_types": _breakdown(rows, "ship_type_id", "ship_name_snapshot"),
        "ship_groups": _breakdown(rows, "ship_group_id", "ship_group_name_snapshot"),
        "characters": _breakdown(rows, "character_id", "character_name_snapshot"),
        "operations": _breakdown(rows, "operation_id", "operation_name_snapshot"),
        "corporations": _breakdown(rows, "corporation_id", "corporation_name_snapshot"),
        "alliances": _breakdown(rows, "alliance_id", "alliance_name_snapshot"),
        "systems": _breakdown(rows, "system_id", "system_name_snapshot"),
        "regions": _breakdown(rows, "region_id", "region_name_snapshot"),
        "statuses": _breakdown(rows, "status", "status"),
        "security_classes": _breakdown(rows, "security_class", "security_class"),
    }
    generated = datetime.now(timezone.utc)
    return {
        "summary": summary, "time_series": time_series, "granularity": granularity, "breakdowns": breakdowns,
        "top": {"doctrines_by_isk": breakdowns["doctrines"][:10],
                "doctrines_by_losses": sorted(breakdowns["doctrines"], key=lambda x: (-x["loss_count"], x["label"]))[:10],
                "ships_by_losses": sorted(breakdowns["ship_types"], key=lambda x: (-x["loss_count"], x["label"]))[:10]},
        "quality": {"unvalued_count": unvalued, "unvalued_percentage": round(unvalued * 100 / len(rows), 2) if rows else 0,
                    "missing_doctrine_count": sum(row.doctrine_id is None for row in rows),
                    "missing_ship_type_count": sum(row.ship_type_id is None for row in rows),
                    "manual_count": sum(row.data_source == "manual" for row in rows),
                    "imported_count": sum(row.data_source != "manual" for row in rows),
                    "excluded_record_count": excluded_count,
                    "latest_included_loss": rows[-1].loss_occurred_at.isoformat() if rows else None,
                    "generated_at": generated.isoformat()},
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
