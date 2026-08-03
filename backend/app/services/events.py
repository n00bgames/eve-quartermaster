from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EsiToken, EveCharacter, Event, EventCharacterRegistration, EventUserResponse, User
from app.schemas.events import (
    AnalyticsBucket,
    AttendanceSource,
    AttendanceStatus,
    AudienceKind,
    CharacterRegistrationStatus,
    CompositionVisibility,
    ConfirmationStatus,
    DoctrineMode,
    EventLifecycle,
    EventRegistrationState,
    EventType,
    FleetRole,
    LimitBasis,
    LocationRole,
    RsvpStatus,
    ShipSource,
)
from app.services.permissions import ROLE_RANK, can_view_section, role_rank


EVENT_TYPES = ["fleet", "mining", "logistics", "mission", "industry", "training", "social", "other"]
EVENT_LIFECYCLES = ["draft", "scheduled", "in_progress", "completed", "cancelled"]
EVENT_REGISTRATION_STATES = ["open", "closed", "locked"]
DOCTRINE_MODES = ["required", "recommended", "none", "assigned", "freeform"]
AUDIENCE_KINDS = ["all_members", "corporation", "alliance", "invite_only"]
COMPOSITION_VISIBILITIES = ["participants", "corporation", "alliance", "managers"]
RSVP_STATUSES = ["going", "maybe", "declined", "waitlisted"]
CHARACTER_REGISTRATION_STATUSES = ["registered", "waitlisted"]
CONFIRMATION_STATUSES = ["confirmed", "tentative"]
SHIP_SOURCES = ["doctrine", "saved_fitting", "sde_hull", "freeform", "undecided"]
LOCATION_ROLES = ["formup", "destination", "route"]
ATTENDANCE_STATUSES = ["attended", "no_show", "excused"]
ATTENDANCE_SOURCES = ["registration", "linked_character", "external_character", "public_guest"]
ANALYTICS_BUCKETS = ["day", "week", "month"]
LIMIT_BASES = ["users", "characters"]
FLEET_ROLES = [
    "fleet_commander",
    "logistics",
    "command_bursts",
    "tackle",
    "scout",
    "electronic_warfare",
    "mainline_dps",
    "capital",
    "cyno",
    "hauler",
    "miner",
    "booster",
    "salvager",
    "other",
]

EVENT_CONSTANTS: dict[str, list[str]] = {
    "event_types": EVENT_TYPES,
    "lifecycle_statuses": EVENT_LIFECYCLES,
    "registration_states": EVENT_REGISTRATION_STATES,
    "doctrine_modes": DOCTRINE_MODES,
    "audience_kinds": AUDIENCE_KINDS,
    "composition_visibilities": COMPOSITION_VISIBILITIES,
    "rsvp_statuses": RSVP_STATUSES,
    "character_registration_statuses": CHARACTER_REGISTRATION_STATUSES,
    "confirmation_statuses": CONFIRMATION_STATUSES,
    "ship_sources": SHIP_SOURCES,
    "location_roles": LOCATION_ROLES,
    "attendance_statuses": ATTENDANCE_STATUSES,
    "attendance_sources": ATTENDANCE_SOURCES,
    "analytics_buckets": ANALYTICS_BUCKETS,
    "limit_bases": LIMIT_BASES,
    "fleet_roles": FLEET_ROLES,
}

