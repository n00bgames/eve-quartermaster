from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class CharacterSkill(Base):
    __tablename__ = "character_skills"
    __table_args__ = (UniqueConstraint("character_id", "skill_type_id", name="uq_character_skill"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("eve_characters.id"), nullable=False, index=True)
    skill_type_id: Mapped[int] = mapped_column(ForeignKey("eve_types.type_id"), nullable=False, index=True)
    trained_skill_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active_skill_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skillpoints_in_skill: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    character = relationship("EveCharacter")
    skill_type = relationship("EveType")


class CharacterSkillQueueEntry(Base):
    __tablename__ = "character_skill_queue_entries"
    __table_args__ = (UniqueConstraint("character_id", "queue_position", name="uq_character_skill_queue_position"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("eve_characters.id"), nullable=False, index=True)
    queue_position: Mapped[int] = mapped_column(Integer, nullable=False)
    skill_type_id: Mapped[int] = mapped_column(ForeignKey("eve_types.type_id"), nullable=False, index=True)
    finished_level: Mapped[int] = mapped_column(Integer, nullable=False)
    training_start_sp: Mapped[int | None] = mapped_column(Integer)
    level_start_sp: Mapped[int | None] = mapped_column(Integer)
    level_end_sp: Mapped[int | None] = mapped_column(Integer)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finish_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())

    character = relationship("EveCharacter")
    skill_type = relationship("EveType")
