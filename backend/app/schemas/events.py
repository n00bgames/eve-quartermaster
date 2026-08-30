from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator


EventType = Literal["fleet", "mining", "logistics", "mission", "industry", "training", "social", "other"]
EventLifecycle = Literal["draft", "scheduled", "in_progress", "completed", "cancelled"]
EventRegistrationState = Literal["open", "closed", "locked"]
DoctrineMode = Literal["required", "recommended", "none", "assigned", "freeform"]
AudienceKind = Literal["all_members", "corporation", "alliance", "invite_only"]
CompositionVisibility = Literal["participants", "corporation", "alliance", "managers"]
RsvpStatus = Literal["going", "maybe", "declined", "waitlisted"]
CharacterRegistrationStatus = Literal["registered", "waitlisted"]
ConfirmationStatus = Literal["confirmed", "tentative"]
ShipSource = Literal["doctrine", "saved_fitting", "sde_hull", "freeform", "undecided"]
LocationRole = Literal["formup", "destination", "route"]
AttendanceStatus = Literal["attended", "no_show", "excused"]
AttendanceSource = Literal["linked_character", "external_character", "public_guest"]
AnalyticsBucket = Literal["day", "week", "month"]
LimitBasis = Literal["users", "characters"]
FleetRole = Literal[
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

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def _require_aware(value: datetime | None, field_name: str) -> datetime | None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ValueError(f"{field_name} must include a timezone")
    return value


def _clean_url(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if not cleaned.lower().startswith(("https://", "http://")):
        raise ValueError("URL must use http or https")
    return cleaned


class EventLocationInput(BaseModel):
    location_role: LocationRole
    sort_order: int = Field(default=0, ge=0)
    system_id: int = Field(gt=0)
    location_id: int | None = Field(default=None, gt=0)
    eve_location_id: int | None = Field(default=None, gt=0)
    location_name_snapshot: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)


class EventRoleRequirementInput(BaseModel):
    role_key: FleetRole
    custom_label: str | None = Field(default=None, max_length=120)
    requested_quantity: int = Field(gt=0)
    notes: str | None = Field(default=None, max_length=500)
    sort_order: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def require_custom_label(self) -> "EventRoleRequirementInput":
        if self.role_key == "other" and not (self.custom_label or "").strip():
            raise ValueError("custom_label is required for the other role")
        return self


class EventDoctrineOptionInput(BaseModel):
    ship_type_id: int | None = Field(default=None, gt=0)
    fitting_id: int | None = Field(default=None, gt=0)
    manual_name_snapshot: str | None = Field(default=None, max_length=255)
    is_primary: bool = False
    sort_order: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def require_identity(self) -> "EventDoctrineOptionInput":
        if self.ship_type_id is None and self.fitting_id is None and not (self.manual_name_snapshot or "").strip():
            raise ValueError("A doctrine option requires a ship, fitting, or manual name")
        return self


class EventDoctrineRequirementInput(BaseModel):
    role_requirement_id: int | None = Field(default=None, gt=0)
    label: NonBlank = Field(max_length=255)
    requested_quantity: int = Field(gt=0)
    notes: str | None = Field(default=None, max_length=500)
    sort_order: int = Field(default=0, ge=0)
    options: list[EventDoctrineOptionInput] = Field(default_factory=list)


class EventCreate(BaseModel):
    title: NonBlank = Field(max_length=255)
    event_type: EventType
    lifecycle_status: EventLifecycle = "draft"
    registration_status: EventRegistrationState = "open"
    formup_at: datetime | None = None
    start_at: datetime
    end_at: datetime | None = None
    estimated_duration_minutes: int | None = Field(default=None, ge=1, le=43200)
    operational_area: str | None = Field(default=None, max_length=500)
    route_notes: str | None = None
    discord_voice_label: str | None = Field(default=None, max_length=255)
    discord_voice_url: str | None = Field(default=None, max_length=1000)
    discord_guild_id: str | None = Field(default=None, max_length=64)
    discord_channel_id: str | None = Field(default=None, max_length=64)
    lead_character_id: int | None = Field(default=None, gt=0)
    doctrine_mode: DoctrineMode = "none"
    doctrine_id: int | None = Field(default=None, gt=0)
    doctrine_manual_name: str | None = Field(default=None, max_length=255)
    doctrine_external_url: str | None = Field(default=None, max_length=1000)
    doctrine_notes: str | None = None
    related_url: str | None = Field(default=None, max_length=1000)
    instructions: str | None = None
    audience_kind: AudienceKind = "all_members"
    audience_corporation_id: int | None = Field(default=None, gt=0)
    audience_alliance_id: int | None = Field(default=None, gt=0)
    composition_visibility: CompositionVisibility = "participants"
    participant_limit: int | None = Field(default=None, gt=0)
    limit_basis: LimitBasis = "characters"
    locations: list[EventLocationInput] = Field(default_factory=list)
    role_requirements: list[EventRoleRequirementInput] = Field(default_factory=list)
    doctrine_requirements: list[EventDoctrineRequirementInput] = Field(default_factory=list)

    @field_validator("formup_at", "start_at", "end_at")
    @classmethod
    def timezone_required(cls, value: datetime | None, info):
        return _require_aware(value, info.field_name)

    @field_validator("discord_voice_url", "doctrine_external_url", "related_url")
    @classmethod
    def http_url_required(cls, value: str | None) -> str | None:
        return _clean_url(value)

    @model_validator(mode="after")
    def validate_event(self) -> "EventCreate":
        if self.lifecycle_status not in {"draft", "scheduled"}:
            raise ValueError("New events must begin as draft or scheduled")
        if self.formup_at is not None and self.formup_at > self.start_at:
            raise ValueError("formup_at must be before or equal to start_at")
        if self.end_at is not None and self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        if self.end_at is not None and self.estimated_duration_minutes is not None:
            raise ValueError("Provide end_at or estimated_duration_minutes, not both")
        if self.audience_kind == "corporation" and self.audience_corporation_id is None:
            raise ValueError("audience_corporation_id is required for a corporation audience")
        if self.audience_kind == "alliance" and self.audience_alliance_id is None:
            raise ValueError("audience_alliance_id is required for an alliance audience")
        formup_count = sum(location.location_role == "formup" for location in self.locations)
        destination_count = sum(location.location_role == "destination" for location in self.locations)
        if formup_count > 1 or destination_count > 1:
            raise ValueError("Only one formup and one destination location are allowed")
        if self.lifecycle_status != "draft" and formup_count != 1:
            raise ValueError("A formup location is required before scheduling an event")
        if self.doctrine_mode in {"required", "recommended"} and not (
            self.doctrine_id or (self.doctrine_manual_name or "").strip() or self.doctrine_external_url
        ):
            raise ValueError("Required or recommended doctrine needs a doctrine reference or label")
        if self.doctrine_mode == "required" and any(not requirement.options for requirement in self.doctrine_requirements):
            raise ValueError("Every required-doctrine requirement needs at least one option")
        return self


class EventPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: NonBlank | None = Field(default=None, max_length=255)
    event_type: EventType | None = None
    formup_at: datetime | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    estimated_duration_minutes: int | None = Field(default=None, ge=1, le=43200)
    operational_area: str | None = Field(default=None, max_length=500)
    route_notes: str | None = None
    discord_voice_label: str | None = Field(default=None, max_length=255)
    discord_voice_url: str | None = Field(default=None, max_length=1000)
    discord_guild_id: str | None = Field(default=None, max_length=64)
    discord_channel_id: str | None = Field(default=None, max_length=64)
    lead_character_id: int | None = Field(default=None, gt=0)
    doctrine_mode: DoctrineMode | None = None
    doctrine_id: int | None = Field(default=None, gt=0)
    doctrine_manual_name: str | None = Field(default=None, max_length=255)
    doctrine_external_url: str | None = Field(default=None, max_length=1000)
    doctrine_notes: str | None = None
    related_url: str | None = Field(default=None, max_length=1000)
    instructions: str | None = None
    audience_kind: AudienceKind | None = None
    audience_corporation_id: int | None = Field(default=None, gt=0)
    audience_alliance_id: int | None = Field(default=None, gt=0)
    composition_visibility: CompositionVisibility | None = None
    participant_limit: int | None = Field(default=None, gt=0)
    limit_basis: LimitBasis | None = None
    expected_updated_at: datetime
    locations: list[EventLocationInput] | None = None
    role_requirements: list[EventRoleRequirementInput] | None = None
    doctrine_requirements: list[EventDoctrineRequirementInput] | None = None

    @field_validator("formup_at", "start_at", "end_at", "expected_updated_at")
    @classmethod
    def timezone_required(cls, value: datetime | None, info):
        return _require_aware(value, info.field_name)

    @field_validator("discord_voice_url", "doctrine_external_url", "related_url")
    @classmethod
    def http_url_required(cls, value: str | None) -> str | None:
        return _clean_url(value)


class EventTransitionRequest(BaseModel):
    lifecycle_status: EventLifecycle | None = None
    registration_status: EventRegistrationState | None = None
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def require_change(self) -> "EventTransitionRequest":
        if self.lifecycle_status is None and self.registration_status is None:
            raise ValueError("At least one status change is required")
        return self


class EventRsvpUpsert(BaseModel):
    status: RsvpStatus
    notes: str | None = Field(default=None, max_length=500)


class EventRegistrationCreate(BaseModel):
    character_id: int = Field(gt=0)
    registration_status: CharacterRegistrationStatus = "registered"
    confirmation_status: ConfirmationStatus = "tentative"
    planned_ship_source: ShipSource = "undecided"
    ship_type_id: int | None = Field(default=None, gt=0)
    saved_fitting_id: int | None = Field(default=None, gt=0)
    doctrine_requirement_id: int | None = Field(default=None, gt=0)
    doctrine_option_id: int | None = Field(default=None, gt=0)
    role_key: FleetRole | None = None
    custom_role: str | None = Field(default=None, max_length=120)
    freeform_ship_description: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=1000)


