from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class CharacterFitting(Base):
    __tablename__ = "character_fittings"
    __table_args__ = (UniqueConstraint("character_id", "eve_fitting_id", name="uq_character_fitting_esi_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("eve_characters.id"), nullable=False, index=True)
    eve_fitting_id: Mapped[int | None] = mapped_column(Integer, index=True)
    source_fitting_id: Mapped[int | None] = mapped_column(ForeignKey("character_fittings.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    ship_type_id: Mapped[int] = mapped_column(ForeignKey("eve_types.type_id"), nullable=False, index=True)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_draft: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    character = relationship("EveCharacter")
    ship_type = relationship("EveType")
    source_fitting: Mapped["CharacterFitting | None"] = relationship(remote_side=[id])
    items: Mapped[list["CharacterFittingItem"]] = relationship(back_populates="fitting", cascade="all, delete-orphan")


class CharacterFittingItem(Base):
    __tablename__ = "character_fitting_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    fitting_id: Mapped[int] = mapped_column(ForeignKey("character_fittings.id", ondelete="CASCADE"), nullable=False, index=True)
    type_id: Mapped[int] = mapped_column(ForeignKey("eve_types.type_id"), nullable=False, index=True)
    charge_type_id: Mapped[int | None] = mapped_column(ForeignKey("eve_types.type_id"), nullable=True, index=True)
    flag: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    simulation_state: Mapped[str] = mapped_column(String(16), default="online", nullable=False)

    fitting: Mapped[CharacterFitting] = relationship(back_populates="items")
    item_type = relationship("EveType", foreign_keys=[type_id])
    charge_type = relationship("EveType", foreign_keys=[charge_type_id])
