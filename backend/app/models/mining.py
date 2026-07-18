from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class MiningOperation(Base):
    __tablename__ = "mining_operations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    solar_system_id: Mapped[int | None] = mapped_column(ForeignKey("eve_systems.system_id"), index=True)
    solar_system_name: Mapped[str | None] = mapped_column(String(255), index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    system = relationship("EveSystem")
    created_by_user = relationship("User")
    participants: Mapped[list["MiningOperationParticipant"]] = relationship(back_populates="operation", cascade="all, delete-orphan")
    entries: Mapped[list["MiningLedgerEntry"]] = relationship(back_populates="operation")


class MiningOperationParticipant(Base):
    __tablename__ = "mining_operation_participants"
    __table_args__ = (UniqueConstraint("operation_id", "character_id", name="uq_mining_operation_participant"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    operation_id: Mapped[int] = mapped_column(ForeignKey("mining_operations.id", ondelete="CASCADE"), nullable=False, index=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("eve_characters.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), default="miner", nullable=False)
    ship_name: Mapped[str | None] = mapped_column(String(255))
    crystal_name: Mapped[str | None] = mapped_column(String(255))

    operation: Mapped[MiningOperation] = relationship(back_populates="participants")
    character = relationship("EveCharacter")


class MiningLedgerEntry(Base):
    __tablename__ = "mining_ledger_entries"
    __table_args__ = (
        UniqueConstraint("character_id", "mined_date", "ore_type_id", "solar_system_id", name="uq_mining_ledger_daily_entry"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("eve_characters.id"), nullable=False, index=True)
    operation_id: Mapped[int | None] = mapped_column(ForeignKey("mining_operations.id", ondelete="SET NULL"), index=True)
    mined_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    mined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    ore_type_id: Mapped[int] = mapped_column(ForeignKey("eve_types.type_id"), nullable=False, index=True)
    solar_system_id: Mapped[int] = mapped_column(ForeignKey("eve_systems.system_id"), nullable=False, index=True)
    ore_type_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    solar_system_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    residue_quantity: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    volume: Mapped[float] = mapped_column(Numeric(24, 4), default=0, nullable=False)
    residue_volume: Mapped[float] = mapped_column(Numeric(24, 4), default=0, nullable=False)
    estimated_price: Mapped[float] = mapped_column(Numeric(24, 2), default=0, nullable=False)
    estimated_residue_price: Mapped[float] = mapped_column(Numeric(24, 2), default=0, nullable=False)
    has_residue_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(20), default="esi", nullable=False, index=True)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    character = relationship("EveCharacter")
    operation: Mapped[MiningOperation | None] = relationship(back_populates="entries")
    ore_type = relationship("EveType")
    system = relationship("EveSystem")
