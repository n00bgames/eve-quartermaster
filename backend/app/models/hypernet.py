from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class HyperNetOffer(Base):
    __tablename__ = "hypernet_offers"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_hypernet_offers_quantity"),
        CheckConstraint("total_nodes > 0", name="ck_hypernet_offers_total_nodes"),
        CheckConstraint("nodes_sold >= 0 AND nodes_sold <= total_nodes", name="ck_hypernet_offers_nodes_sold"),
        CheckConstraint("seller_owned_nodes >= 0 AND seller_owned_nodes <= nodes_sold", name="ck_hypernet_offers_seeded_nodes"),
        CheckConstraint("hypercores_required >= 0", name="ck_hypernet_offers_hypercores"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    seller_character_id: Mapped[int] = mapped_column(ForeignKey("eve_characters.id", ondelete="RESTRICT"), nullable=False, index=True)
    type_id: Mapped[int] = mapped_column(ForeignKey("eve_types.type_id", ondelete="RESTRICT"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"), index=True)
    location_name_snapshot: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False, index=True)
    visibility: Mapped[str] = mapped_column(String(24), default="personal", nullable=False, index=True)
    created_offer_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    total_offer_price: Mapped[Decimal] = mapped_column(Numeric(24, 2), nullable=False)
    total_nodes: Mapped[int] = mapped_column(Integer, nullable=False)
    nodes_sold: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    seller_owned_nodes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unique_participants: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hypercores_required: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hypercore_unit_cost: Mapped[Decimal] = mapped_column(Numeric(24, 2), default=0, nullable=False)
    acquisition_cost: Mapped[Decimal] = mapped_column(Numeric(24, 2), default=0, nullable=False)
    desired_profit: Mapped[Decimal] = mapped_column(Numeric(24, 2), default=0, nullable=False)
    completion_fee: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    payout: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    actual_hypercore_cost: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    final_market_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    final_profit: Mapped[Decimal | None] = mapped_column(Numeric(24, 2), index=True)
    winner: Mapped[str | None] = mapped_column(String(32))
    item_outcome: Mapped[str] = mapped_column(String(32), default="committed", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(32), default="manual", nullable=False, index=True)
    source_reference: Mapped[str | None] = mapped_column(String(255), index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    owner_user = relationship("User", foreign_keys=[owner_user_id])
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])
    seller_character = relationship("EveCharacter")
    item_type = relationship("EveType")
    location = relationship("Location")
    snapshots: Mapped[list["HyperNetOfferSnapshot"]] = relationship(back_populates="offer", cascade="all, delete-orphan")
    participants: Mapped[list["HyperNetParticipant"]] = relationship(back_populates="offer", cascade="all, delete-orphan")


class HyperNetOfferSnapshot(Base):
    __tablename__ = "hypernet_offer_snapshots"
    __table_args__ = (
        CheckConstraint("nodes_sold >= 0", name="ck_hypernet_snapshots_nodes_sold"),
        CheckConstraint("seller_owned_nodes >= 0 AND seller_owned_nodes <= nodes_sold", name="ck_hypernet_snapshots_seeded_nodes"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("hypernet_offers.id", ondelete="CASCADE"), nullable=False, index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    nodes_sold: Mapped[int] = mapped_column(Integer, nullable=False)
    seller_owned_nodes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unique_participants: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    jita_buy: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    jita_sell: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    local_buy: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    local_sell: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    hypercore_buy: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    hypercore_sell: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    note: Mapped[str | None] = mapped_column(Text)
    screenshot_attachment_id: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)

    offer: Mapped[HyperNetOffer] = relationship(back_populates="snapshots")
    created_by_user = relationship("User")


class HyperNetParticipant(Base):
    __tablename__ = "hypernet_participants"
    __table_args__ = (UniqueConstraint("offer_id", "participant_name", name="uq_hypernet_participant_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("hypernet_offers.id", ondelete="CASCADE"), nullable=False, index=True)
    character_id: Mapped[int | None] = mapped_column(ForeignKey("eve_characters.id", ondelete="SET NULL"), index=True)
    participant_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    nodes_owned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_seller: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    offer: Mapped[HyperNetOffer] = relationship(back_populates="participants")
    character = relationship("EveCharacter")


class HyperNetParticipation(Base):
    __tablename__ = "hypernet_participation"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("eve_characters.id", ondelete="RESTRICT"), nullable=False, index=True)
    external_offer_reference: Mapped[str | None] = mapped_column(String(255), index=True)
    item_type_id: Mapped[int] = mapped_column(ForeignKey("eve_types.type_id", ondelete="RESTRICT"), nullable=False, index=True)
    seller_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"), index=True)
    nodes_purchased: Mapped[int] = mapped_column(Integer, nullable=False)
    node_price: Mapped[Decimal] = mapped_column(Numeric(24, 2), nullable=False)
    total_spent: Mapped[Decimal] = mapped_column(Numeric(24, 2), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    won: Mapped[bool | None] = mapped_column(Boolean)
    item_value_at_completion: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    profit_loss: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    notes: Mapped[str | None] = mapped_column(Text)

    user = relationship("User")
    character = relationship("EveCharacter")
    item_type = relationship("EveType")
    location = relationship("Location")


class HyperNetSetting(Base):
    __tablename__ = "hypernet_settings"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    monthly_node_limit: Mapped[int | None] = mapped_column(Integer)
    monthly_spend_limit: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    warning_threshold_percent: Mapped[int] = mapped_column(Integer, default=80, nullable=False)
    preferred_market_hub: Mapped[str] = mapped_column(String(32), default="jita", nullable=False)
    default_hypercore_price_source: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User")
