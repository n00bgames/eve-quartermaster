from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ResearchProject(Base):
    __tablename__ = "research_projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    character_id: Mapped[int | None] = mapped_column(ForeignKey("eve_characters.id"), nullable=True, index=True)
    corporation_id: Mapped[int | None] = mapped_column(ForeignKey("eve_corporations.id"), nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(20), default="character", nullable=False, index=True)
    installer_name: Mapped[str | None] = mapped_column(String(255))
    installer_character_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    completed_character_id: Mapped[int | None] = mapped_column(BigInteger)
    activity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    blueprint_id: Mapped[int | None] = mapped_column(BigInteger)
    blueprint_type_id: Mapped[int | None] = mapped_column(ForeignKey("eve_types.type_id"), index=True)
    product_type_id: Mapped[int | None] = mapped_column(ForeignKey("eve_types.type_id"), index=True)
    facility_id: Mapped[int | None] = mapped_column(BigInteger)
    station_id: Mapped[int | None] = mapped_column(BigInteger)
    facility_name: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    runs: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    licensed_runs: Mapped[int | None] = mapped_column(Integer)
    successful_runs: Mapped[int | None] = mapped_column(Integer)
    probability: Mapped[float | None] = mapped_column(Numeric(10, 6))
    cost: Mapped[float | None] = mapped_column(Numeric(20, 2))
    duration: Mapped[int | None] = mapped_column(Integer)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    pause_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    character = relationship("EveCharacter")
    corporation = relationship("EveCorporation")
    blueprint_type = relationship("EveType", foreign_keys=[blueprint_type_id])
    product_type = relationship("EveType", foreign_keys=[product_type_id])
