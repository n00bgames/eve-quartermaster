"""Opt-in, account-private sampled travel history; never shared with Intel."""
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class JourneyTracker(Base):
    __tablename__ = 'journey_trackers'
    __table_args__ = (UniqueConstraint('user_id','character_id',name='uq_journey_owner_character'),
        Index('ix_journey_due','enabled','next_poll_at','lease_until'))
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id',ondelete='CASCADE'),nullable=False)
    character_id: Mapped[int] = mapped_column(ForeignKey('eve_characters.id',ondelete='CASCADE'),nullable=False)
    track_ship: Mapped[bool] = mapped_column(Boolean,nullable=False,default=False,server_default='false')
    current_ship_segment_id: Mapped[int | None] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean,nullable=False,default=False)
    interval_seconds: Mapped[int] = mapped_column(Integer,nullable=False,default=15)
    revision: Mapped[int] = mapped_column(Integer,nullable=False,default=0)
    state: Mapped[str] = mapped_column(String(24),nullable=False,default='paused')
    next_poll_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_visit_id: Mapped[int | None] = mapped_column(Integer)
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failures: Mapped[int] = mapped_column(Integer,nullable=False,default=0)


class JourneyVisit(Base):
    __tablename__ = 'journey_visits'
    __table_args__ = (Index('ix_journey_visit_time','tracker_id','first_seen_at'),
        Index('ix_journey_visit_system','tracker_id','system_id'))
    id: Mapped[int] = mapped_column(primary_key=True)
    tracker_id: Mapped[int] = mapped_column(ForeignKey('journey_trackers.id',ondelete='CASCADE'),nullable=False)
    # No SDE FK: retained history survives SDE maintenance/missing coordinates.
    system_id: Mapped[int] = mapped_column(Integer,nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),nullable=False)
    samples: Mapped[int] = mapped_column(Integer,nullable=False,default=1)
    gap_before: Mapped[bool] = mapped_column(Boolean,nullable=False,default=True)


class JourneyShipSegment(Base):
    __tablename__ = 'journey_ship_segments'
    __table_args__ = (Index('ix_journey_ship_visit_time','visit_id','first_seen_at'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey('journey_visits.id',ondelete='CASCADE'),nullable=False)
    # Not an SDE FK: retain the sampled type ID through SDE refreshes.
    ship_type_id: Mapped[int] = mapped_column(Integer,nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),nullable=False)
    samples: Mapped[int] = mapped_column(Integer,nullable=False,default=1)
    gap_before: Mapped[bool] = mapped_column(Boolean,nullable=False,default=True)
