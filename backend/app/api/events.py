from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.auth import get_current_user
from app.api.context import can_view_fitting
from app.db.session import get_db
from app.models import (
    CharacterFitting,
    Doctrine,
    EsiToken,
    EveAlliance,
    EveCategory,
    EveCharacter,
    EveCorporation,
    EveGroup,
    EveStation,
    EveSystem,
    EveType,
    Event,
    EventAttendanceEntry,
    EventCharacterRegistration,
    EventDoctrineRequirement,
    EventDoctrineRequirementOption,
    EventLocation,
    EventRoleRequirement,
    EventUserResponse,
    Location,
    User,
)
from app.schemas.events import (
    AttendanceEntryUpdate,
    AttendanceManualCreate,
    AttendanceRegistrationUpdate,
    EventAnalyticsResponse,
    EventCreate,
    EventPatch,
    EventRegistrationCreate,
    EventRegistrationUpdate,
    EventRsvpUpsert,
    EventTransitionRequest,
)
from app.services.audit import record_audit_event
from app.services.events import (
    EVENT_CONSTANTS,
    active_owned_characters,
    can_create_event,
    can_manage_event,
    can_record_attendance,
    can_view_event_analytics,
    can_view_full_composition,
    event_is_visible,
    get_active_owned_character,
    require_attendance_recorder,
    require_event_manager,
    require_events_access,
    utc_aware,
    validate_event_values,
    validate_lifecycle_transition,
    visible_events,
)
from app.services.event_analytics_engine import evaluate_event_analytics_with_engine
from app.services.navigation import search_systems


router = APIRouter(prefix="/events", tags=["events"])


