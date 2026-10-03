from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PlexTransaction(Base):
    __tablename__ = "plex_transactions"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_plex_quantity"),
        CheckConstraint("unit_price IS NULL OR unit_price >= 0", name="ck_plex_price"),
        CheckConstraint("fees >= 0", name="ck_plex_fees"),
        CheckConstraint("kind IN ('buy', 'opening', 'sell', 'consume')", name="ck_plex_kind"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    fees: Mapped[Decimal] = mapped_column(Numeric(24, 2), default=0)
    note: Mapped[str] = mapped_column(Text, default="")


class PlexMarketCache(Base):
    __tablename__ = "plex_market_cache"
    key: Mapped[str] = mapped_column(String(20), primary_key=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict] = mapped_column(JSON)
