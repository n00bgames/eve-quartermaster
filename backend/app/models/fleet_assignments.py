from __future__ import annotations
from datetime import datetime
from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.models.base import Base

class FleetAssignmentOperation(Base):
    __tablename__ = "fleet_assignment_operations"
    __table_args__ = (CheckConstraint("status IN ('draft', 'published', 'archived')", name="ck_fleet_assignment_status"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    briefing: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    slots: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

class FleetAssignmentPilot(Base):
    __tablename__ = "fleet_assignment_pilots"
    __table_args__ = (
        UniqueConstraint("operation_id", "normalized_name", name="uq_fleet_assignment_pilot_name"),
        UniqueConstraint("operation_id", "character_eve_id", name="uq_fleet_assignment_pilot_character"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    operation_id: Mapped[int] = mapped_column(ForeignKey("fleet_assignment_operations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    character_eve_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    slot_key: Mapped[str | None] = mapped_column(String(36))
    fitting_snapshot: Mapped[dict | None] = mapped_column(JSON)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class FleetAssignmentPreset(Base):
    __tablename__ = "fleet_assignment_presets"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    briefing: Mapped[str] = mapped_column(Text, nullable=False, default="")
    slots: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
