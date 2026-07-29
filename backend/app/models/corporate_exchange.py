from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class ExchangeListing(Base):
    __tablename__ = "exchange_listings"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    seller_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    seller_character_id: Mapped[int | None] = mapped_column(ForeignKey("eve_characters.id", ondelete="SET NULL"), index=True)
    seller_corporation_id: Mapped[int | None] = mapped_column(ForeignKey("eve_corporations.id", ondelete="SET NULL"), index=True)
    listing_type: Mapped[str] = mapped_column(String(32), default="fixed", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    summary: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    contact_method: Mapped[str | None] = mapped_column(String(255))
    quantity_total: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    quantity_available: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    asking_price: Mapped[float | None] = mapped_column(Numeric(24, 2))
    minimum_bid: Mapped[float | None] = mapped_column(Numeric(24, 2))
    reserve_price: Mapped[float | None] = mapped_column(Numeric(24, 2))
    sell_as_complete_lot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    bid_visibility: Mapped[str] = mapped_column(String(32), default="private", nullable=False)
    visibility: Mapped[str] = mapped_column(String(32), default="users", nullable=False, index=True)
    eligibility_notes: Mapped[str | None] = mapped_column(Text)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"), index=True)
    location_text: Mapped[str | None] = mapped_column(String(500))
    division_name: Mapped[str | None] = mapped_column(String(255))
    condition_notes: Mapped[str | None] = mapped_column(String(500))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    seller_user = relationship("User", foreign_keys=[seller_user_id])
    seller_character = relationship("EveCharacter", foreign_keys=[seller_character_id])
    seller_corporation = relationship("EveCorporation", foreign_keys=[seller_corporation_id])
    location = relationship("Location")
    items: Mapped[list["ExchangeListingItem"]] = relationship(back_populates="listing", cascade="all, delete-orphan")
    appraisals: Mapped[list["ExchangeAppraisal"]] = relationship(back_populates="listing", cascade="all, delete-orphan")
    claims: Mapped[list["ExchangeClaim"]] = relationship(back_populates="listing", cascade="all, delete-orphan")
    bids: Mapped[list["ExchangeBid"]] = relationship(back_populates="listing", cascade="all, delete-orphan")


class ExchangeListingItem(Base):
    __tablename__ = "exchange_listing_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("exchange_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    type_id: Mapped[int | None] = mapped_column(ForeignKey("eve_types.type_id", ondelete="SET NULL"), index=True)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("assets.id", ondelete="SET NULL"), index=True)
    item_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500))

    listing: Mapped[ExchangeListing] = relationship(back_populates="items")
    item_type = relationship("EveType")
    asset = relationship("Asset")


class ExchangeAppraisal(Base):
    __tablename__ = "exchange_appraisals"

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("exchange_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    hub_key: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    hub_name: Mapped[str] = mapped_column(String(120), nullable=False)
    immediate_buy_value: Mapped[float | None] = mapped_column(Numeric(24, 2))
    immediate_sell_value: Mapped[float | None] = mapped_column(Numeric(24, 2))
    replacement_value: Mapped[float | None] = mapped_column(Numeric(24, 2))
    source: Mapped[str] = mapped_column(String(80), default="ESI market orders", nullable=False)
    priced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    listing: Mapped[ExchangeListing] = relationship(back_populates="appraisals")


class ExchangeClaim(Base):
    __tablename__ = "exchange_claims"

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("exchange_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    claimant_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float | None] = mapped_column(Numeric(24, 2))
    total_price: Mapped[float | None] = mapped_column(Numeric(24, 2))
    status: Mapped[str] = mapped_column(String(32), default="reserved", nullable=False, index=True)
    contract_id: Mapped[int | None] = mapped_column(BigInteger)
    contract_notes: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    listing: Mapped[ExchangeListing] = relationship(back_populates="claims")
    claimant_user = relationship("User", foreign_keys=[claimant_user_id])


class ExchangeBid(Base):
    __tablename__ = "exchange_bids"

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("exchange_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    bidder_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    bidder_name: Mapped[str | None] = mapped_column(String(255))
    bidder_contact: Mapped[str | None] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(24, 2), nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    listing: Mapped[ExchangeListing] = relationship(back_populates="bids")
    bidder_user = relationship("User", foreign_keys=[bidder_user_id])


class ExchangeTransaction(Base):
    __tablename__ = "exchange_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("exchange_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    claim_id: Mapped[int | None] = mapped_column(ForeignKey("exchange_claims.id", ondelete="SET NULL"), index=True)
    bid_id: Mapped[int | None] = mapped_column(ForeignKey("exchange_bids.id", ondelete="SET NULL"), index=True)
    seller_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    buyer_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    total_price: Mapped[float | None] = mapped_column(Numeric(24, 2))
    status: Mapped[str] = mapped_column(String(32), default="reserved", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ExchangeNotification(Base):
    __tablename__ = "exchange_notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    listing_id: Mapped[int | None] = mapped_column(ForeignKey("exchange_listings.id", ondelete="CASCADE"), index=True)
    notification_kind: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ExchangeAuditLog(Base):
    __tablename__ = "exchange_audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int | None] = mapped_column(ForeignKey("exchange_listings.id", ondelete="SET NULL"), index=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    event_kind: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
