from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class CorporationDivision(Base):
    __tablename__ = "corporation_divisions"
    __table_args__ = (
        UniqueConstraint(
            "corporation_id",
            "division_type",
            "division",
            name="uq_corporation_division",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    corporation_id: Mapped[int] = mapped_column(
        ForeignKey("eve_corporations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    division_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    division: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    corporation = relationship("EveCorporation")
