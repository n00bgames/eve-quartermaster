from datetime import date, datetime, time

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class ManufacturingJob(Base):
    __tablename__ = "manufacturing_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    output_type_id: Mapped[int | None] = mapped_column(ForeignKey("eve_types.type_id"), index=True)
    output_quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    activity_flags: Mapped[str] = mapped_column(String(160), default="manufacturing", nullable=False, index=True)
    research_runs: Mapped[int | None] = mapped_column(Integer)
    me_start: Mapped[int | None] = mapped_column(Integer)
    me_target: Mapped[int | None] = mapped_column(Integer)
    te_start: Mapped[int | None] = mapped_column(Integer)
    te_target: Mapped[int | None] = mapped_column(Integer)
    copy_runs: Mapped[int | None] = mapped_column(Integer)
    invention_runs: Mapped[int | None] = mapped_column(Integer)
    invention_successes: Mapped[int | None] = mapped_column(Integer)
    output_disposition: Mapped[str] = mapped_column(String(40), default="pending", nullable=False, index=True)
    output_sale_price: Mapped[float | None] = mapped_column(Numeric(24, 2))
    output_sale_notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False, index=True)
    cost_to_run: Mapped[float | None] = mapped_column(Numeric(24, 2))
    time_to_run: Mapped[str | None] = mapped_column(String(80))
    date_started: Mapped[date | None] = mapped_column(Date)
    time_started: Mapped[time | None] = mapped_column(Time)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    output_type = relationship("EveType")
    items: Mapped[list["ManufacturingJobItem"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class ManufacturingJobItem(Base):
    __tablename__ = "manufacturing_job_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("manufacturing_jobs.id"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    item_type_id: Mapped[int | None] = mapped_column(ForeignKey("eve_types.type_id"), index=True)
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(24, 4), default=1, nullable=False)
    unit_price: Mapped[float | None] = mapped_column(Numeric(24, 2))
    price_paid: Mapped[float | None] = mapped_column(Numeric(24, 2))
    notes: Mapped[str | None] = mapped_column(Text)

    job: Mapped[ManufacturingJob] = relationship(back_populates="items")
    item_type = relationship("EveType")

