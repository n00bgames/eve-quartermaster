from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PlanetaryColony(Base):
    __tablename__ = "planetary_colonies"
    __table_args__ = (
        UniqueConstraint("character_id", "planet_id", name="uq_planetary_colony_character_planet"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(
        ForeignKey("eve_characters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    planet_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    planet_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    planet_type: Mapped[str | None] = mapped_column(String(40), index=True)
    solar_system_id: Mapped[int | None] = mapped_column(
        ForeignKey("eve_systems.system_id"), index=True
    )
    upgrade_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    num_pins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    esi_last_update: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    character = relationship("EveCharacter")
    system = relationship("EveSystem")
    pins: Mapped[list["PlanetaryPin"]] = relationship(
        back_populates="colony", cascade="all, delete-orphan"
    )
    links: Mapped[list["PlanetaryLink"]] = relationship(
        back_populates="colony", cascade="all, delete-orphan"
    )
    routes: Mapped[list["PlanetaryRoute"]] = relationship(
        back_populates="colony", cascade="all, delete-orphan"
    )


class PlanetaryPin(Base):
    __tablename__ = "planetary_pins"
    __table_args__ = (
        UniqueConstraint("colony_id", "pin_id", name="uq_planetary_pin_colony_pin"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    colony_id: Mapped[int] = mapped_column(
        ForeignKey("planetary_colonies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pin_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    type_id: Mapped[int] = mapped_column(ForeignKey("eve_types.type_id"), nullable=False, index=True)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    install_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expiry_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_cycle_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    schematic_id: Mapped[int | None] = mapped_column(Integer, index=True)
    extractor_cycle_time: Mapped[int | None] = mapped_column(Integer)
    extractor_head_radius: Mapped[float | None] = mapped_column(Float)
    extractor_product_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("eve_types.type_id"), index=True
    )
    extractor_qty_per_cycle: Mapped[int | None] = mapped_column(Integer)
    contents_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    extractor_heads_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    colony: Mapped[PlanetaryColony] = relationship(back_populates="pins")
    pin_type = relationship("EveType", foreign_keys=[type_id])
    extractor_product_type = relationship("EveType", foreign_keys=[extractor_product_type_id])


class PlanetaryLink(Base):
    __tablename__ = "planetary_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    colony_id: Mapped[int] = mapped_column(
        ForeignKey("planetary_colonies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_pin_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    destination_pin_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    link_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    colony: Mapped[PlanetaryColony] = relationship(back_populates="links")


class PlanetaryRoute(Base):
    __tablename__ = "planetary_routes"
    __table_args__ = (
        UniqueConstraint("colony_id", "route_id", name="uq_planetary_route_colony_route"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    colony_id: Mapped[int] = mapped_column(
        ForeignKey("planetary_colonies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    route_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    source_pin_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    destination_pin_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    content_type_id: Mapped[int] = mapped_column(
        ForeignKey("eve_types.type_id"), nullable=False, index=True
    )
    quantity: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    waypoints_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    colony: Mapped[PlanetaryColony] = relationship(back_populates="routes")
    content_type = relationship("EveType")
