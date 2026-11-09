"""Account-private, user-entered POS readings, independent of ESI tokens."""
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ManualPos(Base):
    __tablename__ = "manual_pos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    tower_type: Mapped[str] = mapped_column(String(160))
    corporation_name: Mapped[str] = mapped_column(String(160))
    location: Mapped[str] = mapped_column(String(240))
    state: Mapped[str] = mapped_column(String(20))
    fuel_blocks: Mapped[int | None] = mapped_column(Integer)
    fuel_per_hour: Mapped[float] = mapped_column(Float)
    stront_units: Mapped[int | None] = mapped_column(Integer)
    stront_per_hour: Mapped[float] = mapped_column(Float)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reinforced_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
