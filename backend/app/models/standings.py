from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class CharacterStanding(Base):
    __tablename__ = "character_standings"
    __table_args__ = (
        UniqueConstraint(
            "character_id",
            "source_type",
            "source_eve_id",
            name="uq_character_standing_source",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(
        ForeignKey("eve_characters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    source_eve_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    standing: Mapped[float] = mapped_column(Numeric(7, 4), nullable=False)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    character = relationship("EveCharacter")
