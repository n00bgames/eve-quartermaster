from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.enums import SyncStatus


class EsiApplication(Base):
    __tablename__ = "esi_applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    client_id: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_client_secret: Mapped[str | None] = mapped_column(Text)
    callback_url: Mapped[str] = mapped_column(String(500), nullable=False)


class EsiToken(Base):
    __tablename__ = "esi_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("eve_characters.id"), nullable=False, index=True)
    scopes: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    access_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EsiSyncJob(Base):
    __tablename__ = "esi_sync_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_id: Mapped[int | None] = mapped_column(ForeignKey("esi_tokens.id"), index=True)
    ownership_entity_id: Mapped[int | None] = mapped_column(ForeignKey("ownership_entities.id"), index=True)
    sync_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    status: Mapped[SyncStatus] = mapped_column(default=SyncStatus.QUEUED, nullable=False, index=True)
    message: Mapped[str | None] = mapped_column(Text)
    esi_etag: Mapped[str | None] = mapped_column(String(255))
    esi_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
