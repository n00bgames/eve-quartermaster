from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class Killmail(Base):
    """Canonical ESI killmail plus denormalized victim fields used by analytics."""

    __tablename__ = "killmails"

    killmail_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    killmail_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    killmail_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    # Deliberately not an FK: canonical killmails remain ingestible before an SDE import.
    solar_system_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    victim_character_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    victim_corporation_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    victim_alliance_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    victim_faction_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    victim_ship_type_id: Mapped[int | None] = mapped_column(Integer, index=True)
    damage_taken: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    war_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    canonical_esi_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    attackers: Mapped[list["KillmailAttacker"]] = relationship(back_populates="killmail", cascade="all, delete-orphan")
    items: Mapped[list["KillmailItem"]] = relationship(back_populates="killmail", cascade="all, delete-orphan")
    enrichment: Mapped["ZkillEnrichment | None"] = relationship(back_populates="killmail", cascade="all, delete-orphan", uselist=False)
    discoveries: Mapped[list["KillmailDiscovery"]] = relationship(back_populates="killmail", cascade="all, delete-orphan")


class KillmailAttacker(Base):
    __tablename__ = "killmail_attackers"
    __table_args__ = (UniqueConstraint("killmail_id", "attacker_index", name="uq_killmail_attacker_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    killmail_id: Mapped[int] = mapped_column(ForeignKey("killmails.killmail_id", ondelete="CASCADE"), nullable=False, index=True)
    attacker_index: Mapped[int] = mapped_column(Integer, nullable=False)
    character_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    corporation_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    alliance_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    faction_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    ship_type_id: Mapped[int | None] = mapped_column(Integer, index=True)
    weapon_type_id: Mapped[int | None] = mapped_column(Integer, index=True)
    damage_done: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    final_blow: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    security_status: Mapped[float | None] = mapped_column(Float)

    killmail: Mapped[Killmail] = relationship(back_populates="attackers")


class KillmailItem(Base):
    __tablename__ = "killmail_items"
    __table_args__ = (UniqueConstraint("killmail_id", "item_index", name="uq_killmail_item_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    killmail_id: Mapped[int] = mapped_column(ForeignKey("killmails.killmail_id", ondelete="CASCADE"), nullable=False, index=True)
    item_index: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_item_index: Mapped[int | None] = mapped_column(Integer)
    item_type_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    flag: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    singleton: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quantity_destroyed: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    quantity_dropped: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    killmail: Mapped[Killmail] = relationship(back_populates="items")


class ZkillEnrichment(Base):
    __tablename__ = "zkill_enrichment"

    killmail_id: Mapped[int] = mapped_column(ForeignKey("killmails.killmail_id", ondelete="CASCADE"), primary_key=True)
    estimated_total_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    points: Mapped[int | None] = mapped_column(Integer)
    solo: Mapped[bool | None] = mapped_column(Boolean)
    npc: Mapped[bool | None] = mapped_column(Boolean)
    awox: Mapped[bool | None] = mapped_column(Boolean)
    zkill_url: Mapped[str] = mapped_column(String(500), nullable=False)
    raw_enrichment_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    killmail: Mapped[Killmail] = relationship(back_populates="enrichment")


class KillmailDiscovery(Base):
    """Records why a killmail is in EQM without treating zKill as canonical."""

    __tablename__ = "killmail_discoveries"
    __table_args__ = (UniqueConstraint("killmail_id", "owner_type", "owner_id", "feed", name="uq_killmail_discovery_owner_feed"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    killmail_id: Mapped[int] = mapped_column(ForeignKey("killmails.killmail_id", ondelete="CASCADE"), nullable=False, index=True)
    owner_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    feed: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    killmail: Mapped[Killmail] = relationship(back_populates="discoveries")


class KillboardSyncRun(Base):
    """Durable, resumable cursor for a multi-entity zKill -> ESI synchronization."""

    __tablename__ = "killboard_sync_runs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    initiated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="queued", nullable=False, index=True)
    targets_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    target_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    feed: Mapped[str] = mapped_column(String(16), default="kills", nullable=False)
    page: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    lookback_days: Mapped[int] = mapped_column(Integer, nullable=False)
    discovered_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    imported_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class KillboardEntityName(Base):
    """Public EVE entity-name cache for killmail participants outside EQM's roster."""

    __tablename__ = "killboard_entity_names"

    eve_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(255), index=True)
    resolution_status: Mapped[str] = mapped_column(String(24), default="resolved", nullable=False, index=True)
    last_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
