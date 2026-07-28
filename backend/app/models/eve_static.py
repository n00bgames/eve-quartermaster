from typing import Any

from sqlalchemy import Boolean, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class EveCategory(Base):
    __tablename__ = "eve_categories"

    category_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    groups: Mapped[list["EveGroup"]] = relationship(back_populates="category")


class EveGroup(Base):
    __tablename__ = "eve_groups"

    group_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("eve_categories.category_id"))
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    category: Mapped[EveCategory | None] = relationship(back_populates="groups")
    types: Mapped[list["EveType"]] = relationship(back_populates="group")


class EveType(Base):
    __tablename__ = "eve_types"

    type_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("eve_groups.group_id"))
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    volume: Mapped[float | None] = mapped_column(Float)
    packaged_volume: Mapped[float | None] = mapped_column(Float)
    capacity: Mapped[float | None] = mapped_column(Float)
    mass: Mapped[float | None] = mapped_column(Float)
    market_group_id: Mapped[int | None] = mapped_column(Integer, index=True)
    published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    group: Mapped[EveGroup | None] = relationship(back_populates="types")
    dogma_attributes: Mapped[list["EveTypeDogmaAttribute"]] = relationship(back_populates="type")
    dogma_effects: Mapped[list["EveTypeDogmaEffect"]] = relationship(back_populates="type")


class EveDogmaAttribute(Base):
    __tablename__ = "eve_dogma_attributes"

    attribute_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    unit_id: Mapped[int | None] = mapped_column(Integer, index=True)
    default_value: Mapped[float | None] = mapped_column(Float)
    published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    type_values: Mapped[list["EveTypeDogmaAttribute"]] = relationship(back_populates="attribute")


class EveTypeDogmaAttribute(Base):
    __tablename__ = "eve_type_dogma_attributes"
    __table_args__ = (UniqueConstraint("type_id", "attribute_id", name="uq_eve_type_dogma_attribute"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type_id: Mapped[int] = mapped_column(ForeignKey("eve_types.type_id"), nullable=False, index=True)
    attribute_id: Mapped[int] = mapped_column(ForeignKey("eve_dogma_attributes.attribute_id"), nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)

    type: Mapped[EveType] = relationship(back_populates="dogma_attributes")
    attribute: Mapped[EveDogmaAttribute] = relationship(back_populates="type_values")


class EveDogmaEffect(Base):
    __tablename__ = "eve_dogma_effects"

    effect_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[int | None] = mapped_column(Integer, index=True)
    published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_assistance: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_offensive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_warp_safe: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    modifier_info: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)

    type_values: Mapped[list["EveTypeDogmaEffect"]] = relationship(back_populates="effect")


class EveTypeDogmaEffect(Base):
    __tablename__ = "eve_type_dogma_effects"
    __table_args__ = (UniqueConstraint("type_id", "effect_id", name="uq_eve_type_dogma_effect"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type_id: Mapped[int] = mapped_column(ForeignKey("eve_types.type_id"), nullable=False, index=True)
    effect_id: Mapped[int] = mapped_column(ForeignKey("eve_dogma_effects.effect_id"), nullable=False, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    type: Mapped[EveType] = relationship(back_populates="dogma_effects")
    effect: Mapped[EveDogmaEffect] = relationship(back_populates="type_values")


class EveRegion(Base):
    __tablename__ = "eve_regions"

    region_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    constellations: Mapped[list["EveConstellation"]] = relationship(back_populates="region")


class EveConstellation(Base):
    __tablename__ = "eve_constellations"

    constellation_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    region_id: Mapped[int | None] = mapped_column(ForeignKey("eve_regions.region_id"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    region: Mapped[EveRegion | None] = relationship(back_populates="constellations")
    systems: Mapped[list["EveSystem"]] = relationship(back_populates="constellation")


class EveSystem(Base):
    __tablename__ = "eve_systems"

    system_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    constellation_id: Mapped[int | None] = mapped_column(ForeignKey("eve_constellations.constellation_id"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    security_status: Mapped[float | None] = mapped_column(Float)
    security_class: Mapped[str | None] = mapped_column(String(8), index=True)
    x: Mapped[float | None] = mapped_column(Float)
    y: Mapped[float | None] = mapped_column(Float)
    z: Mapped[float | None] = mapped_column(Float)

    constellation: Mapped[EveConstellation | None] = relationship(back_populates="systems")
    outgoing_stargates: Mapped[list["EveStargate"]] = relationship(
        back_populates="system",
        foreign_keys="EveStargate.system_id",
    )
    stations: Mapped[list["EveStation"]] = relationship(back_populates="system")


class EveStargate(Base):
    __tablename__ = "eve_stargates"

    stargate_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    system_id: Mapped[int] = mapped_column(ForeignKey("eve_systems.system_id"), nullable=False, index=True)
    destination_system_id: Mapped[int | None] = mapped_column(ForeignKey("eve_systems.system_id"), index=True)
    destination_stargate_id: Mapped[int | None] = mapped_column(Integer, index=True)
    type_id: Mapped[int | None] = mapped_column(Integer, index=True)
    x: Mapped[float | None] = mapped_column(Float)
    y: Mapped[float | None] = mapped_column(Float)
    z: Mapped[float | None] = mapped_column(Float)

    system: Mapped[EveSystem] = relationship(foreign_keys=[system_id], back_populates="outgoing_stargates")
    destination_system: Mapped[EveSystem | None] = relationship(foreign_keys=[destination_system_id])


class EveStation(Base):
    __tablename__ = "eve_stations"

    station_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    system_id: Mapped[int] = mapped_column(ForeignKey("eve_systems.system_id"), nullable=False, index=True)
    type_id: Mapped[int | None] = mapped_column(ForeignKey("eve_types.type_id"), index=True)
    operation_id: Mapped[int | None] = mapped_column(Integer, index=True)
    operation_name: Mapped[str | None] = mapped_column(String(255), index=True)
    name: Mapped[str | None] = mapped_column(String(255), index=True)
    owner_id: Mapped[int | None] = mapped_column(Integer, index=True)
    owner_name: Mapped[str | None] = mapped_column(String(255), index=True)
    celestial_index: Mapped[int | None] = mapped_column(Integer, index=True)
    orbit_index: Mapped[int | None] = mapped_column(Integer, index=True)
    orbit_id: Mapped[int | None] = mapped_column(Integer, index=True)
    x: Mapped[float | None] = mapped_column(Float)
    y: Mapped[float | None] = mapped_column(Float)
    z: Mapped[float | None] = mapped_column(Float)

    system: Mapped[EveSystem] = relationship(back_populates="stations")
    station_type: Mapped[EveType | None] = relationship()
