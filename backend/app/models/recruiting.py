from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class RecruitmentSettings(Base):
    __tablename__ = "recruitment_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    setup_complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    corporation_eve_id: Mapped[int | None] = mapped_column(Integer, index=True)
    corporation_name: Mapped[str | None] = mapped_column(String(255))
    corporation_ticker: Mapped[str | None] = mapped_column(String(20))
    corporation_logo_url: Mapped[str | None] = mapped_column(String(500))
    alliance_eve_id: Mapped[int | None] = mapped_column(Integer, index=True)
    alliance_name: Mapped[str | None] = mapped_column(String(255))
    alliance_ticker: Mapped[str | None] = mapped_column(String(20))
    alliance_logo_url: Mapped[str | None] = mapped_column(String(500))
    ceo_character_eve_id: Mapped[int | None] = mapped_column(Integer, index=True)
    ceo_character_name: Mapped[str | None] = mapped_column(String(255))
    ceo_portrait_url: Mapped[str | None] = mapped_column(String(500))
    ceo_manual_override: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    primary_timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    activity_window_start: Mapped[str] = mapped_column(String(5), default="18:00", nullable=False)
    activity_window_end: Mapped[str] = mapped_column(String(5), default="23:00", nullable=False)
    public_headline: Mapped[str] = mapped_column(String(255), default="Recruitment", nullable=False)
    public_subheading: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    public_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    public_body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    offers_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    expectations_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    priorities_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    statuses_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    tags_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    form_options_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    application_questions_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    interview_questions_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    parameter_definitions_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    required_scopes_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    privacy_notice: Mapped[str] = mapped_column(Text, default="", nullable=False)
    declined_retention_days: Mapped[int] = mapped_column(Integer, default=365, nullable=False)
    withdrawn_retention_days: Mapped[int] = mapped_column(Integer, default=180, nullable=False)
    abandoned_retention_days: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    auto_refresh_hours: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class RecruitmentUserCapability(Base):
    __tablename__ = "recruitment_user_capabilities"
    __table_args__ = (UniqueConstraint("user_id", "capability", name="uq_recruitment_user_capability"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    capability: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    assigned_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", foreign_keys=[user_id])


class RecruitmentApplication(Base):
    __tablename__ = "recruitment_applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    applicant_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(80), default="Draft", nullable=False, index=True)
    assigned_recruiter_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    discord_username: Mapped[str | None] = mapped_column(String(120), index=True)
    discord_display_name: Mapped[str | None] = mapped_column(String(120))
    discord_user_id: Mapped[str | None] = mapped_column(String(40))
    discord_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discord_verified_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    preferred_name: Mapped[str | None] = mapped_column(String(120))
    pronouns: Mapped[str | None] = mapped_column(String(80))
    timezone: Mapped[str | None] = mapped_column(String(64), index=True)
    primary_interest: Mapped[str | None] = mapped_column(String(80), index=True)
    veteran_status: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    answers_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    acknowledgements_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    activity_preferences_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    internal_flags_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    recruiter_ratings_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    tags_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_applicant_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    applicant = relationship("User", foreign_keys=[applicant_user_id])
    assigned_recruiter = relationship("User", foreign_keys=[assigned_recruiter_user_id])
    linked_characters: Mapped[list["RecruitmentLinkedCharacter"]] = relationship(back_populates="application", cascade="all, delete-orphan")
    interviews: Mapped[list["RecruitmentInterview"]] = relationship(back_populates="application", cascade="all, delete-orphan")
    notes: Mapped[list["RecruitmentNote"]] = relationship(back_populates="application", cascade="all, delete-orphan")
    messages: Mapped[list["RecruitmentMessage"]] = relationship(back_populates="application", cascade="all, delete-orphan")
    history: Mapped[list["RecruitmentStatusHistory"]] = relationship(back_populates="application", cascade="all, delete-orphan")


class RecruitmentLinkedCharacter(Base):
    __tablename__ = "recruitment_linked_characters"
    __table_args__ = (UniqueConstraint("application_id", "character_id", name="uq_recruitment_application_character"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("recruitment_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("eve_characters.id", ondelete="CASCADE"), nullable=False, index=True)
    is_main: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    employment_history_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    granted_scopes_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    token_health: Mapped[str] = mapped_column(String(40), default="unknown", nullable=False)
    verification_status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    last_successful_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_sync_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    application: Mapped[RecruitmentApplication] = relationship(back_populates="linked_characters")
    character = relationship("EveCharacter")


class RecruitmentInterview(Base):
    __tablename__ = "recruitment_interviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("recruitment_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    interviewer_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    applicant_timezone: Mapped[str | None] = mapped_column(String(64))
    availability_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    attendance_status: Mapped[str] = mapped_column(String(40), default="requested", nullable=False, index=True)
    answers_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    internal_notes: Mapped[str | None] = mapped_column(Text)
    visible_follow_up: Mapped[str | None] = mapped_column(Text)
    recommendation: Mapped[str | None] = mapped_column(String(80))
    applicant_acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    application: Mapped[RecruitmentApplication] = relationship(back_populates="interviews")
    interviewer = relationship("User", foreign_keys=[interviewer_user_id])


class RecruitmentNote(Base):
    __tablename__ = "recruitment_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("recruitment_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    author_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    applicant_visible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    redacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    application: Mapped[RecruitmentApplication] = relationship(back_populates="notes")
    author = relationship("User", foreign_keys=[author_user_id])


class RecruitmentMessage(Base):
    __tablename__ = "recruitment_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("recruitment_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    author_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    from_applicant: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    application: Mapped[RecruitmentApplication] = relationship(back_populates="messages")
    author = relationship("User", foreign_keys=[author_user_id])


class RecruitmentStatusHistory(Base):
    __tablename__ = "recruitment_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("recruitment_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    previous_status: Mapped[str | None] = mapped_column(String(80))
    new_status: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    acting_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    reason: Mapped[str | None] = mapped_column(Text)
    applicant_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notifications_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    application: Mapped[RecruitmentApplication] = relationship(back_populates="history")
    acting_user = relationship("User", foreign_keys=[acting_user_id])


class RecruitmentAuditLog(Base):
    __tablename__ = "recruitment_audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int | None] = mapped_column(ForeignKey("recruitment_applications.id", ondelete="SET NULL"), index=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    details_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    actor = relationship("User", foreign_keys=[actor_user_id])
