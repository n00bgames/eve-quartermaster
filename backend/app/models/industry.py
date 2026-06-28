from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.enums import ActivityKind, AssetSource, ProcurementKind


class Blueprint(Base):
    __tablename__ = "blueprints"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("assets.id"), unique=True)
    ownership_entity_id: Mapped[int] = mapped_column(ForeignKey("ownership_entities.id"), nullable=False, index=True)
    blueprint_type_id: Mapped[int] = mapped_column(ForeignKey("eve_types.type_id"), nullable=False, index=True)
    product_type_id: Mapped[int | None] = mapped_column(ForeignKey("eve_types.type_id"), index=True)
    material_efficiency: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    time_efficiency: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    runs_remaining: Mapped[int | None] = mapped_column(Integer)
    is_copy: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"), index=True)
    source: Mapped[AssetSource] = mapped_column(default=AssetSource.ESI, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    asset = relationship("Asset")
    ownership_entity = relationship("OwnershipEntity")
    blueprint_type = relationship("EveType", foreign_keys=[blueprint_type_id])
    product_type = relationship("EveType", foreign_keys=[product_type_id])
    location = relationship("Location")


class IndustryActivity(Base):
    __tablename__ = "industry_activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    blueprint_type_id: Mapped[int] = mapped_column(ForeignKey("eve_types.type_id"), nullable=False, index=True)
    activity_kind: Mapped[ActivityKind] = mapped_column(nullable=False, index=True)
    product_type_id: Mapped[int | None] = mapped_column(ForeignKey("eve_types.type_id"), index=True)
    product_quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    time_seconds: Mapped[int | None] = mapped_column(Integer)

    inputs: Mapped[list["IndustryActivityInput"]] = relationship(back_populates="activity", cascade="all, delete-orphan")


class IndustryActivityInput(Base):
    __tablename__ = "industry_activity_inputs"

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("industry_activities.id"), nullable=False, index=True)
    input_type_id: Mapped[int] = mapped_column(ForeignKey("eve_types.type_id"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    consume_type: Mapped[str] = mapped_column(String(40), default="consumed", nullable=False)

    activity: Mapped[IndustryActivity] = relationship(back_populates="inputs")
    input_type = relationship("EveType")


class ProductionPlan(Base):
    __tablename__ = "production_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ownership_entity_id: Mapped[int] = mapped_column(ForeignKey("ownership_entities.id"), nullable=False, index=True)
    blueprint_id: Mapped[int | None] = mapped_column(ForeignKey("blueprints.id"))
    activity_id: Mapped[int] = mapped_column(ForeignKey("industry_activities.id"), nullable=False)
    runs: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    target_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    inputs: Mapped[list["ProductionPlanInput"]] = relationship(back_populates="production_plan", cascade="all, delete-orphan")


class ProductionPlanInput(Base):
    __tablename__ = "production_plan_inputs"

    id: Mapped[int] = mapped_column(primary_key=True)
    production_plan_id: Mapped[int] = mapped_column(ForeignKey("production_plans.id"), nullable=False, index=True)
    input_type_id: Mapped[int] = mapped_column(ForeignKey("eve_types.type_id"), nullable=False, index=True)
    required_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    owned_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    missing_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    procurement_strategy: Mapped[ProcurementKind] = mapped_column(default=ProcurementKind.BUY, nullable=False)

    production_plan: Mapped[ProductionPlan] = relationship(back_populates="inputs")


class ProcurementSource(Base):
    __tablename__ = "procurement_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    type_id: Mapped[int] = mapped_column(ForeignKey("eve_types.type_id"), nullable=False, index=True)
    source_type: Mapped[ProcurementKind] = mapped_column(nullable=False, index=True)
    preferred_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    estimated_unit_price: Mapped[float | None] = mapped_column(Numeric(18, 2))
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    notes: Mapped[str | None] = mapped_column(String)
