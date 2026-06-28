from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
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
    market_group_id: Mapped[int | None] = mapped_column(Integer, index=True)
    published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    group: Mapped[EveGroup | None] = relationship(back_populates="types")


class EveRegion(Base):
    __tablename__ = "eve_regions"

    region_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)


class EveConstellation(Base):
    __tablename__ = "eve_constellations"

    constellation_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    region_id: Mapped[int | None] = mapped_column(ForeignKey("eve_regions.region_id"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)


class EveSystem(Base):
    __tablename__ = "eve_systems"

    system_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    constellation_id: Mapped[int | None] = mapped_column(ForeignKey("eve_constellations.constellation_id"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    security_status: Mapped[float | None] = mapped_column(Float)
