from __future__ import annotations
from datetime import datetime
from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Index, JSON, String, text, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.models.base import Base

class IntelSubject(Base):
    __tablename__ = "intel_subjects"
    __table_args__ = (UniqueConstraint("kind", "eve_id", name="uq_intel_subject_entity"), CheckConstraint("kind IN ('character','corporation','alliance')", name="ck_intel_subject_kind"))
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    eve_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    public_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

class IntelObservation(Base):
    __tablename__ = "intel_observations"
    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("intel_subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(24), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)

class IntelCollection(Base):
    __tablename__ = "intel_collections"
    __table_args__ = (CheckConstraint("status IN ('queued','running','completed','partial','failed','cancelled')", name="ck_intel_collection_status"), Index("uq_intel_active_collection", "subject_id", unique=True, postgresql_where=text("status IN ('queued','running')"), sqlite_where=text("status IN ('queued','running')")))
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("intel_subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued", index=True)
    from_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    to_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    max_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    stage: Mapped[str] = mapped_column(String(16), nullable=False, default="profile")
    page: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    imported_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reused_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    coverage: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    errors: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class IntelSourceCache(Base):
    __tablename__ = "intel_source_cache"
    key: Mapped[str] = mapped_column(String(96), primary_key=True)
    # Pages retain discovery references and compact zKill flags; no duplicate raw killmails.
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

class IntelNote(Base):
    __tablename__ = "intel_notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("intel_subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

class IntelSighting(Base):
    __tablename__='intel_sightings'
    __table_args__=(UniqueConstraint('subject_id','observer_user_id','request_id',name='uq_intel_sighting_request'),Index('ix_intel_sightings_subject_time','subject_id','observed_at'))
    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey('intel_subjects.id',ondelete='CASCADE'),nullable=False)
    observer_user_id: Mapped[int] = mapped_column(ForeignKey('users.id',ondelete='RESTRICT'),nullable=False)
    request_id: Mapped[str] = mapped_column(String(36),nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),nullable=False,server_default=func.now())
    manual_time: Mapped[bool] = mapped_column(Boolean,nullable=False,default=False)
    system_id: Mapped[int] = mapped_column(ForeignKey('eve_systems.system_id'),nullable=False)
    system_name: Mapped[str] = mapped_column(String(255),nullable=False)
    region_id: Mapped[int | None] = mapped_column(Integer)
    region_name: Mapped[str | None] = mapped_column(String(255))
    ship_type_id: Mapped[int | None] = mapped_column(ForeignKey('eve_types.type_id'),nullable=True)
    ship_type_name: Mapped[str] = mapped_column(String(255),nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),nullable=False)
