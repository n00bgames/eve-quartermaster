from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Index, Integer, JSON, Numeric, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class DoctrinePriorityField(Base):
    __tablename__ = "doctrine_priority_fields"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    field_type: Mapped[str] = mapped_column(String(20), nullable=False, default="select")
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    options: Mapped[list["DoctrinePriorityOption"]] = relationship(back_populates="field", cascade="all, delete-orphan")


class DoctrinePriorityOption(Base):
    __tablename__ = "doctrine_priority_options"
    __table_args__ = (UniqueConstraint("field_id", "value", name="uq_doctrine_priority_option_value"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("doctrine_priority_fields.id", ondelete="CASCADE"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    value: Mapped[str] = mapped_column(String(120), nullable=False)
    short_code: Mapped[str | None] = mapped_column(String(32))
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    field: Mapped[DoctrinePriorityField] = relationship(back_populates="options")


class SkillPlan(Base):
    __tablename__ = "skill_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    character_id: Mapped[int | None] = mapped_column(ForeignKey("eve_characters.id", ondelete="SET NULL"), index=True)
    fitting_id: Mapped[int | None] = mapped_column(ForeignKey("character_fittings.id", ondelete="SET NULL"), index=True)
    source_doctrine_id: Mapped[int | None] = mapped_column(ForeignKey("doctrines.id", ondelete="SET NULL"), index=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual", index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    owner_user = relationship("User")
    character = relationship("EveCharacter")
    fitting = relationship("CharacterFitting")
    source_doctrine = relationship("Doctrine", foreign_keys=[source_doctrine_id])
    entries: Mapped[list["SkillPlanEntry"]] = relationship(back_populates="plan", cascade="all, delete-orphan")


class SkillPlanEntry(Base):
    __tablename__ = "skill_plan_entries"
    __table_args__ = (
        UniqueConstraint("plan_id", "skill_type_id", name="uq_skill_plan_entry_skill"),
        CheckConstraint("target_level >= 1 AND target_level <= 5", name="ck_skill_plan_target_level"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("skill_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    skill_type_id: Mapped[int] = mapped_column(ForeignKey("eve_types.type_id", ondelete="RESTRICT"), nullable=False, index=True)
    target_level: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    introduced_by: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    plan: Mapped[SkillPlan] = relationship(back_populates="entries")
    skill_type = relationship("EveType")


class SrpOperation(Base):
    __tablename__ = "srp_operations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    share_token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    fleet_commander_character_id: Mapped[int | None] = mapped_column(ForeignKey("eve_characters.id", ondelete="SET NULL"), index=True)
    doctrine_id: Mapped[int | None] = mapped_column(ForeignKey("doctrines.id", ondelete="SET NULL"), index=True)
    corporation_id: Mapped[int | None] = mapped_column(ForeignKey("eve_corporations.id", ondelete="SET NULL"), index=True)
    alliance_id: Mapped[int | None] = mapped_column(ForeignKey("eve_alliances.id", ondelete="SET NULL"), index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    fleet_commander = relationship("EveCharacter")
    doctrine = relationship("Doctrine")
    corporation = relationship("EveCorporation")
    alliance = relationship("EveAlliance")
    created_by = relationship("User")


class SrpLossReason(Base):
    __tablename__ = "srp_loss_reasons"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SrpRequest(Base):
    __tablename__ = "srp_requests"
    __table_args__ = (
        Index("ix_srp_loss_doctrine_status", "loss_occurred_at", "doctrine_id", "status"),
        Index("ix_srp_loss_disposition", "loss_occurred_at", "record_disposition"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    requesting_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("eve_characters.id", ondelete="RESTRICT"), nullable=False, index=True)
    fitting_id: Mapped[int] = mapped_column(ForeignKey("character_fittings.id", ondelete="RESTRICT"), nullable=False, index=True)
    doctrine_id: Mapped[int | None] = mapped_column(ForeignKey("doctrines.id", ondelete="SET NULL"), index=True)
    operation_id: Mapped[int | None] = mapped_column(ForeignKey("srp_operations.id", ondelete="SET NULL"), index=True)
    loss_reason_id: Mapped[int | None] = mapped_column(ForeignKey("srp_loss_reasons.id", ondelete="SET NULL"), index=True)
    corporation_id: Mapped[int | None] = mapped_column(ForeignKey("eve_corporations.id", ondelete="SET NULL"), index=True)
    alliance_id: Mapped[int | None] = mapped_column(ForeignKey("eve_alliances.id", ondelete="SET NULL"), index=True)
    ship_type_id: Mapped[int | None] = mapped_column(ForeignKey("eve_types.type_id", ondelete="SET NULL"), index=True)
    ship_group_id: Mapped[int | None] = mapped_column(ForeignKey("eve_groups.group_id", ondelete="SET NULL"), index=True)
    system_id: Mapped[int | None] = mapped_column(ForeignKey("eve_systems.system_id", ondelete="SET NULL"), index=True)
    region_id: Mapped[int | None] = mapped_column(ForeignKey("eve_regions.region_id", ondelete="SET NULL"), index=True)
    character_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    fitting_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    ship_name_snapshot: Mapped[str | None] = mapped_column(String(255))
    doctrine_name_snapshot: Mapped[str | None] = mapped_column(String(255))
    doctrine_priority_code_snapshot: Mapped[str | None] = mapped_column(String(120))
    fitting_snapshot: Mapped[dict | None] = mapped_column(JSON)
    corporation_name_snapshot: Mapped[str | None] = mapped_column(String(255))
    alliance_name_snapshot: Mapped[str | None] = mapped_column(String(255))
    ship_group_name_snapshot: Mapped[str | None] = mapped_column(String(255))
    operation_name_snapshot: Mapped[str | None] = mapped_column(String(255))
    loss_reason_name_snapshot: Mapped[str | None] = mapped_column(String(120))
    system_name_snapshot: Mapped[str | None] = mapped_column(String(255))
    region_name_snapshot: Mapped[str | None] = mapped_column(String(255))
    security_status: Mapped[float | None] = mapped_column(Float)
    security_class: Mapped[str | None] = mapped_column(String(24), index=True)
    loss_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    loss_time: Mapped[time] = mapped_column(Time, nullable=False)
    loss_occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    entered_timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    killmail_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    killmail_hash: Mapped[str | None] = mapped_column(String(255))
    killmail_url: Mapped[str | None] = mapped_column(String(1000))
    data_source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual", index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    expected_fit_value: Mapped[float | None] = mapped_column(Numeric(24, 2))
    hull_value: Mapped[float | None] = mapped_column(Numeric(24, 2))
    fitted_module_value: Mapped[float | None] = mapped_column(Numeric(24, 2))
    cargo_value: Mapped[float | None] = mapped_column(Numeric(24, 2))
    drone_fighter_value: Mapped[float | None] = mapped_column(Numeric(24, 2))
    submission_estimated_loss_value: Mapped[float | None] = mapped_column(Numeric(24, 2))
    killmail_destroyed_value: Mapped[float | None] = mapped_column(Numeric(24, 2))
    killmail_dropped_value: Mapped[float | None] = mapped_column(Numeric(24, 2))
    killmail_total_loss_value: Mapped[float | None] = mapped_column(Numeric(24, 2))
    verified_loss_value: Mapped[float | None] = mapped_column(Numeric(24, 2))
    authoritative_loss_value: Mapped[float | None] = mapped_column(Numeric(24, 2))
    requested_reimbursement_amount: Mapped[float | None] = mapped_column(Numeric(24, 2))
    approved_reimbursement_amount: Mapped[float | None] = mapped_column(Numeric(24, 2))
    paid_reimbursement_amount: Mapped[float | None] = mapped_column(Numeric(24, 2))
    valuation_source: Mapped[str | None] = mapped_column(String(64), index=True)
    valuation_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valuation_region_id: Mapped[int | None] = mapped_column(ForeignKey("eve_regions.region_id", ondelete="SET NULL"), index=True)
    valuation_market_context: Mapped[str | None] = mapped_column(String(255))
    valuation_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    manual_valuation_override: Mapped[float | None] = mapped_column(Numeric(24, 2))
    valuation_override_reason: Mapped[str | None] = mapped_column(Text)
    valuation_override_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    record_disposition: Mapped[str] = mapped_column(String(32), nullable=False, default="operational", index=True)
    duplicate_of_request_id: Mapped[int | None] = mapped_column(ForeignKey("srp_requests.id", ondelete="SET NULL"), index=True)
    exclusion_reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    requesting_user = relationship("User", foreign_keys=[requesting_user_id])
    reviewed_by_user = relationship("User", foreign_keys=[reviewed_by_user_id])
    character = relationship("EveCharacter")
    fitting = relationship("CharacterFitting")
    doctrine = relationship("Doctrine")
    operation = relationship("SrpOperation")
    loss_reason = relationship("SrpLossReason")
    corporation = relationship("EveCorporation")
    alliance = relationship("EveAlliance")
    ship_type = relationship("EveType", foreign_keys=[ship_type_id])
    ship_group = relationship("EveGroup")
    system = relationship("EveSystem")
    region = relationship("EveRegion", foreign_keys=[region_id])
    valuation_region = relationship("EveRegion", foreign_keys=[valuation_region_id])
    valuation_override_by = relationship("User", foreign_keys=[valuation_override_by_user_id])
    events: Mapped[list["SrpRequestEvent"]] = relationship(back_populates="request", cascade="all, delete-orphan")


class SrpRequestEvent(Base):
    __tablename__ = "srp_request_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("srp_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    old_values: Mapped[dict | None] = mapped_column(JSON)
    new_values: Mapped[dict | None] = mapped_column(JSON)
    event_metadata: Mapped[dict | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(Text)

    request: Mapped[SrpRequest] = relationship(back_populates="events")
    actor = relationship("User")
