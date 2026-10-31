"""Stored scan and Industry reports with explicit privacy and optional current-data views."""
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Index, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class LocalScanReport(Base):
    __tablename__ = "local_scan_reports"
    __table_args__ = (Index("ix_local_scan_owner_created", "created_by_user_id", "created_at"),)

    is_private: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    anonymous: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    dynamic: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
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
                     CheckConstraint("kind IN ('corporation','alliance')", name="ck_scan_highlight_kind"),
                     CheckConstraint("color IN ('red','orange','blue','light_blue','green','purple','gray')", name="ck_scan_highlight_color"))
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    eve_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    color: Mapped[str] = mapped_column(String(16), default="red", server_default="red", nullable=False)


class ScanColorSettings(Base):
    __tablename__ = "scan_color_settings"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    character_id: Mapped[int | None] = mapped_column(ForeignKey("eve_characters.id", ondelete="SET NULL"))
    contact_colors: Mapped[list] = mapped_column(JSON, default=list, server_default="[]", nullable=False)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
