from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class EvePlanetSchematic(Base):
    __tablename__ = "eve_planet_schematics"

    schematic_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    cycle_time: Mapped[int] = mapped_column(Integer, nullable=False)
    output_type_id: Mapped[int] = mapped_column(
        ForeignKey("eve_types.type_id"),
        nullable=False,
        index=True,
    )
    output_quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    output_type = relationship("EveType")
    inputs: Mapped[list["EvePlanetSchematicInput"]] = relationship(
        back_populates="schematic",
        cascade="all, delete-orphan",
    )


class EvePlanetSchematicInput(Base):
    __tablename__ = "eve_planet_schematic_inputs"
    __table_args__ = (
        UniqueConstraint(
            "schematic_id",
            "type_id",
            name="uq_eve_planet_schematic_input",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    schematic_id: Mapped[int] = mapped_column(
        ForeignKey("eve_planet_schematics.schematic_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type_id: Mapped[int] = mapped_column(
        ForeignKey("eve_types.type_id"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    schematic: Mapped[EvePlanetSchematic] = relationship(back_populates="inputs")
    item_type = relationship("EveType")