class EventRegistrationUpdate(BaseModel):
    registration_status: CharacterRegistrationStatus | None = None
    confirmation_status: ConfirmationStatus | None = None
    planned_ship_source: ShipSource | None = None
    ship_type_id: int | None = Field(default=None, gt=0)
    saved_fitting_id: int | None = Field(default=None, gt=0)
    doctrine_requirement_id: int | None = Field(default=None, gt=0)
    doctrine_option_id: int | None = Field(default=None, gt=0)
    role_key: FleetRole | None = None
    custom_role: str | None = Field(default=None, max_length=120)
    freeform_ship_description: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=1000)


class AttendanceRegistrationUpdate(BaseModel):
    attendance_status: AttendanceStatus
    checked_in_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("checked_in_at")
    @classmethod
    def timezone_required(cls, value: datetime | None, info):
        return _require_aware(value, info.field_name)


class AttendanceManualCreate(BaseModel):
    attendee_source: AttendanceSource
    character_id: int | None = Field(default=None, gt=0)
    character_eve_id: int | None = Field(default=None, gt=0)
    display_name: NonBlank | None = Field(default=None, max_length=255)
    corporation_name: str | None = Field(default=None, max_length=255)
    alliance_name: str | None = Field(default=None, max_length=255)
    checked_in_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("checked_in_at")
    @classmethod
    def timezone_required(cls, value: datetime | None, info):
        return _require_aware(value, info.field_name)

    @model_validator(mode="after")
    def validate_source(self) -> "AttendanceManualCreate":
        if self.attendee_source == "linked_character" and self.character_id is None:
            raise ValueError("character_id is required for a linked character")
        if self.attendee_source == "external_character" and (
            self.character_eve_id is None or not (self.display_name or "").strip()
        ):
            raise ValueError("character_eve_id and display_name are required for an external character")
        if self.attendee_source == "public_guest" and not (self.display_name or "").strip():
            raise ValueError("display_name is required for a public guest")
        return self


