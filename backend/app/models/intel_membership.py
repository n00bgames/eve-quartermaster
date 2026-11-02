"""Public organization counts; never a private corporation member roster."""
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class IntelMembershipMonitor(Base):
    __tablename__ = "intel_membership_monitors"
    subject_id: Mapped[int] = mapped_column(ForeignKey("intel_subjects.id", ondelete="CASCADE"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requested_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    next_poll_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="idle")
    notice: Mapped[str | None] = mapped_column(String(255))
    failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IntelMembershipSnapshot(Base):
    __tablename__ = "intel_membership_snapshots"
    __table_args__ = (
        UniqueConstraint("subject_id", "utc_day", name="uq_intel_membership_day"),
        CheckConstraint("member_count IS NULL OR member_count >= 0", name="ck_intel_membership_count"),
        Index("ix_intel_membership_subject_time", "subject_id", "observed_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("intel_subjects.id", ondelete="CASCADE"), nullable=False)
    utc_day: Mapped[str] = mapped_column(String(10), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    member_count: Mapped[int | None] = mapped_column(Integer)
    corporation_count: Mapped[int | None] = mapped_column(Integer)
    resolved_corporations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    known_member_count: Mapped[int | None] = mapped_column(Integer)
    # Public corporation IDs, names and counts only. No pilot roster or SSO data.
    corporations: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
