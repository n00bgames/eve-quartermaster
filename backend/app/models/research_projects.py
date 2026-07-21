from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class ResearchProject(Base):
    __tablename__ = "research_projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    character_id: Mapped[int | None] = mapped_column(ForeignKey("eve_characters.id"), nullable=True, index=True)
    corporation_id: Mapped[int | None] = mapped_column(ForeignKey("eve_corporations.id"), nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(20), default="character", nullable=False, index=True)
    installer_name: Mapped[str | None] = mapped_column(String(255))
    installer_character_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    completed_character_id: Mapped[int | None] = mapped_column(BigInteger)
    activity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    blueprint_id: Mapped[int | None] = mapped_column(BigInteger)
    blueprint_type_id: Mapped[int | None] = mapped_column(ForeignKey("eve_types.type_id"), index=True)
    product_type_id: Mapped[int | None] = mapped_column(ForeignKey("eve_types.type_id"), index=True)
    facility_id: Mapped[int | None] = mapped_column(BigInteger)
    station_id: Mapped[int | None] = mapped_column(BigInteger)
    facility_name: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    runs: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    licensed_runs: Mapped[int | None] = mapped_column(Integer)
    successful_runs: Mapped[int | None] = mapped_column(Integer)
    probability: Mapped[float | None] = mapped_column(Numeric(10, 6))
    cost: Mapped[float | None] = mapped_column(Numeric(20, 2))
    duration: Mapped[int | None] = mapped_column(Integer)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    pause_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    character = relationship("EveCharacter")
    corporation = relationship("EveCorporation")
    blueprint_type = relationship("EveType", foreign_keys=[blueprint_type_id])
    product_type = relationship("EveType", foreign_keys=[product_type_id])


class ResearchQueueItem(Base):
    __tablename__ = "research_queue_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    blueprint_id: Mapped[int | None] = mapped_column(ForeignKey("blueprints.id", ondelete="SET NULL"), index=True)
    blueprint_type_id: Mapped[int | None] = mapped_column(ForeignKey("eve_types.type_id", ondelete="SET NULL"), index=True)
    blueprint_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    blueprint_kind: Mapped[str] = mapped_column(String(3), nullable=False)
    owner_name: Mapped[str | None] = mapped_column(String(255))
    material_efficiency: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    time_efficiency: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    runs_remaining: Mapped[int | None] = mapped_column(Integer)
    source_location_name: Mapped[str | None] = mapped_column(String(500))
    source_hangar: Mapped[str | None] = mapped_column(String(500))
    activity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    runs: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    blueprint = relationship("Blueprint")
    blueprint_type = relationship("EveType")
