"""Public ESI reported-hour samples; each feed retains independent provenance."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class IntelActivitySample(Base):
    __tablename__ = "intel_activity_samples"
    __table_args__ = (UniqueConstraint("system_id", "feed", "observed_at", name="uq_intel_activity_feed_hour"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    system_id: Mapped[int] = mapped_column(ForeignKey("eve_systems.system_id", ondelete="CASCADE"), index=True)
    feed: Mapped[str] = mapped_column(String(8), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    jumps: Mapped[int | None] = mapped_column(Integer)
    ship_kills: Mapped[int | None] = mapped_column(Integer)
    pod_kills: Mapped[int | None] = mapped_column(Integer)
    npc_kills: Mapped[int | None] = mapped_column(Integer)
