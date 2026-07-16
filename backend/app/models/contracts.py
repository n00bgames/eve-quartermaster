from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class EveContract(Base):
    __tablename__ = "eve_contracts"
    __table_args__ = (
        Index(
            "uq_eve_contracts_character_contract",
            "contract_id",
            "character_id",
            unique=True,
            postgresql_where=text("scope_type = 'character' AND character_id IS NOT NULL"),
        ),
        Index(
            "uq_eve_contracts_corporation_contract",
            "contract_id",
            "corporation_id",
            unique=True,
            postgresql_where=text("scope_type = 'corporation' AND corporation_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    scope_type: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    character_id: Mapped[int | None] = mapped_column(ForeignKey("eve_characters.id"), index=True)
    corporation_id: Mapped[int | None] = mapped_column(ForeignKey("eve_corporations.id"), index=True)
    issuer_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    issuer_corporation_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    assignee_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    acceptor_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    for_corporation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    contract_type: Mapped[str | None] = mapped_column(String(40), index=True)
    status: Mapped[str | None] = mapped_column(String(40), index=True)
    title: Mapped[str | None] = mapped_column(String(255))
    availability: Mapped[str | None] = mapped_column(String(40), index=True)
    date_issued: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    date_expired: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    date_accepted: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    date_completed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    start_location_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    end_location_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    start_location_name: Mapped[str | None] = mapped_column(String(255))
    end_location_name: Mapped[str | None] = mapped_column(String(255))
    price: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    reward: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    collateral: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    buyout: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    volume: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    days_to_complete: Mapped[int | None] = mapped_column(Integer)
    raw_json: Mapped[str | None] = mapped_column(Text)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    owner_user = relationship("User")
    character = relationship("EveCharacter")
    corporation = relationship("EveCorporation")
