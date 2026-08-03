from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class Doctrine(Base):
    __tablename__ = "doctrines"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    external_url: Mapped[str | None] = mapped_column(String(1000))
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    is_shared: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    created_by_user = relationship("User", foreign_keys=[created_by_user_id])


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("formup_at IS NULL OR formup_at <= start_at", name="ck_events_formup_before_start"),
        CheckConstraint("end_at IS NULL OR end_at > start_at", name="ck_events_end_after_start"),
        CheckConstraint(
            "end_at IS NULL OR estimated_duration_minutes IS NULL",
            name="ck_events_end_or_duration",
        ),
        CheckConstraint(
            "estimated_duration_minutes IS NULL OR "
            "(estimated_duration_minutes >= 1 AND estimated_duration_minutes <= 43200)",
            name="ck_events_duration_range",
        ),
        CheckConstraint(
            "participant_limit IS NULL OR participant_limit > 0",
            name="ck_events_participant_limit_positive",
        ),
        CheckConstraint(
            "audience_kind != 'corporation' OR audience_corporation_id IS NOT NULL",
            name="ck_events_corporation_audience",
        ),
        CheckConstraint(
            "audience_kind != 'alliance' OR audience_alliance_id IS NOT NULL",
            name="ck_events_alliance_audience",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    lifecycle_status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False, index=True)
    registration_status: Mapped[str] = mapped_column(String(32), default="open", nullable=False, index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    formup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    estimated_duration_minutes: Mapped[int | None] = mapped_column(Integer)
    operational_area: Mapped[str | None] = mapped_column(String(500))
    route_notes: Mapped[str | None] = mapped_column(Text)
    discord_voice_label: Mapped[str | None] = mapped_column(String(255))
    discord_voice_url: Mapped[str | None] = mapped_column(String(1000))
    discord_guild_id: Mapped[str | None] = mapped_column(String(64))
    discord_channel_id: Mapped[str | None] = mapped_column(String(64))
    lead_character_id: Mapped[int | None] = mapped_column(
        ForeignKey("eve_characters.id", ondelete="SET NULL"), index=True
    )
    lead_name_snapshot: Mapped[str | None] = mapped_column(String(255))
    doctrine_mode: Mapped[str] = mapped_column(String(32), default="none", nullable=False, index=True)
    doctrine_id: Mapped[int | None] = mapped_column(
        ForeignKey("doctrines.id", ondelete="SET NULL"), index=True
    )
    doctrine_manual_name: Mapped[str | None] = mapped_column(String(255))
    doctrine_external_url: Mapped[str | None] = mapped_column(String(1000))
    doctrine_notes: Mapped[str | None] = mapped_column(Text)
    related_url: Mapped[str | None] = mapped_column(String(1000))
    instructions: Mapped[str | None] = mapped_column(Text)
    audience_kind: Mapped[str] = mapped_column(String(32), default="all_members", nullable=False, index=True)
    audience_corporation_id: Mapped[int | None] = mapped_column(
        ForeignKey("eve_corporations.id", ondelete="SET NULL"), index=True
    )
    audience_alliance_id: Mapped[int | None] = mapped_column(
        ForeignKey("eve_alliances.id", ondelete="SET NULL"), index=True
    )
    composition_visibility: Mapped[str] = mapped_column(String(32), default="participants", nullable=False)
    participant_limit: Mapped[int | None] = mapped_column(Integer)
    limit_basis: Mapped[str] = mapped_column(String(16), default="characters", nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    created_by_user = relationship("User", foreign_keys=[created_by_user_id])
    lead_character = relationship("EveCharacter", foreign_keys=[lead_character_id])
    doctrine = relationship("Doctrine")
    audience_corporation = relationship("EveCorporation", foreign_keys=[audience_corporation_id])
    audience_alliance = relationship("EveAlliance", foreign_keys=[audience_alliance_id])
    locked_by_user = relationship("User", foreign_keys=[locked_by_user_id])
    locations: Mapped[list["EventLocation"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    role_requirements: Mapped[list["EventRoleRequirement"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    doctrine_requirements: Mapped[list["EventDoctrineRequirement"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    responses: Mapped[list["EventUserResponse"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    registrations: Mapped[list["EventCharacterRegistration"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    attendance_entries: Mapped[list["EventAttendanceEntry"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )


class EventLocation(Base):
    __tablename__ = "event_locations"
    __table_args__ = (
        CheckConstraint("sort_order >= 0", name="ck_event_locations_sort_order"),
        Index(
            "uq_event_locations_formup",
            "event_id",
            unique=True,
            postgresql_where=text("location_role = 'formup'"),
            sqlite_where=text("location_role = 'formup'"),
        ),
        Index(
            "uq_event_locations_destination",
            "event_id",
            unique=True,
            postgresql_where=text("location_role = 'destination'"),
            sqlite_where=text("location_role = 'destination'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    location_role: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    system_id: Mapped[int] = mapped_column(ForeignKey("eve_systems.system_id", ondelete="RESTRICT"), nullable=False, index=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"), index=True)
    eve_location_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    location_name_snapshot: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(String(1000))

    event: Mapped[Event] = relationship(back_populates="locations")
    system = relationship("EveSystem")
    location = relationship("Location")


class EventRoleRequirement(Base):
    __tablename__ = "event_role_requirements"
    __table_args__ = (
        UniqueConstraint("event_id", "role_key", "custom_label", name="uq_event_role_requirement"),
        CheckConstraint("requested_quantity > 0", name="ck_event_role_requirement_quantity"),
        CheckConstraint("sort_order >= 0", name="ck_event_role_requirement_sort_order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    role_key: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    custom_label: Mapped[str | None] = mapped_column(String(120))
    requested_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    event: Mapped[Event] = relationship(back_populates="role_requirements")


class EventDoctrineRequirement(Base):
    __tablename__ = "event_doctrine_requirements"
    __table_args__ = (
        CheckConstraint("requested_quantity > 0", name="ck_event_doctrine_requirement_quantity"),
        CheckConstraint("sort_order >= 0", name="ck_event_doctrine_requirement_sort_order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    role_requirement_id: Mapped[int | None] = mapped_column(
        ForeignKey("event_role_requirements.id", ondelete="SET NULL"), index=True
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    requested_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    event: Mapped[Event] = relationship(back_populates="doctrine_requirements")
    role_requirement = relationship("EventRoleRequirement")
    options: Mapped[list["EventDoctrineRequirementOption"]] = relationship(
        back_populates="requirement", cascade="all, delete-orphan"
    )


class EventDoctrineRequirementOption(Base):
    __tablename__ = "event_doctrine_requirement_options"
    __table_args__ = (
        CheckConstraint(
            "ship_type_id IS NOT NULL OR fitting_id IS NOT NULL OR manual_name_snapshot IS NOT NULL",
            name="ck_event_doctrine_option_identity",
        ),
        CheckConstraint("sort_order >= 0", name="ck_event_doctrine_option_sort_order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    requirement_id: Mapped[int] = mapped_column(
        ForeignKey("event_doctrine_requirements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ship_type_id: Mapped[int | None] = mapped_column(ForeignKey("eve_types.type_id", ondelete="SET NULL"), index=True)
    fitting_id: Mapped[int | None] = mapped_column(
        ForeignKey("character_fittings.id", ondelete="SET NULL"), index=True
    )
    manual_name_snapshot: Mapped[str | None] = mapped_column(String(255))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    requirement: Mapped[EventDoctrineRequirement] = relationship(back_populates="options")
    ship_type = relationship("EveType")
    fitting = relationship("CharacterFitting")


class EventUserResponse(Base):
    __tablename__ = "event_user_responses"
    __table_args__ = (UniqueConstraint("event_id", "user_id", name="uq_event_user_response"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(String(500))
    responded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    event: Mapped[Event] = relationship(back_populates="responses")
    user = relationship("User")


class EventCharacterRegistration(Base):
    __tablename__ = "event_character_registrations"
    __table_args__ = (
        Index(
            "uq_event_character_registration",
            "event_id",
            "user_id",
            "character_id",
            unique=True,
            postgresql_where=text("character_id IS NOT NULL"),
            sqlite_where=text("character_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    character_id: Mapped[int | None] = mapped_column(ForeignKey("eve_characters.id", ondelete="SET NULL"), index=True)
    character_eve_id_snapshot: Mapped[int] = mapped_column(BigInteger, nullable=False)
    character_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    corporation_name_snapshot: Mapped[str | None] = mapped_column(String(255))
    alliance_name_snapshot: Mapped[str | None] = mapped_column(String(255))
    registration_status: Mapped[str] = mapped_column(String(24), default="registered", nullable=False, index=True)
    confirmation_status: Mapped[str] = mapped_column(String(24), default="tentative", nullable=False, index=True)
    planned_ship_source: Mapped[str] = mapped_column(String(24), default="undecided", nullable=False)
    ship_type_id: Mapped[int | None] = mapped_column(ForeignKey("eve_types.type_id", ondelete="SET NULL"), index=True)
    ship_name_snapshot: Mapped[str | None] = mapped_column(String(255))
    saved_fitting_id: Mapped[int | None] = mapped_column(
        ForeignKey("character_fittings.id", ondelete="SET NULL"), index=True
    )
    fitting_name_snapshot: Mapped[str | None] = mapped_column(String(255))
    fitting_updated_at_snapshot: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    doctrine_requirement_id: Mapped[int | None] = mapped_column(
        ForeignKey("event_doctrine_requirements.id", ondelete="SET NULL"), index=True
    )
    doctrine_option_id: Mapped[int | None] = mapped_column(
        ForeignKey("event_doctrine_requirement_options.id", ondelete="SET NULL"), index=True
    )
    role_key: Mapped[str | None] = mapped_column(String(48), index=True)
    custom_role: Mapped[str | None] = mapped_column(String(120))
    freeform_ship_description: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    event: Mapped[Event] = relationship(back_populates="registrations")
    user = relationship("User")
    character = relationship("EveCharacter")
    ship_type = relationship("EveType")
    saved_fitting = relationship("CharacterFitting")
    doctrine_requirement = relationship("EventDoctrineRequirement", foreign_keys=[doctrine_requirement_id])
    doctrine_option = relationship("EventDoctrineRequirementOption", foreign_keys=[doctrine_option_id])


class EventAttendanceEntry(Base):
    __tablename__ = "event_attendance_entries"
    __table_args__ = (
        Index(
            "uq_event_attendance_registration",
            "event_id",
            "registration_id",
            unique=True,
            postgresql_where=text("registration_id IS NOT NULL"),
            sqlite_where=text("registration_id IS NOT NULL"),
        ),
        Index(
            "uq_event_attendance_character",
            "event_id",
            "character_eve_id_snapshot",
            unique=True,
            postgresql_where=text("character_eve_id_snapshot IS NOT NULL"),
            sqlite_where=text("character_eve_id_snapshot IS NOT NULL"),
        ),
        CheckConstraint(
            "attendee_source != 'registration' OR registration_id IS NOT NULL",
            name="ck_event_attendance_registration_source",
        ),
        CheckConstraint(
            "attendee_source != 'linked_character' OR character_id IS NOT NULL",
            name="ck_event_attendance_linked_source",
        ),
        CheckConstraint(
            "attendee_source != 'external_character' OR character_eve_id_snapshot IS NOT NULL",
            name="ck_event_attendance_external_source",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    registration_id: Mapped[int | None] = mapped_column(
        ForeignKey("event_character_registrations.id", ondelete="SET NULL"), index=True
    )
    attendee_source: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    attendance_status: Mapped[str] = mapped_column(String(24), default="attended", nullable=False, index=True)
    linked_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    character_id: Mapped[int | None] = mapped_column(ForeignKey("eve_characters.id", ondelete="SET NULL"), index=True)
    character_eve_id_snapshot: Mapped[int | None] = mapped_column(BigInteger, index=True)
    display_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    corporation_name_snapshot: Mapped[str | None] = mapped_column(String(255))
    alliance_name_snapshot: Mapped[str | None] = mapped_column(String(255))
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(String(1000))
    recorded_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    event: Mapped[Event] = relationship(back_populates="attendance_entries")
    registration = relationship("EventCharacterRegistration")
    linked_user = relationship("User", foreign_keys=[linked_user_id])
    character = relationship("EveCharacter")
    recorded_by_user = relationship("User", foreign_keys=[recorded_by_user_id])
