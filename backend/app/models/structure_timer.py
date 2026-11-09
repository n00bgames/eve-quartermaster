"""Opt-in structure deadlines and durable recipient deliveries."""
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class StructureTimerConfig(Base):
    __tablename__ = 'structure_timer_configs'
    __table_args__ = (UniqueConstraint('owner_user_id', 'source', 'source_id', 'token_key'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    source: Mapped[str] = mapped_column(String(16))
    source_id: Mapped[str] = mapped_column(String(36))
    token_key: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    roles: Mapped[list] = mapped_column(JSON, default=list)
    minutes: Mapped[list] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(160), default='Not enabled')
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StructureTimer(Base):
    __tablename__ = 'structure_timers'
    __table_args__ = (UniqueConstraint('config_id', 'kind'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    config_id: Mapped[int] = mapped_column(ForeignKey('structure_timer_configs.id'), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    generation: Mapped[int] = mapped_column(Integer, default=1)
    event_id: Mapped[int] = mapped_column(ForeignKey('events.id'), unique=True)


class StructureTimerDelivery(Base):
    __tablename__ = 'structure_timer_deliveries'
    __table_args__ = (UniqueConstraint('timer_id', 'generation', 'minutes', 'user_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    timer_id: Mapped[int] = mapped_column(ForeignKey('structure_timers.id'), index=True)
    generation: Mapped[int] = mapped_column(Integer)
    minutes: Mapped[int] = mapped_column(Integer)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    notice_id: Mapped[int] = mapped_column(ForeignKey('audit_events.id'), unique=True)
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False)
