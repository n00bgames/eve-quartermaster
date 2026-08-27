from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class SystemKillFetchCache(Base):
    __tablename__ = "system_kill_fetch_cache"
    __table_args__ = (UniqueConstraint("system_id", "lookback_hours", "feed", name="uq_system_kill_fetch_cache_window"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    system_id: Mapped[int] = mapped_column(ForeignKey("eve_systems.system_id", ondelete="CASCADE"), nullable=False, index=True)
    lookback_hours: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    feed: Mapped[str] = mapped_column(String(40), default="zkill_industrial", nullable=False, index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    kill_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="success", nullable=False, index=True)
    message: Mapped[str | None] = mapped_column(Text)


class SystemJumpObservation(Base):
    __tablename__ = "system_jump_observations"
    __table_args__ = (UniqueConstraint("system_id", "observed_at", name="uq_system_jump_observation_bucket"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    system_id: Mapped[int] = mapped_column(ForeignKey("eve_systems.system_id", ondelete="CASCADE"), nullable=False, index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ship_jumps: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ship_kills: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pod_kills: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    npc_kills: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source: Mapped[str] = mapped_column(String(40), default="esi_system_jumps", nullable=False, index=True)
    cached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class SystemIndustrialKillObservation(Base):
    __tablename__ = "system_industrial_kill_observations"

    id: Mapped[int] = mapped_column(primary_key=True)
    killmail_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    system_id: Mapped[int] = mapped_column(ForeignKey("eve_systems.system_id", ondelete="CASCADE"), nullable=False, index=True)
    killmail_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    total_value: Mapped[Decimal] = mapped_column(Numeric(24, 2), default=0, nullable=False)
    zkb_url: Mapped[str | None] = mapped_column(String(500))
    victim_ship_type_id: Mapped[int | None] = mapped_column(Integer, index=True)
    victim_hull: Mapped[str | None] = mapped_column(String(255), index=True)
    victim_character_id: Mapped[int | None] = mapped_column(Integer, index=True)
    victim_character_name: Mapped[str | None] = mapped_column(String(255), index=True)
    victim_corporation_id: Mapped[int | None] = mapped_column(Integer, index=True)
    victim_corporation_name: Mapped[str | None] = mapped_column(String(255), index=True)
    victim_alliance_id: Mapped[int | None] = mapped_column(Integer, index=True)
    victim_alliance_name: Mapped[str | None] = mapped_column(String(255), index=True)
    attacker_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    combatant_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    smartbomb_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    location_id: Mapped[int | None] = mapped_column(Integer, index=True)
    location_kind: Mapped[str | None] = mapped_column(String(40), index=True)
    location_name: Mapped[str | None] = mapped_column(String(255), index=True)
    final_blow_character_id: Mapped[int | None] = mapped_column(Integer, index=True)
    final_blow_character_name: Mapped[str | None] = mapped_column(String(255), index=True)
    final_blow_corporation_id: Mapped[int | None] = mapped_column(Integer, index=True)
    final_blow_corporation_name: Mapped[str | None] = mapped_column(String(255), index=True)
    final_blow_alliance_id: Mapped[int | None] = mapped_column(Integer, index=True)
    final_blow_alliance_name: Mapped[str | None] = mapped_column(String(255), index=True)
    final_blow_ship_type_id: Mapped[int | None] = mapped_column(Integer, index=True)
    final_blow_ship_type_name: Mapped[str | None] = mapped_column(String(255), index=True)
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    cached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

class SystemPvpKillObservation(Base):
    __tablename__ = "system_pvp_kill_observations"

    id: Mapped[int] = mapped_column(primary_key=True)
    killmail_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    system_id: Mapped[int] = mapped_column(ForeignKey("eve_systems.system_id", ondelete="CASCADE"), nullable=False, index=True)
    killmail_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    total_value: Mapped[Decimal] = mapped_column(Numeric(24, 2), default=0, nullable=False)
    zkb_url: Mapped[str | None] = mapped_column(String(500))
    victim_ship_type_id: Mapped[int | None] = mapped_column(Integer, index=True)
    victim_hull: Mapped[str | None] = mapped_column(String(255), index=True)
    victim_character_id: Mapped[int | None] = mapped_column(Integer, index=True)
    victim_character_name: Mapped[str | None] = mapped_column(String(255), index=True)
    victim_corporation_id: Mapped[int | None] = mapped_column(Integer, index=True)
    victim_corporation_name: Mapped[str | None] = mapped_column(String(255), index=True)
    victim_alliance_id: Mapped[int | None] = mapped_column(Integer, index=True)
    victim_alliance_name: Mapped[str | None] = mapped_column(String(255), index=True)
    attacker_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    combatant_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    smartbomb_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    location_id: Mapped[int | None] = mapped_column(Integer, index=True)
    location_kind: Mapped[str | None] = mapped_column(String(40), index=True)
    location_name: Mapped[str | None] = mapped_column(String(255), index=True)
    final_blow_character_id: Mapped[int | None] = mapped_column(Integer, index=True)
    final_blow_character_name: Mapped[str | None] = mapped_column(String(255), index=True)
    final_blow_corporation_id: Mapped[int | None] = mapped_column(Integer, index=True)
    final_blow_corporation_name: Mapped[str | None] = mapped_column(String(255), index=True)
    final_blow_alliance_id: Mapped[int | None] = mapped_column(Integer, index=True)
    final_blow_alliance_name: Mapped[str | None] = mapped_column(String(255), index=True)
    final_blow_ship_type_id: Mapped[int | None] = mapped_column(Integer, index=True)
    final_blow_ship_type_name: Mapped[str | None] = mapped_column(String(255), index=True)
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    cached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

