from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    note_type: Mapped[str] = mapped_column(String(20), default="freeform", nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    body: Mapped[str | None] = mapped_column(Text)
    destination_system_id: Mapped[int | None] = mapped_column(ForeignKey("eve_systems.system_id", ondelete="SET NULL"), index=True)
    destination_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"), index=True)
    source_market_hub_key: Mapped[str | None] = mapped_column(String(120))
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    owner_user = relationship("User")
    destination_system = relationship("EveSystem")
    destination_location = relationship("Location")
    items: Mapped[list["NoteItem"]] = relationship(back_populates="note", cascade="all, delete-orphan", order_by="NoteItem.sort_order")


class NoteItem(Base):
    __tablename__ = "note_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    note_id: Mapped[int] = mapped_column(ForeignKey("notes.id", ondelete="CASCADE"), nullable=False, index=True)
    type_id: Mapped[int | None] = mapped_column(ForeignKey("eve_types.type_id", ondelete="SET NULL"), index=True)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    requested_quantity: Mapped[int] = mapped_column(BigInteger, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="needed", nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    note: Mapped[Note] = relationship(back_populates="items")
    item_type = relationship("EveType")