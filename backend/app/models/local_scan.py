"""Immutable public local-scan snapshots; no private ESI data is retained."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Index, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class LocalScanReport(Base):
    __tablename__ = "local_scan_reports"
    __table_args__ = (Index("ix_local_scan_owner_created", "created_by_user_id", "created_at"),)

    report_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="local", server_default="local", index=True)
    token: Mapped[str] = mapped_column(String(48), primary_key=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    # Public EVE corporation ID, explicitly selected from the creator's linked corporations.
    corporation_id: Mapped[int | None] = mapped_column(Integer, index=True)
    account_name: Mapped[str] = mapped_column(String(120), nullable=False)
    application_version: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    retention: Mapped[str] = mapped_column(String(16), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)


class ScanHighlight(Base):
    __tablename__ = "scan_highlights"
    __table_args__ = (UniqueConstraint("user_id", "kind", "eve_id", name="uq_scan_highlight_owner_entity"),
                     CheckConstraint("kind IN ('corporation','alliance')", name="ck_scan_highlight_kind"))
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    eve_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
