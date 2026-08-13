from __future__ import annotations

import secrets
from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import can_view_all_characters, get_current_user
from app.api.fittings import can_view_fitting
from app.core.config import get_settings
from app.core.security import encrypt_secret
from app.db.session import get_db
from app.models import (CharacterFitting, CharacterFittingItem, Doctrine, DoctrineFitting, EveCharacter, EveConstellation, EveSystem, EveType, SrpLossReason,
                        SrpOperation, SrpRequest, SrpRequestEvent, User)
from app.schemas.fleet_operations import (SrpLossReasonInput, SrpOperationInput, SrpOperationPatch, SrpRequestInput,
                                          SrpRequestPatch, SrpReviewPatch, SrpTransitionInput)
from app.services.permissions import can_view_at_least, can_view_section
from app.services.srp import (audit_event, fitting_snapshot, money_string, normalize_loss_datetime,
                              refresh_authoritative_value, validate_srp_transition)
from app.services.srp_analytics import aggregate_csv, build_analytics, detailed_csv, filtered_rows

router = APIRouter(prefix="/srp", tags=["srp"])


def require_view(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if not can_view_section(user, "srp", db):
        raise HTTPException(status_code=403, detail="SRP permission is required")
    return user


def is_manager(user: User, db: Session) -> bool:
    return can_view_at_least(user, "officer", db)


def require_manager(user: User, db: Session) -> None:
    if not is_manager(user, db):
        raise HTTPException(status_code=403, detail="An officer or director is required")


def srp_query():
    return select(SrpRequest).options(
        selectinload(SrpRequest.requesting_user), selectinload(SrpRequest.reviewed_by_user),
        selectinload(SrpRequest.character).selectinload(EveCharacter.corporation),
        selectinload(SrpRequest.character).selectinload(EveCharacter.alliance),
        selectinload(SrpRequest.fitting).selectinload(CharacterFitting.ship_type),
        selectinload(SrpRequest.fitting).selectinload(CharacterFitting.items),
        selectinload(SrpRequest.doctrine), selectinload(SrpRequest.operation), selectinload(SrpRequest.loss_reason),
        selectinload(SrpRequest.events).selectinload(SrpRequestEvent.actor),
    )


def load_request(db: Session, request_id: int, current_user: User) -> SrpRequest:
    row = db.scalar(srp_query().where(SrpRequest.id == request_id))
    if row is None or (row.requesting_user_id != current_user.id and not is_manager(current_user, db)):
        raise HTTPException(status_code=404, detail="SRP request not found")
    return row


def operation_data(row: SrpOperation, *, include_link: bool = True) -> dict[str, Any]:
    data = {"id": row.id, "name": row.name, "start_at": row.start_at.isoformat(),
            "end_at": row.end_at.isoformat() if row.end_at else None,
            "fleet_commander_character_id": row.fleet_commander_character_id,
            "fleet_commander_name": row.fleet_commander.name if row.fleet_commander else None,
            "doctrine_id": row.doctrine_id, "doctrine_name": row.doctrine.name if row.doctrine else None,
            "fitting_id": row.doctrine.fitting_id if row.doctrine else None,
            "corporation_id": row.corporation_id, "corporation_name": row.corporation.name if row.corporation else None,
            "alliance_id": row.alliance_id, "alliance_name": row.alliance.name if row.alliance else None,
            "notes": row.notes, "status": row.status, "created_at": row.created_at.isoformat()}
    if include_link:
        data.update(share_token=row.share_token,
                    submission_url=f"{get_settings().frontend_url.rstrip('/')}/#srp/submit/{row.share_token}")
    return data


def serialize_request(row: SrpRequest, current_user: User, db: Session, *, include_events: bool = False) -> dict[str, Any]:
    data = {
        "id": row.id, "requesting_user_id": row.requesting_user_id,
        "requesting_user_name": row.requesting_user.display_name if row.requesting_user else None,
        "character_id": row.character_id, "character_name": row.character_name_snapshot,
        "corporation_id": row.corporation_id, "corporation_name": row.corporation_name_snapshot,
        "alliance_id": row.alliance_id, "alliance_name": row.alliance_name_snapshot,
        "fitting_id": row.fitting_id, "fitting_name": row.fitting_name_snapshot,
        "fitting_snapshot": row.fitting_snapshot, "ship_type_id": row.ship_type_id,
        "ship_name": row.ship_name_snapshot, "ship_group_id": row.ship_group_id,
        "ship_group_name": row.ship_group_name_snapshot,
        "doctrine_id": row.doctrine_id, "doctrine_name": row.doctrine_name_snapshot,
        "doctrine_priority_code": row.doctrine_priority_code_snapshot,
        "operation_id": row.operation_id, "operation_name": row.operation_name_snapshot,
        "loss_reason_id": row.loss_reason_id, "loss_reason_name": row.loss_reason_name_snapshot,
        "system_id": row.system_id, "system_name": row.system_name_snapshot,
        "region_id": row.region_id, "region_name": row.region_name_snapshot,
        "security_status": row.security_status, "security_class": row.security_class,
        "loss_date": row.loss_date.isoformat(), "loss_time": row.loss_time.isoformat(timespec="minutes"),
        "loss_occurred_at": row.loss_occurred_at.isoformat(), "entered_timezone": row.entered_timezone,
        "killmail_id": row.killmail_id, "killmail_url": row.killmail_url,
        "has_killmail_hash": bool(row.killmail_hash), "data_source": row.data_source,
        "notes": row.notes, "status": row.status, "record_disposition": row.record_disposition,
        "duplicate_of_request_id": row.duplicate_of_request_id, "exclusion_reason": row.exclusion_reason,
        "valuation_source": row.valuation_source, "valuation_status": row.valuation_status,
        "valuation_timestamp": row.valuation_timestamp.isoformat() if row.valuation_timestamp else None,
        "valuation_market_context": row.valuation_market_context,
        "valuation_override_reason": row.valuation_override_reason,
        "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "paid_at": row.paid_at.isoformat() if row.paid_at else None,
        "reviewed_by": row.reviewed_by_user.display_name if row.reviewed_by_user else None,
        "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat(),
        "can_edit": row.requesting_user_id == current_user.id and row.status == "draft",
        "can_review": is_manager(current_user, db),
    }
    for field in ("expected_fit_value", "hull_value", "fitted_module_value", "cargo_value", "drone_fighter_value",
                  "submission_estimated_loss_value", "killmail_destroyed_value", "killmail_dropped_value",
                  "killmail_total_loss_value", "verified_loss_value", "authoritative_loss_value",
                  "requested_reimbursement_amount", "approved_reimbursement_amount", "paid_reimbursement_amount",
                  "manual_valuation_override"):
        data[field] = money_string(getattr(row, field))
    if include_events:
        data["events"] = [{"id": event.id, "event_type": event.event_type,
                           "actor": event.actor.display_name if event.actor else None,
                           "occurred_at": event.occurred_at.isoformat(), "old_values": event.old_values,
                           "new_values": event.new_values, "metadata": event.event_metadata, "reason": event.reason}
                          for event in sorted(row.events, key=lambda value: (value.occurred_at, value.id))]
    return data


def validate_selection(character_id: int, fitting_id: int, doctrine_id: int | None, current_user: User, db: Session):
    character = db.get(EveCharacter, character_id)
    if character is None: raise HTTPException(status_code=400, detail="Character is unavailable")
    if character.owner_user_id != current_user.id and not can_view_all_characters(current_user, db):
        raise HTTPException(status_code=403, detail="You can only submit SRP for your own characters")
    fitting = db.scalar(select(CharacterFitting).options(
        selectinload(CharacterFitting.character), selectinload(CharacterFitting.ship_type).selectinload(EveType.group),
        selectinload(CharacterFitting.items)).where(CharacterFitting.id == fitting_id))
    if fitting is None or not can_view_fitting(current_user, fitting, db): raise HTTPException(status_code=400, detail="Fitting is unavailable")
    doctrine = db.scalar(select(Doctrine).options(selectinload(Doctrine.fitting_links)).where(Doctrine.id == doctrine_id)) if doctrine_id else None
    if doctrine_id and (doctrine is None or doctrine.archived_at is not None): raise HTTPException(status_code=400, detail="Doctrine is unavailable")
    if doctrine and fitting.id not in ({link.fitting_id for link in doctrine.fitting_links} or {doctrine.fitting_id}): raise HTTPException(status_code=400, detail="Selected fitting does not match the doctrine")
    return character, fitting, doctrine


def resolve_operation(db: Session, operation_id: int | None, operation_token: str | None = None) -> SrpOperation | None:
    statement = select(SrpOperation).options(selectinload(SrpOperation.doctrine), selectinload(SrpOperation.fleet_commander),
        selectinload(SrpOperation.corporation), selectinload(SrpOperation.alliance))
    operation = db.scalar(statement.where(SrpOperation.share_token == operation_token)) if operation_token else db.scalar(statement.where(SrpOperation.id == operation_id)) if operation_id else None
    if (operation_id or operation_token) and operation is None: raise HTTPException(status_code=400, detail="SRP instance is unavailable")
    return operation


def operation_statement_for(user: User, db: Session):
    statement = select(SrpOperation).options(selectinload(SrpOperation.doctrine), selectinload(SrpOperation.fleet_commander),
        selectinload(SrpOperation.corporation), selectinload(SrpOperation.alliance)).where(SrpOperation.archived_at.is_(None))
    if is_manager(user, db):
        return statement
    owned = db.scalars(select(EveCharacter).where(EveCharacter.owner_user_id == user.id)).all()
    corporation_ids = {row.corporation_id for row in owned if row.corporation_id}
    alliance_ids = {row.alliance_id for row in owned if row.alliance_id}
    visibility = [and_(SrpOperation.corporation_id.is_(None), SrpOperation.alliance_id.is_(None))]
    if corporation_ids: visibility.append(SrpOperation.corporation_id.in_(corporation_ids))
    if alliance_ids: visibility.append(SrpOperation.alliance_id.in_(alliance_ids))
    return statement.where(or_(*visibility))


def apply_request_values(row: SrpRequest, payload: SrpRequestInput | SrpRequestPatch, current_user: User, db: Session) -> None:
    character_id = payload.character_id if payload.character_id is not None else row.character_id
    fitting_id = payload.fitting_id if payload.fitting_id is not None else row.fitting_id
    doctrine_id = payload.doctrine_id if "doctrine_id" in payload.model_fields_set else row.doctrine_id
    operation_id = payload.operation_id if "operation_id" in payload.model_fields_set else row.operation_id
    operation = resolve_operation(db, operation_id, getattr(payload, "operation_token", None))
    if operation:
        visible_ids = {candidate.id for candidate in db.scalars(operation_statement_for(current_user, db)).all()}
        if operation.id not in visible_ids:
            raise HTTPException(status_code=404, detail="This SRP instance is unavailable to your organization")
        if operation.status != "open" and row.id is None: raise HTTPException(status_code=409, detail="This SRP instance is closed")
        operation_id = operation.id
        if operation.doctrine_id:
            doctrine_id = operation.doctrine_id
            doctrine_fit = db.get(Doctrine, operation.doctrine_id)
            allowed_ids = set(db.scalars(select(DoctrineFitting.fitting_id).where(DoctrineFitting.doctrine_id == operation.doctrine_id)).all())
            if fitting_id not in allowed_ids:
                fitting_id = doctrine_fit.fitting_id if doctrine_fit and doctrine_fit.fitting_id else fitting_id
    elif "doctrine_id" in payload.model_fields_set and doctrine_id:
        selected_doctrine = db.get(Doctrine, doctrine_id)
        if selected_doctrine and selected_doctrine.fitting_id and "fitting_id" not in payload.model_fields_set:
            fitting_id = selected_doctrine.fitting_id
    character, fitting, doctrine = validate_selection(character_id, fitting_id, doctrine_id, current_user, db)
    entered_timezone = payload.entered_timezone if payload.entered_timezone is not None else row.entered_timezone
    loss_date = payload.loss_date if payload.loss_date is not None else row.loss_date
    loss_time = payload.loss_time if payload.loss_time is not None else row.loss_time
    row.character_id = character.id; row.character_name_snapshot = character.name
    row.corporation_id = character.corporation_id; row.corporation_name_snapshot = character.corporation.name if character.corporation else None
    row.alliance_id = character.alliance_id; row.alliance_name_snapshot = character.alliance.name if character.alliance else None
    row.fitting_id = fitting.id; row.fitting_name_snapshot = fitting.name; row.fitting_snapshot = fitting_snapshot(fitting)
    row.ship_type_id = fitting.ship_type_id; row.ship_name_snapshot = fitting.ship_type.name if fitting.ship_type else None
    row.ship_group_id = fitting.ship_type.group_id if fitting.ship_type else None
    row.ship_group_name_snapshot = fitting.ship_type.group.name if fitting.ship_type and fitting.ship_type.group else None
    row.doctrine_id = doctrine.id if doctrine else None; row.doctrine_name_snapshot = doctrine.name if doctrine else None
    row.doctrine_priority_code_snapshot = doctrine.priority_code if doctrine else None
    row.operation_id = operation_id; row.operation_name_snapshot = operation.name if operation else None
    reason_id = payload.loss_reason_id if "loss_reason_id" in payload.model_fields_set else row.loss_reason_id
    loss_reason = db.get(SrpLossReason, reason_id) if reason_id else None
    if reason_id and not loss_reason: raise HTTPException(status_code=400, detail="Loss reason is unavailable")
    row.loss_reason_id = reason_id; row.loss_reason_name_snapshot = loss_reason.name if loss_reason else None
    system_id = payload.system_id if "system_id" in payload.model_fields_set else row.system_id
    system = db.scalar(select(EveSystem).options(selectinload(EveSystem.constellation).selectinload(EveConstellation.region)).where(EveSystem.system_id == system_id)) if system_id else None
    if system_id and not system: raise HTTPException(status_code=400, detail="Solar system is unavailable")
    row.system_id = system_id; row.system_name_snapshot = system.name if system else None
    row.region_id = system.constellation.region_id if system and system.constellation else None
    row.region_name_snapshot = system.constellation.region.name if system and system.constellation and system.constellation.region else None
    row.security_status = system.security_status if system else None; row.security_class = system.security_class if system else None
    row.loss_date = loss_date; row.loss_time = loss_time; row.entered_timezone = entered_timezone
    row.loss_occurred_at = normalize_loss_datetime(loss_date, loss_time, entered_timezone)
    for field in ("notes", "killmail_id", "killmail_url", "hull_value", "fitted_module_value", "cargo_value",
                  "drone_fighter_value", "submission_estimated_loss_value", "requested_reimbursement_amount"):
        if field in payload.model_fields_set: setattr(row, field, getattr(payload, field))
    if "killmail_hash" in payload.model_fields_set:
        if payload.killmail_hash and not get_settings().token_encryption_key:
            raise HTTPException(status_code=503, detail="Killmail hash storage requires TOKEN_ENCRYPTION_KEY")
        row.killmail_hash = encrypt_secret(payload.killmail_hash, get_settings().token_encryption_key) if payload.killmail_hash else None
    if "data_source" in payload.model_fields_set:
        if payload.data_source == "administrative_entry" and not is_manager(current_user, db):
            raise HTTPException(status_code=403, detail="Only SRP staff may create an administrative entry")
        row.data_source = payload.data_source
    refresh_authoritative_value(row)


@router.get("/meta")
def srp_meta(current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    characters = db.scalars(select(EveCharacter).where(EveCharacter.owner_user_id == current_user.id).order_by(EveCharacter.name)).all()
    fittings = db.scalars(select(CharacterFitting).options(selectinload(CharacterFitting.character), selectinload(CharacterFitting.ship_type)).order_by(CharacterFitting.name)).all()
    statement = select(Doctrine).options(selectinload(Doctrine.fitting).selectinload(CharacterFitting.ship_type), selectinload(Doctrine.fitting_links).selectinload(DoctrineFitting.fitting).selectinload(CharacterFitting.ship_type)).where(Doctrine.archived_at.is_(None), Doctrine.fitting_id.is_not(None))
    if not is_manager(current_user, db): statement = statement.where(Doctrine.is_shared.is_(True))
    doctrines = db.scalars(statement.order_by(Doctrine.name)).all()
    operations = db.scalars(operation_statement_for(current_user, db).order_by(SrpOperation.start_at.desc())).all()
    reasons = db.scalars(select(SrpLossReason).where(SrpLossReason.is_active.is_(True)).order_by(SrpLossReason.display_order, SrpLossReason.name)).all()
    return {"can_review": is_manager(current_user, db), "characters": [{"id": r.id, "name": r.name} for r in characters],
        "fittings": [{"id": r.id, "name": r.name, "ship_name": r.ship_type.name if r.ship_type else None} for r in fittings if can_view_fitting(current_user, r, db)],
        "doctrines": [{"id": r.id, "name": r.name, "purpose": r.purpose or r.description, "priority_code": r.priority_code,
                        "fitting_id": r.fitting_id, "fitting_name": r.fitting.name if r.fitting else None,
                        "ship_name": r.fitting.ship_type.name if r.fitting and r.fitting.ship_type else None,
                        "fittings": [{"id": link.fitting_id, "name": link.fitting.name, "ship_name": link.fitting.ship_type.name if link.fitting and link.fitting.ship_type else None, "is_primary": link.is_primary} for link in r.fitting_links if link.fitting]} for r in doctrines],
        "operations": [operation_data(r, include_link=is_manager(current_user, db)) for r in operations],
        "loss_reasons": [{"id": r.id, "key": r.key, "name": r.name, "description": r.description} for r in reasons],
        "statuses": ["draft", "submitted", "under_review", "approved", "rejected", "paid"], "time_standard": "EVE time (UTC)"}


@router.get("/intake/{share_token}")
def intake_context(share_token: str, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    operation = resolve_operation(db, None, share_token)
    if not operation or operation.archived_at or operation.status != "open": raise HTTPException(status_code=404, detail="This SRP submission link is closed or unavailable")
    visible_ids = {candidate.id for candidate in db.scalars(operation_statement_for(current_user, db)).all()}
    if operation.id not in visible_ids: raise HTTPException(status_code=404, detail="This SRP submission link is unavailable to your organization")
    return operation_data(operation, include_link=False)


@router.get("/systems")
def search_systems(q: str = Query(min_length=2, max_length=80), current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.scalars(select(EveSystem).options(selectinload(EveSystem.constellation).selectinload(EveConstellation.region)).where(EveSystem.name.ilike(f"%{q.strip()}%")).order_by(EveSystem.name).limit(25)).all()
    return [{"id": r.system_id, "name": r.name, "region": r.constellation.region.name if r.constellation and r.constellation.region else None,
             "security_status": r.security_status, "security_class": r.security_class} for r in rows]


@router.get("/operations")
def list_operations(current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.scalars(operation_statement_for(current_user, db).order_by(SrpOperation.start_at.desc())).all()
    return [operation_data(row, include_link=is_manager(current_user, db)) for row in rows]


@router.post("/operations")
def create_operation(payload: SrpOperationInput, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_manager(current_user, db)
    row = SrpOperation(**payload.model_dump(), share_token=secrets.token_urlsafe(24), created_by_user_id=current_user.id)
    db.add(row); db.commit(); db.refresh(row)
    return operation_data(resolve_operation(db, row.id), include_link=True)


@router.patch("/operations/{operation_id}")
def update_operation(operation_id: int, payload: SrpOperationPatch, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_manager(current_user, db); row = db.get(SrpOperation, operation_id)
    if not row or row.archived_at: raise HTTPException(status_code=404, detail="SRP instance not found")
    for field, value in payload.model_dump(exclude_unset=True).items(): setattr(row, field, value)
    db.commit(); return operation_data(resolve_operation(db, row.id), include_link=True)


@router.post("/operations/{operation_id}/rotate-link")
def rotate_operation_link(operation_id: int, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_manager(current_user, db); row = db.get(SrpOperation, operation_id)
    if not row or row.archived_at: raise HTTPException(status_code=404, detail="SRP instance not found")
    row.share_token = secrets.token_urlsafe(24); db.commit()
    return operation_data(resolve_operation(db, row.id), include_link=True)


@router.post("/loss-reasons")
def create_loss_reason(payload: SrpLossReasonInput, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_manager(current_user, db); row = SrpLossReason(**payload.model_dump()); db.add(row); db.commit(); db.refresh(row)
    return {"id": row.id, **payload.model_dump()}


def analytics_params(date_from=None, date_to=None, reporting_timezone="UTC", doctrine_id=None, doctrine_priority=None, fitting_id=None,
                     ship_type_id=None, ship_group_id=None, character_id=None, corporation_id=None, alliance_id=None, operation_id=None,
                     system_id=None, region_id=None, security_class=None, status=None, valuation_status=None, data_source=None, include_excluded=False):
    return locals()


@router.get("/analytics")
def analytics(date_from: date | None = None, date_to: date | None = None, reporting_timezone: str = "UTC", doctrine_id: int | None = None,
              doctrine_priority: str | None = None, fitting_id: int | None = None, ship_type_id: int | None = None,
              ship_group_id: int | None = None, character_id: int | None = None, corporation_id: int | None = None,
              alliance_id: int | None = None, operation_id: int | None = None, system_id: int | None = None,
              region_id: int | None = None, security_class: str | None = None, status: str | None = None,
              valuation_status: str | None = None, data_source: str | None = None, include_excluded: bool = False,
              current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    params = analytics_params(date_from, date_to, reporting_timezone, doctrine_id, doctrine_priority, fitting_id, ship_type_id,
        ship_group_id, character_id, corporation_id, alliance_id, operation_id, system_id, region_id, security_class, status,
        valuation_status, data_source, include_excluded)
    manager = is_manager(current_user, db); rows = filtered_rows(db, user_id=current_user.id, manager=manager, **params)
    return build_analytics(db, rows, date_from=date_from, date_to=date_to, reporting_timezone=reporting_timezone,
                           applied_filters={k: v for k, v in params.items() if v not in (None, "", False)}, user_id=current_user.id, manager=manager)


@router.get("/analytics/records")
def analytics_records(request_ids: str = "", current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    ids = {int(value) for value in request_ids.split(",") if value.strip().isdigit()}
    if not ids: return []
    statement = srp_query().where(SrpRequest.id.in_(ids))
    if not is_manager(current_user, db): statement = statement.where(SrpRequest.requesting_user_id == current_user.id)
    return [serialize_request(row, current_user, db) for row in db.scalars(statement).all()]


@router.get("/analytics/export.csv")
def export_analytics(kind: str = Query(default="details", pattern="^(details|aggregates)$"), date_from: date | None = None,
                     date_to: date | None = None, reporting_timezone: str = "UTC", doctrine_id: int | None = None,
                     operation_id: int | None = None, status: str | None = None, valuation_status: str | None = None,
                     data_source: str | None = None, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> Response:
    params = analytics_params(date_from=date_from, date_to=date_to, reporting_timezone=reporting_timezone, doctrine_id=doctrine_id,
                              operation_id=operation_id, status=status, valuation_status=valuation_status, data_source=data_source)
    manager = is_manager(current_user, db); rows = filtered_rows(db, user_id=current_user.id, manager=manager, **params)
    if kind == "details": content = detailed_csv(rows)
    else: content = aggregate_csv(build_analytics(db, rows, date_from=date_from, date_to=date_to, reporting_timezone=reporting_timezone,
            applied_filters={k: v for k, v in params.items() if v not in (None, "", False)}, user_id=current_user.id, manager=manager))
    return Response(content=content, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="eqm-srp-{kind}.csv"'})


@router.get("/analytics/export")
def export_analytics_json(kind: str = Query(default="details", pattern="^(details|aggregates)$"), date_from: date | None = None,
                          date_to: date | None = None, reporting_timezone: str = "UTC", doctrine_id: int | None = None,
                          operation_id: int | None = None, status: str | None = None, valuation_status: str | None = None,
                          data_source: str | None = None, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, str]:
    params = analytics_params(date_from=date_from, date_to=date_to, reporting_timezone=reporting_timezone, doctrine_id=doctrine_id,
                              operation_id=operation_id, status=status, valuation_status=valuation_status, data_source=data_source)
    manager = is_manager(current_user, db); rows = filtered_rows(db, user_id=current_user.id, manager=manager, **params)
    if kind == "details": content = detailed_csv(rows)
    else: content = aggregate_csv(build_analytics(db, rows, date_from=date_from, date_to=date_to, reporting_timezone=reporting_timezone,
            applied_filters={k: v for k, v in params.items() if v not in (None, "", False)}, user_id=current_user.id, manager=manager))
    return {"filename": f"eqm-srp-{kind}.csv", "csv": content}


@router.get("")
def list_requests(q: str = "", status: str = "", character_id: int | None = None, doctrine_id: int | None = None,
                  fitting_id: int | None = None, operation_id: int | None = None, date_from: date | None = None,
                  date_to: date | None = None, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    statement = srp_query().where(SrpRequest.archived_at.is_(None))
    if not is_manager(current_user, db): statement = statement.where(SrpRequest.requesting_user_id == current_user.id)
    if q.strip(): statement = statement.where(or_(SrpRequest.character_name_snapshot.ilike(f"%{q.strip()}%"), SrpRequest.fitting_name_snapshot.ilike(f"%{q.strip()}%"), SrpRequest.doctrine_name_snapshot.ilike(f"%{q.strip()}%"), SrpRequest.operation_name_snapshot.ilike(f"%{q.strip()}%"), SrpRequest.notes.ilike(f"%{q.strip()}%")))
    for column, value in ((SrpRequest.status, status), (SrpRequest.character_id, character_id), (SrpRequest.doctrine_id, doctrine_id), (SrpRequest.fitting_id, fitting_id), (SrpRequest.operation_id, operation_id)):
        if value: statement = statement.where(column == value)
    if date_from: statement = statement.where(SrpRequest.loss_date >= date_from)
    if date_to: statement = statement.where(SrpRequest.loss_date <= date_to)
    return [serialize_request(row, current_user, db) for row in db.scalars(statement.order_by(SrpRequest.loss_occurred_at.desc())).all()]


@router.post("")
def create_request(payload: SrpRequestInput, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    row = SrpRequest(requesting_user_id=current_user.id, character_id=payload.character_id, fitting_id=payload.fitting_id,
        character_name_snapshot="", fitting_name_snapshot="", loss_date=payload.loss_date, loss_time=payload.loss_time,
        loss_occurred_at=normalize_loss_datetime(payload.loss_date, payload.loss_time, payload.entered_timezone), status=payload.status)
    apply_request_values(row, payload, current_user, db); db.add(row); db.flush()
    event_type = "submitted" if payload.status == "submitted" else "draft_created"
    if payload.status == "submitted": row.submitted_at = datetime.now(timezone.utc)
    audit_event(db, row, event_type, current_user.id, new_values={"status": row.status, "operation_id": row.operation_id})
    db.commit(); return serialize_request(load_request(db, row.id, current_user), current_user, db)


@router.get("/{request_id}")
def get_request(request_id: int, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    return serialize_request(load_request(db, request_id, current_user), current_user, db, include_events=True)


@router.patch("/{request_id}")
def update_request(request_id: int, payload: SrpRequestPatch, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    row = load_request(db, request_id, current_user)
    if row.requesting_user_id != current_user.id or row.status != "draft": raise HTTPException(status_code=403, detail="Only your own draft SRP may be edited")
    old = {"doctrine_id": row.doctrine_id, "fitting_id": row.fitting_id, "operation_id": row.operation_id}
    apply_request_values(row, payload, current_user, db)
    audit_event(db, row, "edited", current_user.id, old_values=old,
                new_values={"doctrine_id": row.doctrine_id, "fitting_id": row.fitting_id, "operation_id": row.operation_id})
    db.commit(); return serialize_request(load_request(db, row.id, current_user), current_user, db)


@router.patch("/{request_id}/review")
def review_request(request_id: int, payload: SrpReviewPatch, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_manager(current_user, db); row = load_request(db, request_id, current_user)
    old = {field: money_string(getattr(row, field)) if "value" in field or "amount" in field else getattr(row, field)
           for field in payload.model_fields_set if hasattr(row, field) and field != "reason"}
    selection_fields = {"doctrine_id", "fitting_id", "operation_id", "loss_reason_id", "system_id"}
    if payload.model_fields_set & selection_fields:
        proxy = SrpRequestPatch(**{field: getattr(payload, field) for field in payload.model_fields_set & selection_fields})
        apply_request_values(row, proxy, current_user, db)
    for field in payload.model_fields_set - selection_fields - {"reason"}:
        setattr(row, field, getattr(payload, field))
    if row.record_disposition == "duplicate" and not row.duplicate_of_request_id:
        raise HTTPException(status_code=400, detail="A duplicate must reference the canonical SRP request")
    if row.duplicate_of_request_id == row.id: raise HTTPException(status_code=400, detail="An SRP request cannot duplicate itself")
    if row.manual_valuation_override is not None and not row.valuation_override_reason:
        raise HTTPException(status_code=400, detail="A valuation override reason is required")
    if row.manual_valuation_override is not None:
        row.valuation_status = "overridden"; row.valuation_override_by_user_id = current_user.id; row.valuation_timestamp = datetime.now(timezone.utc)
    refresh_authoritative_value(row)
    new = {field: money_string(getattr(row, field)) if "value" in field or "amount" in field else getattr(row, field)
           for field in payload.model_fields_set if hasattr(row, field) and field != "reason"}
    event_type = "valuation_overridden" if "manual_valuation_override" in payload.model_fields_set else "doctrine_or_fitting_changed" if payload.model_fields_set & {"doctrine_id", "fitting_id"} else "review_edited"
    audit_event(db, row, event_type, current_user.id, old_values=old, new_values=new, reason=payload.reason)
    db.commit(); return serialize_request(load_request(db, row.id, current_user), current_user, db, include_events=True)


@router.post("/{request_id}/transition")
def transition_request(request_id: int, payload: SrpTransitionInput, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    row = load_request(db, request_id, current_user); manager = is_manager(current_user, db)
    if row.status == "draft" and row.requesting_user_id != current_user.id: raise HTTPException(status_code=403, detail="Only the requester may submit a draft")
    old_status = row.status; validate_srp_transition(row.status, payload.status, manager)
    now = datetime.now(timezone.utc); row.status = payload.status
    if payload.status == "submitted": row.submitted_at = now
    if payload.status in {"under_review", "approved", "rejected"}: row.reviewed_at = now; row.reviewed_by_user_id = current_user.id
    if payload.status == "paid": row.paid_at = now; row.reviewed_by_user_id = current_user.id
    event_names = {"submitted": "submitted", "under_review": "review_started", "approved": "approved", "rejected": "rejected", "paid": "payment_recorded"}
    event_type = "reopened" if old_status == "rejected" else event_names[payload.status]
    audit_event(db, row, event_type, current_user.id, old_values={"status": old_status}, new_values={"status": row.status}, reason=payload.reason)
    db.commit(); return serialize_request(load_request(db, row.id, current_user), current_user, db, include_events=True)


@router.delete("/{request_id}")
def archive_request(request_id: int, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    row = load_request(db, request_id, current_user)
    if row.requesting_user_id != current_user.id or row.status != "draft": raise HTTPException(status_code=403, detail="Only your own draft may be archived")
    row.archived_at = datetime.now(timezone.utc); audit_event(db, row, "archived", current_user.id)
    db.commit(); return {"id": row.id, "archived": True}
