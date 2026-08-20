from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class CharacterJumpClone(Base):
    __tablename__ = "character_jump_clones"
    __table_args__ = (UniqueConstraint("character_id", "clone_kind", "jump_clone_id", name="uq_character_jump_clone"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("eve_characters.id", ondelete="CASCADE"), nullable=False, index=True)
    clone_kind: Mapped[str] = mapped_column(String(32), default="jump_clone", nullable=False, index=True)
    jump_clone_id: Mapped[int | None] = mapped_column(Integer, index=True)
    name: Mapped[str | None] = mapped_column(String(255))
    location_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    location_type: Mapped[str | None] = mapped_column(String(32))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    character = relationship("EveCharacter")
    implants: Mapped[list["JumpCloneImplant"]] = relationship(back_populates="clone", cascade="all, delete-orphan")


class JumpCloneImplant(Base):
    __tablename__ = "jump_clone_implants"
    __table_args__ = (UniqueConstraint("clone_id", "type_id", name="uq_jump_clone_implant"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    clone_id: Mapped[int] = mapped_column(ForeignKey("character_jump_clones.id", ondelete="CASCADE"), nullable=False, index=True)
    type_id: Mapped[int] = mapped_column(ForeignKey("eve_types.type_id"), nullable=False, index=True)
    slot: Mapped[int | None] = mapped_column(Integer)

    clone: Mapped[CharacterJumpClone] = relationship(back_populates="implants")
    implant_type = relationship("EveType")


class ImplantSet(Base):
    __tablename__ = "implant_sets"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    character_id: Mapped[int | None] = mapped_column(ForeignKey("eve_characters.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    owner_user = relationship("User")
    character = relationship("EveCharacter")
    implants: Mapped[list["ImplantSetImplant"]] = relationship(back_populates="set", cascade="all, delete-orphan")


class ImplantSetImplant(Base):
    __tablename__ = "implant_set_implants"
    __table_args__ = (UniqueConstraint("set_id", "type_id", name="uq_implant_set_implant"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    set_id: Mapped[int] = mapped_column(ForeignKey("implant_sets.id", ondelete="CASCADE"), nullable=False, index=True)
    type_id: Mapped[int] = mapped_column(ForeignKey("eve_types.type_id"), nullable=False, index=True)
    slot: Mapped[int | None] = mapped_column(Integer)

    set: Mapped[ImplantSet] = relationship(back_populates="implants")
    implant_type = relationship("EveType")