class AttendanceEntryUpdate(BaseModel):
    attendance_status: AttendanceStatus | None = None
    display_name: NonBlank | None = Field(default=None, max_length=255)
    corporation_name: str | None = Field(default=None, max_length=255)
    alliance_name: str | None = Field(default=None, max_length=255)
    checked_in_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("checked_in_at")
    @classmethod
    def timezone_required(cls, value: datetime | None, info):
        return _require_aware(value, info.field_name)


class AttendanceRate(BaseModel):
    numerator: int = 0
    denominator: int = 0
    percent: float | None = None


class EventAnalyticsCounts(BaseModel):
    event_count: int = 0
    rsvp_going: int = 0
    rsvp_maybe: int = 0
    rsvp_declined: int = 0
    rsvp_waitlisted: int = 0
    registered_characters: int = 0
    attended_registered: int = 0
    attended_unregistered: int = 0
    no_show: int = 0
    excused: int = 0
    unmarked: int = 0
    attendance_rate: AttendanceRate = Field(default_factory=AttendanceRate)


class EventAnalyticsBucket(EventAnalyticsCounts):
    period_start: datetime


class EventAnalyticsTypeRow(EventAnalyticsCounts):
    event_type: EventType


class EventAnalyticsResponse(BaseModel):
    from_at: datetime
    to_at: datetime
    bucket: AnalyticsBucket
    totals: EventAnalyticsCounts
    by_event_type: list[EventAnalyticsTypeRow]
    series: list[EventAnalyticsBucket]
    engine_requested: str | None = None
    engine_used: str | None = None
    engine_shadow_match: bool | None = None
    engine_fallback_reason: str | None = None
