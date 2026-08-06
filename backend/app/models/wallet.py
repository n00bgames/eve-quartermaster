from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class CharacterWalletSnapshot(Base):
    __tablename__ = "character_wallet_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_run_id: Mapped[int] = mapped_column(ForeignKey("snapshot_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("eve_characters.id", ondelete="CASCADE"), nullable=False, index=True)
    character_eve_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    character_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    corporation_id: Mapped[int | None] = mapped_column(ForeignKey("eve_corporations.id", ondelete="SET NULL"), index=True)
    corporation_name: Mapped[str | None] = mapped_column(String(255), index=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(24, 2), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class CharacterWalletJournalEntry(Base):
    __tablename__ = "character_wallet_journal_entries"
    __table_args__ = (UniqueConstraint("character_id", "reference_id", name="uq_character_wallet_journal_reference"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("eve_characters.id", ondelete="CASCADE"), nullable=False, index=True)
    reference_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    reference_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    balance: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    description: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    first_party_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    second_party_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    context_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    context_id_type: Mapped[str | None] = mapped_column(String(80))
    item_type_id: Mapped[int | None] = mapped_column(Integer, index=True)
    item_name: Mapped[str | None] = mapped_column(String(255), index=True)
    quantity: Mapped[int | None] = mapped_column(Integer)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    is_buy: Mapped[bool | None] = mapped_column(Boolean)
    tax: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    tax_receiver_id: Mapped[int | None] = mapped_column(BigInteger)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    character = relationship("EveCharacter")
