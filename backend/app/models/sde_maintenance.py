from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class SdeMaintenanceJob(Base):
    __tablename__ = "sde_maintenance_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    active_key: Mapped[str | None] = mapped_column(String(16), unique=True)
    action: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    stage: Mapped[str] = mapped_column(String(120))
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    source_path: Mapped[str | None] = mapped_column(Text)
    options: Mapped[dict] = mapped_column(JSON, default=dict)
    progress: Mapped[dict] = mapped_column(JSON, default=dict)
    archive: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
