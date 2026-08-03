from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class SnapshotRun(Base):
    __tablename__ = "snapshot_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scope_type: Mapped[str] = mapped_column(String(40), default="global", nullable=False, index=True)
    scope_id: Mapped[int | None] = mapped_column(Integer, index=True)
    source: Mapped[str] = mapped_column(String(60), default="manual", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default="running", nullable=False, index=True)
    schema_version: Mapped[int] = mapped_column(Integer, default=2, nullable=False, index=True)
    message: Mapped[str | None] = mapped_column(Text)

    metrics: Mapped[list["SnapshotMetric"]] = relationship(back_populates="snapshot_run", cascade="all, delete-orphan")


class SnapshotMetric(Base):
    __tablename__ = "snapshot_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_run_id: Mapped[int] = mapped_column(ForeignKey("snapshot_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    owner_id: Mapped[int | None] = mapped_column(Integer, index=True)
    owner_name: Mapped[str | None] = mapped_column(String(255), index=True)
    metric_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    metric_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False, index=True)
    metric_value: Mapped[Decimal] = mapped_column(Numeric(24, 2), default=0, nullable=False)
    dimensions_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    snapshot_run: Mapped[SnapshotRun] = relationship(back_populates="metrics")


class CharacterSkillSnapshot(Base):
    __tablename__ = "character_skill_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_run_id: Mapped[int] = mapped_column(ForeignKey("snapshot_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("eve_characters.id"), nullable=False, index=True)
    character_eve_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    character_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    total_skill_points: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    unallocated_skill_points: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    skill_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    queue_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    category_name: Mapped[str | None] = mapped_column(String(255), index=True)
    category_skill_points: Mapped[int | None] = mapped_column(BigInteger)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class CorporationSnapshot(Base):
    __tablename__ = "corporation_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_run_id: Mapped[int] = mapped_column(ForeignKey("snapshot_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    corporation_id: Mapped[int] = mapped_column(ForeignKey("eve_corporations.id"), nullable=False, index=True)
    corporation_eve_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    corporation_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    member_count: Mapped[int | None] = mapped_column(Integer)
    wallet_balance: Mapped[Decimal] = mapped_column(Numeric(24, 2), default=0, nullable=False)
    asset_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    asset_units: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    blueprint_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class CorporationWalletSnapshot(Base):
    __tablename__ = "corporation_wallet_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_run_id: Mapped[int] = mapped_column(ForeignKey("snapshot_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    corporation_id: Mapped[int] = mapped_column(ForeignKey("eve_corporations.id"), nullable=False, index=True)
    corporation_eve_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    corporation_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    division: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(24, 2), default=0, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class BlueprintSnapshot(Base):
    __tablename__ = "blueprint_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_run_id: Mapped[int] = mapped_column(ForeignKey("snapshot_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    ownership_entity_id: Mapped[int] = mapped_column(ForeignKey("ownership_entities.id"), nullable=False, index=True)
    owner_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    blueprint_item_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    blueprint_type_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    blueprint_type_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    material_efficiency: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    time_efficiency: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    runs_remaining: Mapped[int | None] = mapped_column(Integer)
    is_copy: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    inventory_state: Mapped[str] = mapped_column(String(30), default="inventory", nullable=False, index=True)
    research_job_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