def require_events(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    return require_events_access(current_user, db)


def event_load_options() -> tuple[Any, ...]:
    return (
        selectinload(Event.created_by_user),
        selectinload(Event.lead_character),
        selectinload(Event.doctrine),
        selectinload(Event.audience_corporation),
        selectinload(Event.audience_alliance),
        selectinload(Event.locations).selectinload(EventLocation.system),
        selectinload(Event.locations).selectinload(EventLocation.location),
        selectinload(Event.role_requirements),
        selectinload(Event.doctrine_requirements)
        .selectinload(EventDoctrineRequirement.options)
        .selectinload(EventDoctrineRequirementOption.ship_type),
        selectinload(Event.doctrine_requirements)
        .selectinload(EventDoctrineRequirement.options)
        .selectinload(EventDoctrineRequirementOption.fitting),
        selectinload(Event.responses).selectinload(EventUserResponse.user),
        selectinload(Event.registrations).selectinload(EventCharacterRegistration.character),
        selectinload(Event.registrations).selectinload(EventCharacterRegistration.user),
        selectinload(Event.registrations).selectinload(EventCharacterRegistration.ship_type),
        selectinload(Event.registrations).selectinload(EventCharacterRegistration.saved_fitting),
        selectinload(Event.attendance_entries),
    )


def get_visible_event(event_id: int, current_user: User, db: Session) -> Event:
    event = db.scalar(select(Event).options(*event_load_options()).where(Event.id == event_id))
    if event is None or not event_is_visible(event, current_user, db):
        raise HTTPException(status_code=404, detail="Event not found")
    return event


def formup_location(event: Event) -> EventLocation | None:
    return next((row for row in event.locations if row.location_role == "formup"), None)


def serialize_location(row: EventLocation) -> dict[str, Any]:
    return {
        "id": row.id,
        "location_role": row.location_role,
        "sort_order": row.sort_order,
        "system_id": row.system_id,
        "system_name": row.system.name if row.system else None,
        "security_status": row.system.security_status if row.system else None,
        "location_id": row.location_id,
        "eve_location_id": row.eve_location_id,
        "location_name": row.location.name if row.location else row.location_name_snapshot,
        "location_name_snapshot": row.location_name_snapshot,
        "notes": row.notes,
    }


def serialize_registration(row: EventCharacterRegistration) -> dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "character_id": row.character_id,
        "character_eve_id": row.character_eve_id_snapshot,
        "character_name": row.character_name_snapshot,
        "corporation_name": row.corporation_name_snapshot,
        "alliance_name": row.alliance_name_snapshot,
        "registration_status": row.registration_status,
        "confirmation_status": row.confirmation_status,
        "planned_ship_source": row.planned_ship_source,
        "ship_type_id": row.ship_type_id,
        "ship_name": row.ship_name_snapshot,
        "saved_fitting_id": row.saved_fitting_id,
        "fitting_name": row.fitting_name_snapshot,
        "doctrine_requirement_id": row.doctrine_requirement_id,
        "doctrine_option_id": row.doctrine_option_id,
        "role_key": row.role_key,
        "custom_role": row.custom_role,
        "freeform_ship_description": row.freeform_ship_description,
        "notes": row.notes,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def serialize_attendance(row: EventAttendanceEntry) -> dict[str, Any]:
    return {
        "id": row.id,
        "registration_id": row.registration_id,
        "attendee_source": row.attendee_source,
        "attendance_status": row.attendance_status,
        "linked_user_id": row.linked_user_id,
        "character_id": row.character_id,
        "character_eve_id": row.character_eve_id_snapshot,
        "display_name": row.display_name_snapshot,
        "corporation_name": row.corporation_name_snapshot,
        "alliance_name": row.alliance_name_snapshot,
        "checked_in_at": row.checked_in_at,
        "notes": row.notes,
        "recorded_by_user_id": row.recorded_by_user_id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def serialize_event(event: Event, current_user: User, db: Session, *, detail: bool = False) -> dict[str, Any]:
    formup = formup_location(event)
    own_response = next((row for row in event.responses if row.user_id == current_user.id), None)
    own_registrations = [row for row in event.registrations if row.user_id == current_user.id]
    response_counts: dict[str, int] = defaultdict(int)
    for response in event.responses:
        response_counts[response.status] += 1
    registration_counts: dict[str, int] = defaultdict(int)
    for registration in event.registrations:
        registration_counts[registration.registration_status] += 1
    payload: dict[str, Any] = {
        "id": event.id,
        "title": event.title,
        "event_type": event.event_type,
        "lifecycle_status": event.lifecycle_status,
        "registration_status": event.registration_status,
        "formup_at": event.formup_at,
        "start_at": event.start_at,
        "end_at": event.end_at,
        "estimated_duration_minutes": event.estimated_duration_minutes,
        "operational_area": event.operational_area,
        "lead": {
            "character_id": event.lead_character_id,
            "name": event.lead_character.name if event.lead_character else event.lead_name_snapshot,
        },
        "doctrine_mode": event.doctrine_mode,
        "doctrine": {
            "id": event.doctrine_id,
            "name": event.doctrine.name if event.doctrine else event.doctrine_manual_name,
            "external_url": event.doctrine_external_url or (event.doctrine.external_url if event.doctrine else None),
        },
        "audience_kind": event.audience_kind,
        "composition_visibility": event.composition_visibility,
        "participant_limit": event.participant_limit,
        "limit_basis": event.limit_basis,
        "formup_location": serialize_location(formup) if formup else None,
        "rsvp_counts": dict(response_counts),
        "registration_counts": dict(registration_counts),
        "actual_attendance": sum(row.attendance_status == "attended" for row in event.attendance_entries),
        "my_rsvp": {"status": own_response.status, "notes": own_response.notes} if own_response else None,
        "my_registrations": [serialize_registration(row) for row in own_registrations],
        "permissions": {
            "can_manage": can_manage_event(event, current_user, db),
            "can_record_attendance": can_record_attendance(event, current_user, db),
            "can_view_composition": can_view_full_composition(event, current_user, db),
        },
        "created_by": {
            "id": event.created_by_user_id,
            "name": event.created_by_user.display_name if event.created_by_user else None,
        },
        "created_at": event.created_at,
        "updated_at": event.updated_at,
    }
    if detail:
        payload.update(
            {
                "route_notes": event.route_notes,
                "discord_voice_label": event.discord_voice_label,
                "discord_voice_url": event.discord_voice_url,
                "discord_guild_id": event.discord_guild_id,
                "discord_channel_id": event.discord_channel_id,
                "doctrine_notes": event.doctrine_notes,
                "related_url": event.related_url,
                "instructions": event.instructions,
                "audience_corporation_id": event.audience_corporation_id,
                "audience_alliance_id": event.audience_alliance_id,
                "locations": [serialize_location(row) for row in sorted(event.locations, key=lambda row: row.sort_order)],
                "role_requirements": [
                    {
                        "id": row.id,
                        "role_key": row.role_key,
                        "custom_label": row.custom_label,
                        "requested_quantity": row.requested_quantity,
                        "notes": row.notes,
                        "sort_order": row.sort_order,
                    }
                    for row in sorted(event.role_requirements, key=lambda row: row.sort_order)
                ],
                "doctrine_requirements": [
                    {
                        "id": row.id,
                        "role_requirement_id": row.role_requirement_id,
                        "label": row.label,
                        "requested_quantity": row.requested_quantity,
                        "notes": row.notes,
                        "sort_order": row.sort_order,
                        "options": [
                            {
                                "id": option.id,
                                "ship_type_id": option.ship_type_id,
                                "ship_name": option.ship_type.name if option.ship_type else option.manual_name_snapshot,
                                "fitting_id": option.fitting_id,
                                "fitting_name": option.fitting.name if option.fitting else None,
                                "is_primary": option.is_primary,
                                "sort_order": option.sort_order,
                            }
                            for option in sorted(row.options, key=lambda option: option.sort_order)
                        ],
                    }
                    for row in sorted(event.doctrine_requirements, key=lambda row: row.sort_order)
                ],
            }
        )
    return payload


def add_event_children(event: Event, payload: EventCreate, current_user: User, db: Session) -> None:
    for location_input in payload.locations:
        if db.get(EveSystem, location_input.system_id) is None:
            raise HTTPException(status_code=422, detail=f"Unknown solar system {location_input.system_id}")
        location = db.get(Location, location_input.location_id) if location_input.location_id else None
        if location_input.location_id and location is None:
            raise HTTPException(status_code=422, detail=f"Unknown location {location_input.location_id}")
        if location is not None and location.system_id != location_input.system_id:
            raise HTTPException(status_code=422, detail="Selected location does not belong to the selected system")
        event.locations.append(
            EventLocation(
                **location_input.model_dump(exclude={"location_name_snapshot"}),
                location_name_snapshot=location_input.location_name_snapshot or (location.name if location else None),
            )
        )
    for role_input in payload.role_requirements:
        event.role_requirements.append(EventRoleRequirement(**role_input.model_dump()))
    for requirement_input in payload.doctrine_requirements:
        requirement_values = requirement_input.model_dump(exclude={"options"})
        requirement = EventDoctrineRequirement(**requirement_values)
        for option_input in requirement_input.options:
            option_values = option_input.model_dump()
            if option_input.ship_type_id is not None:
                require_ship_type(option_input.ship_type_id, db)
            if option_input.fitting_id is not None:
                fitting = db.get(CharacterFitting, option_input.fitting_id)
                if fitting is None:
                    raise HTTPException(status_code=422, detail=f"Unknown fitting {option_input.fitting_id}")
                if not can_view_fitting(fitting, current_user, db):
                    raise HTTPException(status_code=403, detail="Doctrine fitting is not visible to the event creator")
            requirement.options.append(EventDoctrineRequirementOption(**option_values))
        event.doctrine_requirements.append(requirement)


def event_corporation_missing(corporation_id: int, db: Session) -> bool:
    from app.models import EveCorporation

    return db.get(EveCorporation, corporation_id) is None


def event_alliance_missing(alliance_id: int, db: Session) -> bool:
    from app.models import EveAlliance

    return db.get(EveAlliance, alliance_id) is None


def require_ship_type(type_id: int, db: Session) -> EveType:
    ship = db.scalar(
        select(EveType)
        .join(EveGroup, EveGroup.group_id == EveType.group_id)
        .join(EveCategory, EveCategory.category_id == EveGroup.category_id)
        .where(
            EveType.type_id == type_id,
            EveType.published.is_(True),
            EveGroup.published.is_(True),
            EveCategory.published.is_(True),
            func.lower(EveCategory.name) == "ship",
        )
    )
    if ship is None:
        raise HTTPException(status_code=422, detail="Selected type is not a published ship hull")
    return ship


@router.get("/meta")
def event_meta(current_user: User = Depends(require_events), db: Session = Depends(get_db)) -> dict[str, Any]:
    lead_characters = db.scalars(
        select(EveCharacter)
        .join(EsiToken, EsiToken.character_id == EveCharacter.id)
        .options(selectinload(EveCharacter.corporation), selectinload(EveCharacter.alliance))
        .where(EsiToken.revoked_at.is_(None), EveCharacter.sync_opt_out.is_(False))
        .distinct()
        .order_by(EveCharacter.name)
    ).all()
    corporations = db.scalars(
        select(EveCorporation)
        .where(EveCorporation.hide_from_corporation_list.is_(False))
        .order_by(EveCorporation.name)
    ).all()
    alliances = db.scalars(select(EveAlliance).order_by(EveAlliance.name)).all()
    return {
        "constants": EVENT_CONSTANTS,
        "permissions": {
            "can_create": can_create_event(current_user, db),
            "can_view_analytics": can_view_event_analytics(current_user, db),
        },
        "directory": {
            "lead_characters": [
                {
                    "id": character.id,
                    "name": character.name,
                    "corporation_name": character.corporation.name if character.corporation else None,
                    "alliance_name": character.alliance.name if character.alliance else None,
                }
                for character in lead_characters
            ],
            "corporations": [
                {"id": corporation.id, "name": corporation.name, "ticker": corporation.ticker}
                for corporation in corporations
            ],
            "alliances": [
                {"id": alliance.id, "name": alliance.name, "ticker": alliance.ticker}
                for alliance in alliances
            ],
        },
    }

@router.get("/search/systems")
def event_system_search(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=50),
    _: User = Depends(require_events),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    return search_systems(db, q, limit)


@router.get("/search/locations")
def event_location_search(
    system_id: int = Query(..., gt=0),
    _: User = Depends(require_events),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    locations = db.scalars(select(Location).where(Location.system_id == system_id).order_by(Location.name)).all()
    stations = db.scalars(select(EveStation).where(EveStation.system_id == system_id).order_by(EveStation.name)).all()
    rows = [
        {"source": "location", "location_id": row.id, "eve_location_id": row.eve_location_id, "name": row.name}
        for row in locations
    ]
    known_eve_ids = {row["eve_location_id"] for row in rows if row["eve_location_id"] is not None}
    rows.extend(
        {
            "source": "station",
            "location_id": None,
            "eve_location_id": station.station_id,
            "name": station.name,
        }
        for station in stations
        if station.station_id not in known_eve_ids
    )
    return rows


@router.get("/search/ships")
def event_ship_search(
    q: str = Query(..., min_length=1),
    limit: int = Query(25, ge=1, le=100),
    _: User = Depends(require_events),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    ships = db.scalars(
        select(EveType)
        .join(EveGroup, EveGroup.group_id == EveType.group_id)
        .join(EveCategory, EveCategory.category_id == EveGroup.category_id)
        .where(
            EveType.name.ilike(f"%{q.strip()}%"),
            EveType.published.is_(True),
            EveGroup.published.is_(True),
            EveCategory.published.is_(True),
            func.lower(EveCategory.name) == "ship",
        )
        .order_by(func.lower(EveType.name))
        .limit(limit)
    ).all()
    return [{"type_id": ship.type_id, "name": ship.name, "group_name": ship.group.name if ship.group else None} for ship in ships]


@router.get("/doctrines")
def event_doctrine_search(
    q: str = Query("", max_length=255),
    _: User = Depends(require_events),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    statement = select(Doctrine).where(Doctrine.archived_at.is_(None), Doctrine.is_shared.is_(True))
    if q.strip():
        statement = statement.where(Doctrine.name.ilike(f"%{q.strip()}%"))
    rows = db.scalars(statement.order_by(func.lower(Doctrine.name)).limit(50)).all()
    return [{"id": row.id, "name": row.name, "description": row.description, "purpose": row.purpose or row.description,
             "priority_code": row.priority_code, "fitting_id": row.fitting_id, "external_url": row.external_url} for row in rows]


@router.get("/next")
def next_event(
    current_user: User = Depends(require_events),
    db: Session = Depends(get_db),
) -> dict[str, Any] | None:
    now = datetime.now(timezone.utc)
    candidates = db.scalars(
        select(Event)
        .options(*event_load_options())
        .where(Event.lifecycle_status.in_(["scheduled", "in_progress"]), Event.start_at >= now - timedelta(days=2))
        .order_by(Event.formup_at.asc().nullslast(), Event.start_at.asc())
        .limit(100)
    ).all()
    visible = visible_events(candidates, current_user, db)
    if not visible:
        return None
    return serialize_event(visible[0], current_user, db)


@router.get("/analytics", response_model=EventAnalyticsResponse)
def event_analytics(
    from_at: datetime = Query(..., alias="from"),
    to_at: datetime = Query(..., alias="to"),
    bucket: str = Query("day", pattern="^(day|week|month)$"),
    event_type: str | None = Query(default=None),
    include_cancelled: bool = False,
    current_user: User = Depends(require_events),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if not can_view_event_analytics(current_user, db):
        raise HTTPException(status_code=403, detail="Officer access is required for event analytics")
    from_at = utc_aware(from_at)
    to_at = utc_aware(to_at)
    if to_at <= from_at:
        raise HTTPException(status_code=422, detail="to must be after from")
    if to_at - from_at > timedelta(days=730):
        raise HTTPException(status_code=422, detail="Analytics range may not exceed 730 days")
    statement = (
        select(Event)
        .options(*event_load_options())
        .where(Event.start_at >= from_at, Event.start_at < to_at, Event.lifecycle_status != "draft")
    )
    if not include_cancelled:
        statement = statement.where(Event.lifecycle_status != "cancelled")
    if event_type:
        if event_type not in EVENT_CONSTANTS["event_types"]:
            raise HTTPException(status_code=422, detail="Unknown event type")
        statement = statement.where(Event.event_type == event_type)
    events = visible_events(db.scalars(statement.order_by(Event.start_at)).all(), current_user, db)
    return build_analytics(events, from_at, to_at, bucket)


def empty_counts() -> dict[str, Any]:
    return {
        "event_count": 0,
        "rsvp_going": 0,
        "rsvp_maybe": 0,
        "rsvp_declined": 0,
        "rsvp_waitlisted": 0,
        "registered_characters": 0,
        "attended_registered": 0,
        "attended_unregistered": 0,
        "no_show": 0,
        "excused": 0,
        "unmarked": 0,
    }


def period_start(value: datetime, bucket: str) -> datetime:
    value = utc_aware(value)
    if bucket == "month":
        return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    day = value.replace(hour=0, minute=0, second=0, microsecond=0)
    if bucket == "week":
        return day - timedelta(days=day.weekday())
    return day


def add_event_counts(target: dict[str, Any], event: Event) -> None:
    target["event_count"] += 1
    for response in event.responses:
        key = f"rsvp_{response.status}"
        if key in target:
            target[key] += 1
    registered = [row for row in event.registrations if row.registration_status == "registered"]
    target["registered_characters"] += len(registered)
    registered_ids = {row.id for row in registered}
    marked_registration_ids: set[int] = set()
    for attendance in event.attendance_entries:
        if attendance.registration_id in registered_ids:
            marked_registration_ids.add(attendance.registration_id)
            if attendance.attendance_status == "attended":
                target["attended_registered"] += 1
            elif attendance.attendance_status == "no_show":
                target["no_show"] += 1
            elif attendance.attendance_status == "excused":
                target["excused"] += 1
        elif attendance.attendance_status == "attended":
            target["attended_unregistered"] += 1
    target["unmarked"] += len(registered_ids - marked_registration_ids)


def finalize_counts(counts: dict[str, Any]) -> dict[str, Any]:
    numerator = counts["attended_registered"]
    denominator = counts["registered_characters"]
    return {
        **counts,
        "attendance_rate": {
            "numerator": numerator,
            "denominator": denominator,
            "percent": round(numerator / denominator * 100, 1) if denominator else None,
        },
    }


def _build_analytics_python(events: list[Event], from_at: datetime, to_at: datetime, bucket: str) -> dict[str, Any]:
    totals = empty_counts()
    by_type: dict[str, dict[str, Any]] = defaultdict(empty_counts)
    by_period: dict[datetime, dict[str, Any]] = defaultdict(empty_counts)
    for event in events:
        add_event_counts(totals, event)
        add_event_counts(by_type[event.event_type], event)
        add_event_counts(by_period[period_start(event.start_at, bucket)], event)
    return {
        "from_at": from_at,
        "to_at": to_at,
        "bucket": bucket,
        "totals": finalize_counts(totals),
        "by_event_type": [
            {"event_type": event_type, **finalize_counts(counts)}
            for event_type, counts in sorted(by_type.items())
        ],
        "series": [
            {"period_start": start, **finalize_counts(counts)}
            for start, counts in sorted(by_period.items())
        ],
    }


def response_engine_row(row: Any) -> dict[str, Any]:
    return {"user_id": int(getattr(row, "user_id", 0) or 0), "status": row.status}


def registration_engine_row(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "user_id": int(getattr(row, "user_id", 0) or 0),
        "registration_status": row.registration_status,
        "confirmation_status": getattr(row, "confirmation_status", None),
        "role_label": getattr(row, "custom_role", None) or getattr(row, "role_key", None) or "unassigned",
        "hull_label": getattr(row, "ship_name_snapshot", None) or getattr(row, "freeform_ship_description", None) or "Undecided",
        "doctrine_requirement_id": getattr(row, "doctrine_requirement_id", None),
    }


def attendance_engine_row(row: Any) -> dict[str, Any]:
    return {"registration_id": row.registration_id, "attendance_status": row.attendance_status}


def event_range_engine_payload(events: list[Event], from_at: datetime, to_at: datetime, bucket: str) -> dict[str, Any]:
    return {
        "schema_version": "eqm.event-analytics.v1",
        "operation": "range",
        "range": {
            "from_at": utc_aware(from_at).isoformat(),
            "to_at": utc_aware(to_at).isoformat(),
            "bucket": bucket,
            "events": [
                {
                    "event_type": event.event_type,
                    "start_at": utc_aware(event.start_at).isoformat(),
                    "responses": [response_engine_row(row) for row in event.responses],
                    "registrations": [registration_engine_row(row) for row in event.registrations],
                    "attendance": [attendance_engine_row(row) for row in event.attendance_entries],
                }
                for event in events
            ],
        },
    }


def build_analytics(events: list[Event], from_at: datetime, to_at: datetime, bucket: str) -> dict[str, Any]:
    from_at = utc_aware(from_at)
    to_at = utc_aware(to_at)
    return evaluate_event_analytics_with_engine(
        payload=event_range_engine_payload(events, from_at, to_at, bucket),
        python_result=lambda: _build_analytics_python(events, from_at, to_at, bucket),
    )


@router.get("")
def list_events(
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    event_type: str | None = None,
    lifecycle: str | None = None,
    mine: bool = False,
    limit: int = Query(250, ge=1, le=1000),
    current_user: User = Depends(require_events),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    statement = select(Event).options(*event_load_options())
    if from_at is not None:
        statement = statement.where(Event.start_at >= utc_aware(from_at))
    if to_at is not None:
        statement = statement.where(Event.start_at < utc_aware(to_at))
    if event_type:
        statement = statement.where(Event.event_type == event_type)
    if lifecycle:
        statement = statement.where(Event.lifecycle_status == lifecycle)
    if mine:
        statement = statement.where(
            or_(
                Event.created_by_user_id == current_user.id,
                Event.responses.any(EventUserResponse.user_id == current_user.id),
                Event.registrations.any(EventCharacterRegistration.user_id == current_user.id),
            )
        )
    candidates = db.scalars(statement.order_by(Event.start_at).limit(limit)).all()
    return [serialize_event(event, current_user, db) for event in visible_events(candidates, current_user, db)]


@router.post("", status_code=201)
def create_event(
    payload: EventCreate,
    current_user: User = Depends(require_events),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if not can_create_event(current_user, db):
        raise HTTPException(status_code=403, detail="Officer access is required to create events")
    scalar_values = payload.model_dump(
        exclude={"locations", "role_requirements", "doctrine_requirements"}
    )
    lead = db.get(EveCharacter, payload.lead_character_id) if payload.lead_character_id else None
    if payload.lead_character_id and lead is None:
        raise HTTPException(status_code=422, detail="Unknown lead character")
    if payload.doctrine_id and db.get(Doctrine, payload.doctrine_id) is None:
        raise HTTPException(status_code=422, detail="Unknown doctrine")
    if payload.audience_corporation_id and event_corporation_missing(payload.audience_corporation_id, db):
        raise HTTPException(status_code=422, detail="Unknown audience corporation")
    if payload.audience_alliance_id and event_alliance_missing(payload.audience_alliance_id, db):
        raise HTTPException(status_code=422, detail="Unknown audience alliance")
    event = Event(
        **scalar_values,
        created_by_user_id=current_user.id,
        lead_name_snapshot=lead.name if lead else None,
        published_at=datetime.now(timezone.utc) if payload.lifecycle_status != "draft" else None,
    )
    db.add(event)
    add_event_children(event, payload, current_user, db)
    record_audit_event(
        db,
        event_kind="event_created",
        title=f"Event created: {event.title}",
        body=f"{event.event_type}; {event.lifecycle_status}",
        actor_user=current_user,
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Event conflicts with an existing record") from exc
    return serialize_event(get_visible_event(event.id, current_user, db), current_user, db, detail=True)


def replace_event_locations(event: Event, location_inputs: list[Any], db: Session) -> None:
    event.locations.clear()
    db.flush()
    for location_input in location_inputs:
        if db.get(EveSystem, location_input.system_id) is None:
            raise HTTPException(status_code=422, detail=f"Unknown solar system {location_input.system_id}")
        location = db.get(Location, location_input.location_id) if location_input.location_id else None
        if location_input.location_id and location is None:
            raise HTTPException(status_code=422, detail=f"Unknown location {location_input.location_id}")
        if location is not None and location.system_id != location_input.system_id:
            raise HTTPException(status_code=422, detail="Selected location does not belong to the selected system")
        event.locations.append(
            EventLocation(
                **location_input.model_dump(exclude={"location_name_snapshot"}),
                location_name_snapshot=location_input.location_name_snapshot or (location.name if location else None),
            )
        )


def replace_role_requirements(event: Event, requirement_inputs: list[Any], db: Session) -> None:
    for doctrine_requirement in event.doctrine_requirements:
        doctrine_requirement.role_requirement_id = None
    event.role_requirements.clear()
    db.flush()
    event.role_requirements.extend(
        EventRoleRequirement(**requirement_input.model_dump())
        for requirement_input in requirement_inputs
    )


def replace_doctrine_requirements(
    event: Event,
    requirement_inputs: list[Any],
    current_user: User,
    db: Session,
) -> None:
    event.doctrine_requirements.clear()
    db.flush()
    for requirement_input in requirement_inputs:
        values = requirement_input.model_dump(exclude={"options"})
        if values.get("role_requirement_id"):
            role_requirement = db.get(EventRoleRequirement, values["role_requirement_id"])
            if role_requirement is None or role_requirement.event_id != event.id:
                raise HTTPException(status_code=422, detail="Role requirement does not belong to this event")
        requirement = EventDoctrineRequirement(**values)
        for option_input in requirement_input.options:
            if option_input.ship_type_id is not None:
                require_ship_type(option_input.ship_type_id, db)
            if option_input.fitting_id is not None:
                fitting = db.get(CharacterFitting, option_input.fitting_id)
                if fitting is None:
                    raise HTTPException(status_code=422, detail=f"Unknown fitting {option_input.fitting_id}")
                if not can_view_fitting(fitting, current_user, db):
                    raise HTTPException(status_code=403, detail="Doctrine fitting is not visible to the event manager")
            requirement.options.append(EventDoctrineRequirementOption(**option_input.model_dump()))
        event.doctrine_requirements.append(requirement)


@router.patch("/{event_id}")
def update_event(
    event_id: int,
    payload: EventPatch,
    current_user: User = Depends(require_events),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    event = get_visible_event(event_id, current_user, db)
    require_event_manager(event, current_user, db)
    if utc_aware(event.updated_at) != utc_aware(payload.expected_updated_at):
        raise HTTPException(status_code=409, detail="Event changed since this editor was opened")
    values = payload.model_dump(
        exclude_unset=True,
        exclude={"expected_updated_at", "locations", "role_requirements", "doctrine_requirements"},
    )
    for required_field in ("title", "event_type", "start_at"):
        if required_field in values and values[required_field] is None:
            raise HTTPException(status_code=422, detail=f"{required_field} may not be cleared")
    merged = {
        "start_at": event.start_at,
        "formup_at": event.formup_at,
        "end_at": event.end_at,
        "estimated_duration_minutes": event.estimated_duration_minutes,
        "participant_limit": event.participant_limit,
        "audience_kind": event.audience_kind,
        "audience_corporation_id": event.audience_corporation_id,
        "audience_alliance_id": event.audience_alliance_id,
        "lifecycle_status": event.lifecycle_status,
    }
    merged.update(values)
    locations_for_validation = (
        [location.model_dump() for location in payload.locations]
        if payload.locations is not None
        else [{"location_role": row.location_role} for row in event.locations]
    )
    validate_event_values(merged, locations_for_validation)
    doctrine_mode = values.get("doctrine_mode", event.doctrine_mode)
    doctrine_id = values.get("doctrine_id", event.doctrine_id)
    doctrine_name = values.get("doctrine_manual_name", event.doctrine_manual_name)
    doctrine_url = values.get("doctrine_external_url", event.doctrine_external_url)
    if doctrine_mode in {"required", "recommended"} and not (doctrine_id or doctrine_name or doctrine_url):
        raise HTTPException(status_code=422, detail="Doctrine reference or label is required")
    if doctrine_id and db.get(Doctrine, doctrine_id) is None:
        raise HTTPException(status_code=422, detail="Unknown doctrine")
    audience_corporation_id = merged.get("audience_corporation_id")
    audience_alliance_id = merged.get("audience_alliance_id")
    if audience_corporation_id and event_corporation_missing(audience_corporation_id, db):
        raise HTTPException(status_code=422, detail="Unknown audience corporation")
    if audience_alliance_id and event_alliance_missing(audience_alliance_id, db):
        raise HTTPException(status_code=422, detail="Unknown audience alliance")
    if "lead_character_id" in values:
        lead = db.get(EveCharacter, values["lead_character_id"]) if values["lead_character_id"] else None
        if values["lead_character_id"] and lead is None:
            raise HTTPException(status_code=422, detail="Unknown lead character")
        event.lead_name_snapshot = lead.name if lead else None
    for field, value in values.items():
        setattr(event, field, value)
    if payload.locations is not None:
        replace_event_locations(event, payload.locations, db)
    if payload.role_requirements is not None:
        replace_role_requirements(event, payload.role_requirements, db)
    if payload.doctrine_requirements is not None:
        if doctrine_mode == "required" and any(not requirement.options for requirement in payload.doctrine_requirements):
            raise HTTPException(status_code=422, detail="Every required-doctrine requirement needs at least one option")
        replace_doctrine_requirements(event, payload.doctrine_requirements, current_user, db)
    event.updated_at = datetime.now(timezone.utc)
    record_audit_event(
        db,
        event_kind="event_updated",
        title=f"Event updated: {event.title}",
        actor_user=current_user,
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Event update conflicts with another record") from exc
    return serialize_event(get_visible_event(event.id, current_user, db), current_user, db, detail=True)


@router.get("/{event_id}")
def event_detail(
    event_id: int,
    current_user: User = Depends(require_events),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return serialize_event(get_visible_event(event_id, current_user, db), current_user, db, detail=True)


@router.post("/{event_id}/transition")
def transition_event(
    event_id: int,
    payload: EventTransitionRequest,
    current_user: User = Depends(require_events),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    event = get_visible_event(event_id, current_user, db)
    require_event_manager(event, current_user, db)
    now = datetime.now(timezone.utc)
    if payload.lifecycle_status is not None:
        validate_lifecycle_transition(event, payload.lifecycle_status, has_formup=formup_location(event) is not None)
        event.lifecycle_status = payload.lifecycle_status
        if payload.lifecycle_status == "scheduled" and event.published_at is None:
            event.published_at = now
        elif payload.lifecycle_status == "completed":
            event.completed_at = now
        elif payload.lifecycle_status == "cancelled":
            event.cancelled_at = now
    if payload.registration_status is not None:
        event.registration_status = payload.registration_status
        if payload.registration_status == "locked":
            event.locked_at = now
            event.locked_by_user_id = current_user.id
        elif event.registration_status != "locked":
            event.locked_at = None
            event.locked_by_user_id = None
    record_audit_event(
        db,
        event_kind="event_transitioned",
        title=f"Event status updated: {event.title}",
        body=payload.reason,
        actor_user=current_user,
    )
    db.commit()
    return serialize_event(get_visible_event(event.id, current_user, db), current_user, db, detail=True)


def require_participant_mutation(event: Event, current_user: User, db: Session) -> None:
    if can_manage_event(event, current_user, db):
        if event.lifecycle_status in {"completed", "cancelled"}:
            raise HTTPException(status_code=409, detail="Completed and cancelled event registrations are immutable")
        return
    if event.lifecycle_status not in {"draft", "scheduled"} or event.registration_status != "open":
        raise HTTPException(status_code=409, detail="Event registration is not open")


@router.put("/{event_id}/rsvp")
def upsert_rsvp(
    event_id: int,
    payload: EventRsvpUpsert,
    current_user: User = Depends(require_events),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    event = get_visible_event(event_id, current_user, db)
    require_participant_mutation(event, current_user, db)
    response = db.scalar(
        select(EventUserResponse).where(
            EventUserResponse.event_id == event.id,
            EventUserResponse.user_id == current_user.id,
        )
    )
    if response is None:
        response = EventUserResponse(event_id=event.id, user_id=current_user.id, status=payload.status)
        db.add(response)
    response.status = payload.status
    response.notes = payload.notes
    record_audit_event(
        db,
        event_kind="event_rsvp_updated",
        title=f"RSVP updated: {event.title}",
        body=payload.status,
        actor_user=current_user,
    )
    db.commit()
    return {"event_id": event.id, "status": response.status, "notes": response.notes}


@router.delete("/{event_id}/rsvp")
def delete_rsvp(
    event_id: int,
    current_user: User = Depends(require_events),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    event = get_visible_event(event_id, current_user, db)
    require_participant_mutation(event, current_user, db)
    if db.scalar(
        select(EventCharacterRegistration.id).where(
            EventCharacterRegistration.event_id == event.id,
            EventCharacterRegistration.user_id == current_user.id,
        )
    ):
        raise HTTPException(status_code=409, detail="Remove character registrations before removing the RSVP")
    response = db.scalar(
        select(EventUserResponse).where(
            EventUserResponse.event_id == event.id,
            EventUserResponse.user_id == current_user.id,
        )
    )
    if response is not None:
        db.delete(response)
        db.commit()
    return {"ok": True}


@router.get("/{event_id}/registration-options")
def registration_options(
    event_id: int,
    character_id: int | None = Query(default=None, gt=0),
    current_user: User = Depends(require_events),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    event = get_visible_event(event_id, current_user, db)
    characters = active_owned_characters(current_user, db)
    excluded_ids = {row.character_id for row in event.registrations if row.user_id == current_user.id}
    chosen = get_active_owned_character(character_id, current_user, db) if character_id else None
    fittings = (
        db.scalars(
            select(CharacterFitting)
            .options(selectinload(CharacterFitting.ship_type))
            .where(CharacterFitting.character_id == chosen.id)
            .order_by(CharacterFitting.name)
        ).all()
        if chosen
        else []
    )
    return {
        "characters": [
            {
                "id": character.id,
                "character_id": character.character_id,
                "name": character.name,
                "portrait_url": character.portrait_url,
                "already_registered": character.id in excluded_ids,
            }
            for character in characters
        ],
        "fittings": [
            {"id": fitting.id, "name": fitting.name, "ship_type_id": fitting.ship_type_id, "ship_name": fitting.ship_type.name}
            for fitting in fittings
        ],
        "roles": EVENT_CONSTANTS["fleet_roles"],
        "doctrine_requirements": serialize_event(event, current_user, db, detail=True)["doctrine_requirements"],
    }


@router.post("/{event_id}/registrations", status_code=201)
def create_registration(
    event_id: int,
    payload: EventRegistrationCreate,
    current_user: User = Depends(require_events),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    event = get_visible_event(event_id, current_user, db)
    require_participant_mutation(event, current_user, db)
    character = get_active_owned_character(payload.character_id, current_user, db)
    if db.scalar(
        select(EventCharacterRegistration.id).where(
            EventCharacterRegistration.event_id == event.id,
            EventCharacterRegistration.user_id == current_user.id,
            EventCharacterRegistration.character_id == character.id,
        )
    ):
        raise HTTPException(status_code=409, detail="Character is already registered for this event")
    fitting = db.get(CharacterFitting, payload.saved_fitting_id) if payload.saved_fitting_id else None
    if fitting is not None and fitting.character_id != character.id:
        raise HTTPException(status_code=403, detail="Saved fitting does not belong to the selected character")
    if payload.saved_fitting_id and fitting is None:
        raise HTTPException(status_code=422, detail="Saved fitting not found")
    ship = require_ship_type(payload.ship_type_id, db) if payload.ship_type_id else None
    if fitting and ship is None:
        ship = require_ship_type(fitting.ship_type_id, db)
    if payload.doctrine_requirement_id:
        requirement = db.get(EventDoctrineRequirement, payload.doctrine_requirement_id)
        if requirement is None or requirement.event_id != event.id:
            raise HTTPException(status_code=422, detail="Doctrine requirement does not belong to this event")
    if payload.doctrine_option_id:
        option = db.get(EventDoctrineRequirementOption, payload.doctrine_option_id)
        if option is None or option.requirement.event_id != event.id:
            raise HTTPException(status_code=422, detail="Doctrine option does not belong to this event")
    status = payload.registration_status
    if status == "registered" and event.participant_limit and event.limit_basis == "characters":
        registered_count = db.scalar(
            select(func.count()).select_from(EventCharacterRegistration).where(
                EventCharacterRegistration.event_id == event.id,
                EventCharacterRegistration.registration_status == "registered",
            )
        ) or 0
        if registered_count >= event.participant_limit:
            status = "waitlisted"
    registration = EventCharacterRegistration(
        event_id=event.id,
        user_id=current_user.id,
        character_id=character.id,
        character_eve_id_snapshot=character.character_id,
        character_name_snapshot=character.name,
        corporation_name_snapshot=character.corporation.name if character.corporation else None,
        alliance_name_snapshot=character.alliance.name if character.alliance else None,
        registration_status=status,
        confirmation_status=payload.confirmation_status,
        planned_ship_source=payload.planned_ship_source,
        ship_type_id=ship.type_id if ship else None,
        ship_name_snapshot=ship.name if ship else None,
        saved_fitting_id=fitting.id if fitting else None,
        fitting_name_snapshot=fitting.name if fitting else None,
        fitting_updated_at_snapshot=fitting.updated_at if fitting else None,
        doctrine_requirement_id=payload.doctrine_requirement_id,
        doctrine_option_id=payload.doctrine_option_id,
        role_key=payload.role_key,
        custom_role=payload.custom_role,
        freeform_ship_description=payload.freeform_ship_description,
        notes=payload.notes,
    )
    db.add(registration)
    record_audit_event(
        db,
        event_kind="event_character_registered",
        title=f"Character registered: {character.name}",
        body=event.title,
        actor_user=current_user,
        character=character,
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Character is already registered") from exc
    db.refresh(registration)
    return serialize_registration(registration)


def get_event_registration(event: Event, registration_id: int, current_user: User, db: Session) -> EventCharacterRegistration:
    registration = db.get(EventCharacterRegistration, registration_id)
    if registration is None or registration.event_id != event.id:
        raise HTTPException(status_code=404, detail="Registration not found")
    if registration.user_id != current_user.id and not can_manage_event(event, current_user, db):
        raise HTTPException(status_code=403, detail="Registration ownership or event manager access is required")
    return registration


@router.patch("/{event_id}/registrations/{registration_id}")
def update_registration(
    event_id: int,
    registration_id: int,
    payload: EventRegistrationUpdate,
    current_user: User = Depends(require_events),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    event = get_visible_event(event_id, current_user, db)
    require_participant_mutation(event, current_user, db)
    registration = get_event_registration(event, registration_id, current_user, db)
    values = payload.model_dump(exclude_unset=True)
    if "registration_status" in values and not can_manage_event(event, current_user, db):
        raise HTTPException(status_code=403, detail="Only event managers may promote or waitlist registrations")
    if "saved_fitting_id" in values:
        fitting = db.get(CharacterFitting, values["saved_fitting_id"]) if values["saved_fitting_id"] else None
        if fitting is not None and fitting.character_id != registration.character_id:
            raise HTTPException(status_code=403, detail="Saved fitting does not belong to the registered character")
        if values["saved_fitting_id"] and fitting is None:
            raise HTTPException(status_code=422, detail="Saved fitting not found")
        registration.saved_fitting_id = fitting.id if fitting else None
        registration.fitting_name_snapshot = fitting.name if fitting else None
        registration.fitting_updated_at_snapshot = fitting.updated_at if fitting else None
        if fitting and "ship_type_id" not in values:
            ship = require_ship_type(fitting.ship_type_id, db)
            registration.ship_type_id = ship.type_id
            registration.ship_name_snapshot = ship.name
    if "ship_type_id" in values:
        ship = require_ship_type(values["ship_type_id"], db) if values["ship_type_id"] else None
        registration.ship_type_id = ship.type_id if ship else None
        registration.ship_name_snapshot = ship.name if ship else None
    if values.get("doctrine_requirement_id"):
        requirement = db.get(EventDoctrineRequirement, values["doctrine_requirement_id"])
        if requirement is None or requirement.event_id != event.id:
            raise HTTPException(status_code=422, detail="Doctrine requirement does not belong to this event")
    if values.get("doctrine_option_id"):
        option = db.get(EventDoctrineRequirementOption, values["doctrine_option_id"])
        if option is None or option.requirement.event_id != event.id:
            raise HTTPException(status_code=422, detail="Doctrine option does not belong to this event")
    handled = {"saved_fitting_id", "ship_type_id"}
    for field, value in values.items():
        if field not in handled:
            setattr(registration, field, value)
    record_audit_event(
        db,
        event_kind="event_registration_updated",
        title=f"Registration updated: {registration.character_name_snapshot}",
        body=event.title,
        actor_user=current_user,
    )
    db.commit()
    db.refresh(registration)
    return serialize_registration(registration)


@router.delete("/{event_id}/registrations/{registration_id}")
def delete_registration(
    event_id: int,
    registration_id: int,
    current_user: User = Depends(require_events),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    event = get_visible_event(event_id, current_user, db)
    require_participant_mutation(event, current_user, db)
    registration = get_event_registration(event, registration_id, current_user, db)
    label = registration.character_name_snapshot
    db.delete(registration)
    record_audit_event(
        db,
        event_kind="event_registration_removed",
        title=f"Registration removed: {label}",
        body=event.title,
        actor_user=current_user,
    )
    db.commit()
    return {"ok": True}


def _event_composition_python(event: Event) -> dict[str, Any]:
    attendance_by_registration = {
        row.registration_id: row for row in event.attendance_entries if row.registration_id is not None
    }
    role_counts: dict[str, int] = defaultdict(int)
    hull_counts: dict[str, int] = defaultdict(int)
    doctrine_counts: dict[int, int] = defaultdict(int)
    status_counts: dict[str, int] = defaultdict(int)
    confirmation_counts: dict[str, int] = defaultdict(int)
    for registration in event.registrations:
        status_counts[registration.registration_status] += 1
        confirmation_counts[registration.confirmation_status] += 1
        role_counts[registration.custom_role or registration.role_key or "unassigned"] += 1
        hull_counts[registration.ship_name_snapshot or registration.freeform_ship_description or "Undecided"] += 1
        if registration.doctrine_requirement_id:
            doctrine_counts[registration.doctrine_requirement_id] += 1
    response_user_ids = {response.user_id for response in event.responses if response.status in {"going", "maybe"}}
    registered_user_ids = {registration.user_id for registration in event.registrations}
    response_counts: dict[str, int] = defaultdict(int)
    for response in event.responses:
        response_counts[response.status] += 1
    return {
        "totals": {
            "rsvp": dict(response_counts),
            "registration": dict(status_counts),
            "confirmation": dict(confirmation_counts),
            "attendance": {
                "attended": sum(row.attendance_status == "attended" for row in event.attendance_entries),
                "no_show": sum(row.attendance_status == "no_show" for row in event.attendance_entries),
                "excused": sum(row.attendance_status == "excused" for row in event.attendance_entries),
                "unmarked": sum(registration.id not in attendance_by_registration for registration in event.registrations),
            },
        },
        "roles": [{"label": label, "count": count} for label, count in sorted(role_counts.items())],
        "hulls": [{"label": label, "count": count} for label, count in sorted(hull_counts.items())],
        "role_requirements": [
            {
                "id": requirement.id,
                "label": requirement.custom_label or requirement.role_key,
                "requested": requirement.requested_quantity,
                "registered": role_counts.get(requirement.custom_label or requirement.role_key, 0),
                "remaining": max(0, requirement.requested_quantity - role_counts.get(requirement.custom_label or requirement.role_key, 0)),
            }
            for requirement in sorted(event.role_requirements, key=lambda row: row.sort_order)
        ],
        "doctrine_requirements": [
            {
                "id": requirement.id,
                "label": requirement.label,
                "requested": requirement.requested_quantity,
                "registered": doctrine_counts.get(requirement.id, 0),
                "remaining": max(0, requirement.requested_quantity - doctrine_counts.get(requirement.id, 0)),
            }
            for requirement in sorted(event.doctrine_requirements, key=lambda row: row.sort_order)
        ],
        "users_without_characters": len(response_user_ids - registered_user_ids),
    }


def event_composition_engine_payload(event: Event) -> dict[str, Any]:
    return {
        "schema_version": "eqm.event-analytics.v1",
        "operation": "composition",
        "composition": {
            "responses": [response_engine_row(row) for row in event.responses],
            "registrations": [registration_engine_row(row) for row in event.registrations],
            "attendance": [attendance_engine_row(row) for row in event.attendance_entries],
            "role_requirements": [
                {
                    "id": row.id,
                    "label": row.custom_label or row.role_key,
                    "requested": row.requested_quantity,
                    "sort_order": row.sort_order,
                }
                for row in event.role_requirements
            ],
            "doctrine_requirements": [
                {"id": row.id, "label": row.label, "requested": row.requested_quantity, "sort_order": row.sort_order}
                for row in event.doctrine_requirements
            ],
        },
    }


@router.get("/{event_id}/composition")
def event_composition(
    event_id: int,
    current_user: User = Depends(require_events),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    event = get_visible_event(event_id, current_user, db)
    full_detail = can_view_full_composition(event, current_user, db)
    attendance_by_registration = {
        row.registration_id: row for row in event.attendance_entries if row.registration_id is not None
    }
    composition = evaluate_event_analytics_with_engine(
        payload=event_composition_engine_payload(event),
        python_result=lambda: _event_composition_python(event),
    )
    payload: dict[str, Any] = {
        "event_id": event.id,
        "identity_visible": full_detail,
        **composition,
    }
    if full_detail:
        response_user_ids = {response.user_id for response in event.responses if response.status in {"going", "maybe"}}
        registered_user_ids = {registration.user_id for registration in event.registrations}
        payload["registrations"] = [
            {
                **serialize_registration(registration),
                "user_name": registration.user.display_name if registration.user else None,
                "attendance": serialize_attendance(attendance_by_registration[registration.id])
                if registration.id in attendance_by_registration
                else None,
            }
            for registration in event.registrations
        ]
        payload["unregistered_attendees"] = [
            serialize_attendance(row) for row in event.attendance_entries if row.registration_id is None
        ]
        payload["responses_without_characters"] = [
            {"user_id": response.user_id, "user_name": response.user.display_name if response.user else None, "status": response.status}
            for response in event.responses
            if response.user_id in response_user_ids - registered_user_ids
        ]
    return payload


@router.get("/{event_id}/attendance")
def attendance_roster(
    event_id: int,
    current_user: User = Depends(require_events),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    event = get_visible_event(event_id, current_user, db)
    require_attendance_recorder(event, current_user, db)
    attendance_by_registration = {
        row.registration_id: row for row in event.attendance_entries if row.registration_id is not None
    }
    return {
        "event_id": event.id,
        "eligible": True,
        "registrations": [
            {
                **serialize_registration(registration),
                "attendance": serialize_attendance(attendance_by_registration[registration.id])
                if registration.id in attendance_by_registration
                else None,
                "derived_attendance_status": attendance_by_registration[registration.id].attendance_status
                if registration.id in attendance_by_registration
                else "unmarked",
            }
            for registration in event.registrations
        ],
        "unregistered_attendees": [
            serialize_attendance(row) for row in event.attendance_entries if row.registration_id is None
        ],
    }


@router.put("/{event_id}/attendance/registrations/{registration_id}")
def mark_registration_attendance(
    event_id: int,
    registration_id: int,
    payload: AttendanceRegistrationUpdate,
    current_user: User = Depends(require_events),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    event = get_visible_event(event_id, current_user, db)
    require_attendance_recorder(event, current_user, db)
    registration = db.get(EventCharacterRegistration, registration_id)
    if registration is None or registration.event_id != event.id:
        raise HTTPException(status_code=404, detail="Registration not found")
    entry = db.scalar(
        select(EventAttendanceEntry).where(
            EventAttendanceEntry.event_id == event.id,
            EventAttendanceEntry.registration_id == registration.id,
        )
    )
    if entry is None:
        entry = EventAttendanceEntry(
            event_id=event.id,
            registration_id=registration.id,
            attendee_source="registration",
            display_name_snapshot=registration.character_name_snapshot,
            linked_user_id=registration.user_id,
            character_id=registration.character_id,
            character_eve_id_snapshot=registration.character_eve_id_snapshot,
            corporation_name_snapshot=registration.corporation_name_snapshot,
            alliance_name_snapshot=registration.alliance_name_snapshot,
            recorded_by_user_id=current_user.id,
        )
        db.add(entry)
    entry.attendance_status = payload.attendance_status
    entry.checked_in_at = payload.checked_in_at
    entry.notes = payload.notes
    entry.recorded_by_user_id = current_user.id
    record_audit_event(
        db,
        event_kind="event_attendance_recorded",
        title=f"Attendance recorded: {registration.character_name_snapshot}",
        body=f"{event.title}: {payload.attendance_status}",
        actor_user=current_user,
    )
    db.commit()
    db.refresh(entry)
    return serialize_attendance(entry)


@router.post("/{event_id}/attendance", status_code=201)
def add_manual_attendance(
    event_id: int,
    payload: AttendanceManualCreate,
    current_user: User = Depends(require_events),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    event = get_visible_event(event_id, current_user, db)
    require_attendance_recorder(event, current_user, db)
    character = db.get(EveCharacter, payload.character_id) if payload.character_id else None
    if payload.attendee_source == "linked_character" and character is None:
        raise HTTPException(status_code=422, detail="Linked character not found")
    eve_character_id = character.character_id if character else payload.character_eve_id
    display_name = character.name if character else payload.display_name
    entry = EventAttendanceEntry(
        event_id=event.id,
        attendee_source=payload.attendee_source,
        attendance_status="attended",
        linked_user_id=character.owner_user_id if character else None,
        character_id=character.id if character else None,
        character_eve_id_snapshot=eve_character_id,
        display_name_snapshot=display_name or "Unknown attendee",
        corporation_name_snapshot=(character.corporation.name if character and character.corporation else payload.corporation_name),
        alliance_name_snapshot=(character.alliance.name if character and character.alliance else payload.alliance_name),
        checked_in_at=payload.checked_in_at,
        notes=payload.notes,
        recorded_by_user_id=current_user.id,
    )
    db.add(entry)
    record_audit_event(
        db,
        event_kind="event_attendance_added",
        title=f"Unregistered attendee added: {entry.display_name_snapshot}",
        body=event.title,
        actor_user=current_user,
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Attendee is already recorded for this event") from exc
    db.refresh(entry)
    return serialize_attendance(entry)


@router.patch("/{event_id}/attendance/{attendance_id}")
def update_attendance(
    event_id: int,
    attendance_id: int,
    payload: AttendanceEntryUpdate,
    current_user: User = Depends(require_events),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    event = get_visible_event(event_id, current_user, db)
    require_attendance_recorder(event, current_user, db)
    entry = db.get(EventAttendanceEntry, attendance_id)
    if entry is None or entry.event_id != event.id:
        raise HTTPException(status_code=404, detail="Attendance entry not found")
    values = payload.model_dump(exclude_unset=True)
    if entry.attendee_source == "registration" and any(
        key in values for key in {"display_name", "corporation_name", "alliance_name"}
    ):
        raise HTTPException(status_code=409, detail="Registration identity snapshots cannot be edited here")
    field_map = {
        "display_name": "display_name_snapshot",
        "corporation_name": "corporation_name_snapshot",
        "alliance_name": "alliance_name_snapshot",
    }
    for key, value in values.items():
        setattr(entry, field_map.get(key, key), value)
    entry.recorded_by_user_id = current_user.id
    db.commit()
    db.refresh(entry)
    return serialize_attendance(entry)


@router.delete("/{event_id}/attendance/{attendance_id}")
def delete_attendance(
    event_id: int,
    attendance_id: int,
    current_user: User = Depends(require_events),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    event = get_visible_event(event_id, current_user, db)
    require_attendance_recorder(event, current_user, db)
    entry = db.get(EventAttendanceEntry, attendance_id)
    if entry is None or entry.event_id != event.id:
        raise HTTPException(status_code=404, detail="Attendance entry not found")
    label = entry.display_name_snapshot
    db.delete(entry)
    record_audit_event(
        db,
        event_kind="event_attendance_removed",
        title=f"Attendance reset: {label}",
        body=event.title,
        actor_user=current_user,

    )
    db.commit()
    return {"ok": True}
