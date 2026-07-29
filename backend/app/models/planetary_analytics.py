from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PlanetaryProductionSnapshot(Base):
    __tablename__ = "planetary_production_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "character_id",
            "pin_id",
            "product_type_id",
            "captured_at",
            name="uq_planetary_production_snapshot_observation",
        ),
        Index(
            "ix_planetary_production_snapshot_character_captured",
            "character_id",
            "captured_at",
        ),
        Index(
            "ix_planetary_production_snapshot_product_captured",
            "product_type_id",
            "captured_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(
        ForeignKey("eve_characters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    interval_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    planet_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    solar_system_id: Mapped[int | None] = mapped_column(
        ForeignKey("eve_systems.system_id"), index=True
    )
    pin_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    source_kind: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    product_type_id: Mapped[int] = mapped_column(
        ForeignKey("eve_types.type_id"), nullable=False, index=True
    )
    commodity_tier: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    unit_volume: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    projected_units_per_day: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    projected_remaining_units: Mapped[float | None] = mapped_column(Float)
    estimated_units_since_previous: Mapped[float] = mapped_column(
        Float, default=0, nullable=False
    )
    program_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    character = relationship("EveCharacter")
    product_type = relationship("EveType")
    system = relationship("EveSystem")
