from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
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


class MiningSettlement(Base):
    __tablename__ = "mining_settlements"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    operation_id: Mapped[int | None] = mapped_column(ForeignKey("mining_operations.id", ondelete="SET NULL"), index=True)
    source_type: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    source_signature: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_filter_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    range_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    range_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)
    contribution_basis: Mapped[str] = mapped_column(String(40), nullable=False)
    settlement_mode: Mapped[str] = mapped_column(String(20), default="isk", nullable=False)
    price_source: Mapped[str] = mapped_column(String(40), default="manual", nullable=False)
    reserve_method: Mapped[str] = mapped_column(String(30), default="none", nullable=False)
    reserve_entered_value: Mapped[float] = mapped_column(Numeric(24, 8), default=0, nullable=False)
    reserve_normalized_percentage: Mapped[float | None] = mapped_column(Numeric(12, 10))
    refining_pilot_name: Mapped[str | None] = mapped_column(String(255))
    refining_pilot_character_id: Mapped[int | None] = mapped_column(ForeignKey("eve_characters.id", ondelete="SET NULL"), index=True)
    refining_location: Mapped[str | None] = mapped_column(String(500))
    stated_refine_percent: Mapped[float | None] = mapped_column(Numeric(12, 10))
    gross_value: Mapped[float] = mapped_column(Numeric(24, 2), default=0, nullable=False)
    reserve_value: Mapped[float] = mapped_column(Numeric(24, 2), default=0, nullable=False)
    deduction_total: Mapped[float] = mapped_column(Numeric(24, 2), default=0, nullable=False)
    distributable_value: Mapped[float] = mapped_column(Numeric(24, 2), default=0, nullable=False)
    fixed_payout_total: Mapped[float] = mapped_column(Numeric(24, 2), default=0, nullable=False)
    share_pool_value: Mapped[float] = mapped_column(Numeric(24, 2), default=0, nullable=False)
    participant_payout_total: Mapped[float] = mapped_column(Numeric(24, 2), default=0, nullable=False)
    unallocated_remainder: Mapped[float] = mapped_column(Numeric(24, 2), default=0, nullable=False)
    warnings_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    operation = relationship("MiningOperation")
    refining_pilot = relationship("EveCharacter", foreign_keys=[refining_pilot_character_id])
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])
    outputs: Mapped[list["MiningSettlementOutput"]] = relationship(back_populates="settlement", cascade="all, delete-orphan")
    participants: Mapped[list["MiningSettlementParticipant"]] = relationship(back_populates="settlement", cascade="all, delete-orphan")
    deductions: Mapped[list["MiningSettlementDeduction"]] = relationship(back_populates="settlement", cascade="all, delete-orphan")
    ledger_links: Mapped[list["MiningSettlementLedgerEntry"]] = relationship(back_populates="settlement", cascade="all, delete-orphan")


class MiningSettlementOutput(Base):
    __tablename__ = "mining_settlement_outputs"
    __table_args__ = (UniqueConstraint("settlement_id", "type_id", name="uq_mining_settlement_output_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    settlement_id: Mapped[int] = mapped_column(ForeignKey("mining_settlements.id", ondelete="CASCADE"), nullable=False, index=True)
    type_id: Mapped[int] = mapped_column(ForeignKey("eve_types.type_id"), nullable=False, index=True)
    type_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    distributed_quantity: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    retained_quantity: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(24, 4), default=0, nullable=False)
    total_value: Mapped[float] = mapped_column(Numeric(24, 2), default=0, nullable=False)
    stated_refine_percent: Mapped[float | None] = mapped_column(Numeric(12, 10))
    price_source: Mapped[str] = mapped_column(String(40), default="manual", nullable=False)
    price_overridden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    settlement: Mapped[MiningSettlement] = relationship(back_populates="outputs")
    type = relationship("EveType")


class MiningSettlementParticipant(Base):
    __tablename__ = "mining_settlement_participants"

    id: Mapped[int] = mapped_column(primary_key=True)
    settlement_id: Mapped[int] = mapped_column(ForeignKey("mining_settlements.id", ondelete="CASCADE"), nullable=False, index=True)
    character_id: Mapped[int | None] = mapped_column(ForeignKey("eve_characters.id", ondelete="SET NULL"), index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    ore_types_snapshot: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    contribution_quantity: Mapped[float] = mapped_column(Numeric(30, 4), default=0, nullable=False)
    contribution_volume: Mapped[float] = mapped_column(Numeric(24, 4), default=0, nullable=False)
    contribution_value: Mapped[float] = mapped_column(Numeric(24, 2), default=0, nullable=False)
    contribution_basis_value: Mapped[float] = mapped_column(Numeric(30, 4), default=0, nullable=False)
    contribution_percentage: Mapped[float] = mapped_column(Numeric(12, 10), default=0, nullable=False)
    compensation_method: Mapped[str] = mapped_column(String(20), nullable=False)
    fixed_percentage: Mapped[float | None] = mapped_column(Numeric(12, 10))
    share_weight: Mapped[float | None] = mapped_column(Numeric(30, 8))
    share_weight_overridden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    payout_ratio: Mapped[float] = mapped_column(Numeric(12, 10), default=0, nullable=False)
    payout_isk: Mapped[float] = mapped_column(Numeric(24, 2), default=0, nullable=False)
    mineral_payouts_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    settlement: Mapped[MiningSettlement] = relationship(back_populates="participants")
    character = relationship("EveCharacter")


class MiningSettlementDeduction(Base):
    __tablename__ = "mining_settlement_deductions"

    id: Mapped[int] = mapped_column(primary_key=True)
    settlement_id: Mapped[int] = mapped_column(ForeignKey("mining_settlements.id", ondelete="CASCADE"), nullable=False, index=True)
    deduction_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    calculation_method: Mapped[str] = mapped_column(String(20), nullable=False)
    entered_value: Mapped[float] = mapped_column(Numeric(24, 8), default=0, nullable=False)
    normalized_percentage: Mapped[float | None] = mapped_column(Numeric(12, 10))
    calculated_amount: Mapped[float] = mapped_column(Numeric(24, 2), default=0, nullable=False)

    settlement: Mapped[MiningSettlement] = relationship(back_populates="deductions")


class MiningSettlementLedgerEntry(Base):
    __tablename__ = "mining_settlement_ledger_entries"
    __table_args__ = (UniqueConstraint("settlement_id", "ledger_entry_id", name="uq_mining_settlement_ledger_entry"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    settlement_id: Mapped[int] = mapped_column(ForeignKey("mining_settlements.id", ondelete="CASCADE"), nullable=False, index=True)
    ledger_entry_id: Mapped[int] = mapped_column(ForeignKey("mining_ledger_entries.id", ondelete="RESTRICT"), nullable=False, index=True)
    character_id: Mapped[int | None] = mapped_column(ForeignKey("eve_characters.id", ondelete="SET NULL"), index=True)
    contribution_snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    settlement: Mapped[MiningSettlement] = relationship(back_populates="ledger_links")
    ledger_entry = relationship("MiningLedgerEntry")
    character = relationship("EveCharacter")