LIFECYCLE_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"scheduled", "cancelled"},
    "scheduled": {"in_progress", "completed", "cancelled"},
    "in_progress": {"completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}


def utc_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def require_events_access(user: User, db: Session) -> User:
    if not can_view_section(user, "calendar_events", db):
        raise HTTPException(status_code=403, detail="Calendar and Events access is required")
    return user


def can_create_event(user: User, db: Session) -> bool:
    return can_view_section(user, "calendar_events", db) and role_rank(user, db) >= ROLE_RANK["officer"]


def can_manage_event(event: Event, user: User, db: Session) -> bool:
    if not can_view_section(user, "calendar_events", db):
        return False
    if role_rank(user, db) >= ROLE_RANK["director"]:
        return True
    return role_rank(user, db) >= ROLE_RANK["officer"] and event.created_by_user_id == user.id


def active_owned_characters(user: User, db: Session) -> list[EveCharacter]:
    return list(
        db.scalars(
            select(EveCharacter)
            .join(EsiToken, EsiToken.character_id == EveCharacter.id)
            .where(
                EveCharacter.owner_user_id == user.id,
                EsiToken.user_id == user.id,
                EsiToken.revoked_at.is_(None),
            )
            .distinct()
            .order_by(EveCharacter.name)
        ).all()
    )


def get_active_owned_character(character_id: int, user: User, db: Session) -> EveCharacter:
    character = db.scalar(
        select(EveCharacter)
        .join(EsiToken, EsiToken.character_id == EveCharacter.id)
        .where(
            EveCharacter.id == character_id,
            EveCharacter.owner_user_id == user.id,
            EsiToken.user_id == user.id,
            EsiToken.revoked_at.is_(None),
        )
        .limit(1)
    )
    if character is None:
        raise HTTPException(status_code=403, detail="Character is not actively authenticated for this user")
    return character


def active_affiliations(user: User, db: Session) -> tuple[set[int], set[int]]:
    characters = active_owned_characters(user, db)
    return (
        {character.corporation_id for character in characters if character.corporation_id is not None},
        {character.alliance_id for character in characters if character.alliance_id is not None},
    )


def event_is_visible(event: Event, user: User, db: Session) -> bool:
    if not can_view_section(user, "calendar_events", db):
        return False
    if role_rank(user, db) >= ROLE_RANK["director"] or event.created_by_user_id == user.id:
        return True
    if event.audience_kind == "all_members":
        return True
    corporations, alliances = active_affiliations(user, db)
    if event.audience_kind == "corporation":
        return event.audience_corporation_id in corporations
    if event.audience_kind == "alliance":
        return event.audience_alliance_id in alliances
    if event.audience_kind == "invite_only":
        response = db.scalar(
            select(EventUserResponse.id).where(
                EventUserResponse.event_id == event.id,
                EventUserResponse.user_id == user.id,
            )
        )
        registration = db.scalar(
            select(EventCharacterRegistration.id).where(
                EventCharacterRegistration.event_id == event.id,
                EventCharacterRegistration.user_id == user.id,
            )
        )
        return response is not None or registration is not None
    return False


def visible_events(events: Iterable[Event], user: User, db: Session) -> list[Event]:
    return [event for event in events if event_is_visible(event, user, db)]


def effective_event_end(event: Event) -> datetime | None:
    if event.end_at is not None:
        return utc_aware(event.end_at)
    if event.estimated_duration_minutes is not None:
        return utc_aware(event.start_at) + timedelta(minutes=event.estimated_duration_minutes)
    if event.lifecycle_status == "completed":
        return utc_aware(event.completed_at or event.start_at)
    return None


def attendance_is_open(event: Event, *, now: datetime | None = None) -> bool:
    if event.lifecycle_status in {"draft", "cancelled"}:
        return False
    if event.lifecycle_status == "completed":
        return True
    end_at = effective_event_end(event)
    return end_at is not None and end_at <= utc_aware(now or datetime.now(timezone.utc))


def can_record_attendance(event: Event, user: User, db: Session, *, now: datetime | None = None) -> bool:
    return (
        can_view_section(user, "calendar_events", db)
        and role_rank(user, db) >= ROLE_RANK["officer"]
        and event_is_visible(event, user, db)
        and attendance_is_open(event, now=now)
    )


def can_view_event_analytics(user: User, db: Session) -> bool:
    return can_view_section(user, "calendar_events", db) and role_rank(user, db) >= ROLE_RANK["officer"]


def can_view_full_composition(event: Event, user: User, db: Session) -> bool:
    if can_manage_event(event, user, db) or can_record_attendance(event, user, db):
        return True
    own_response = db.scalar(
        select(EventUserResponse.status).where(
            EventUserResponse.event_id == event.id,
            EventUserResponse.user_id == user.id,
        )
    )
    own_registration = db.scalar(
        select(EventCharacterRegistration.id).where(
            EventCharacterRegistration.event_id == event.id,
            EventCharacterRegistration.user_id == user.id,
        )
    )
    if event.composition_visibility == "participants":
        return own_response in {"going", "maybe", "waitlisted"} or own_registration is not None
    corporations, alliances = active_affiliations(user, db)
    if event.composition_visibility == "corporation":
        return event.audience_corporation_id in corporations
    if event.composition_visibility == "alliance":
        return event.audience_alliance_id in alliances
    return False


def validate_event_values(values: Mapping[str, Any], locations: Iterable[Mapping[str, Any]] | None = None) -> None:
    start_at = values.get("start_at")
    formup_at = values.get("formup_at")
    end_at = values.get("end_at")
    duration = values.get("estimated_duration_minutes")
    if start_at is None:
        raise HTTPException(status_code=422, detail="start_at is required")
    if formup_at is not None and utc_aware(formup_at) > utc_aware(start_at):
        raise HTTPException(status_code=422, detail="formup_at must be before or equal to start_at")
    if end_at is not None and utc_aware(end_at) <= utc_aware(start_at):
        raise HTTPException(status_code=422, detail="end_at must be after start_at")
    if end_at is not None and duration is not None:
        raise HTTPException(status_code=422, detail="Provide end_at or estimated_duration_minutes, not both")
    if duration is not None and not 1 <= int(duration) <= 43200:
        raise HTTPException(status_code=422, detail="estimated_duration_minutes must be between 1 and 43200")
    if values.get("participant_limit") is not None and int(values["participant_limit"]) <= 0:
        raise HTTPException(status_code=422, detail="participant_limit must be positive")
    if values.get("audience_kind") == "corporation" and values.get("audience_corporation_id") is None:
        raise HTTPException(status_code=422, detail="Corporation audience requires audience_corporation_id")
    if values.get("audience_kind") == "alliance" and values.get("audience_alliance_id") is None:
        raise HTTPException(status_code=422, detail="Alliance audience requires audience_alliance_id")
    location_rows = list(locations or [])
    formup_count = sum(row.get("location_role") == "formup" for row in location_rows)
    destination_count = sum(row.get("location_role") == "destination" for row in location_rows)
    if formup_count > 1 or destination_count > 1:
        raise HTTPException(status_code=422, detail="Only one formup and one destination are allowed")
    if values.get("lifecycle_status") != "draft" and formup_count != 1:
        raise HTTPException(status_code=422, detail="A formup location is required before scheduling")


def validate_lifecycle_transition(event: Event, next_status: str, *, has_formup: bool) -> None:
    if next_status == event.lifecycle_status:
        return
    allowed = LIFECYCLE_TRANSITIONS.get(event.lifecycle_status, set())
    if next_status not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot transition an event from {event.lifecycle_status} to {next_status}",
        )
    if next_status == "scheduled" and not has_formup:
        raise HTTPException(status_code=409, detail="A formup location is required before scheduling")


def require_event_manager(event: Event, user: User, db: Session) -> None:
    if not can_manage_event(event, user, db):
        raise HTTPException(status_code=403, detail="Event manager access is required")


def require_attendance_recorder(event: Event, user: User, db: Session, *, now: datetime | None = None) -> None:
    if not can_record_attendance(event, user, db, now=now):
        raise HTTPException(status_code=403, detail="Attendance may only be recorded by authorized staff after the event")
