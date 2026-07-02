"""add industrial kill cache

Revision ID: 0015_industrial_kill_cache
Revises: 0014_nav_map
Create Date: 2026-07-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0015_industrial_kill_cache"
down_revision: Union[str, None] = "0014_nav_map"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "system_kill_fetch_cache",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("system_id", sa.Integer(), sa.ForeignKey("eve_systems.system_id", ondelete="CASCADE"), nullable=False),
        sa.Column("lookback_hours", sa.Integer(), nullable=False),
        sa.Column("feed", sa.String(length=40), nullable=False, server_default="zkill_industrial"),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kill_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="success"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.UniqueConstraint("system_id", "lookback_hours", "feed", name="uq_system_kill_fetch_cache_window"),
    )
    for name, column in {
        "ix_skfc_system": "system_id",
        "ix_skfc_lookback": "lookback_hours",
        "ix_skfc_feed": "feed",
        "ix_skfc_fetched": "fetched_at",
        "ix_skfc_expires": "expires_at",
        "ix_skfc_status": "status",
    }.items():
        op.create_index(name, "system_kill_fetch_cache", [column])

    op.create_table(
        "system_industrial_kill_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("killmail_id", sa.Integer(), nullable=False, unique=True),
        sa.Column("system_id", sa.Integer(), sa.ForeignKey("eve_systems.system_id", ondelete="CASCADE"), nullable=False),
        sa.Column("killmail_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_value", sa.Numeric(24, 2), nullable=False, server_default="0"),
        sa.Column("zkb_url", sa.String(length=500), nullable=True),
        sa.Column("victim_ship_type_id", sa.Integer(), nullable=True),
        sa.Column("victim_hull", sa.String(length=255), nullable=True),
        sa.Column("victim_character_id", sa.Integer(), nullable=True),
        sa.Column("victim_character_name", sa.String(length=255), nullable=True),
        sa.Column("victim_corporation_id", sa.Integer(), nullable=True),
        sa.Column("victim_corporation_name", sa.String(length=255), nullable=True),
        sa.Column("victim_alliance_id", sa.Integer(), nullable=True),
        sa.Column("victim_alliance_name", sa.String(length=255), nullable=True),
        sa.Column("attacker_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("combatant_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("location_id", sa.Integer(), nullable=True),
        sa.Column("location_kind", sa.String(length=40), nullable=True),
        sa.Column("location_name", sa.String(length=255), nullable=True),
        sa.Column("final_blow_character_id", sa.Integer(), nullable=True),
        sa.Column("final_blow_character_name", sa.String(length=255), nullable=True),
        sa.Column("final_blow_corporation_id", sa.Integer(), nullable=True),
        sa.Column("final_blow_corporation_name", sa.String(length=255), nullable=True),
        sa.Column("final_blow_alliance_id", sa.Integer(), nullable=True),
        sa.Column("final_blow_alliance_name", sa.String(length=255), nullable=True),
        sa.Column("final_blow_ship_type_id", sa.Integer(), nullable=True),
        sa.Column("final_blow_ship_type_name", sa.String(length=255), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("cached_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    for name, column in {
        "ix_siko_killmail": "killmail_id",
        "ix_siko_system": "system_id",
        "ix_siko_time": "killmail_time",
        "ix_siko_v_ship_type": "victim_ship_type_id",
        "ix_siko_v_hull": "victim_hull",
        "ix_siko_v_char_id": "victim_character_id",
        "ix_siko_v_char_name": "victim_character_name",
        "ix_siko_v_corp_id": "victim_corporation_id",
        "ix_siko_v_corp_name": "victim_corporation_name",
        "ix_siko_v_alli_id": "victim_alliance_id",
        "ix_siko_v_alli_name": "victim_alliance_name",
        "ix_siko_attackers": "attacker_count",
        "ix_siko_location_id": "location_id",
        "ix_siko_location_kind": "location_kind",
        "ix_siko_location_name": "location_name",
        "ix_siko_fb_char_id": "final_blow_character_id",
        "ix_siko_fb_char_name": "final_blow_character_name",
        "ix_siko_fb_corp_id": "final_blow_corporation_id",
        "ix_siko_fb_corp_name": "final_blow_corporation_name",
        "ix_siko_fb_alli_id": "final_blow_alliance_id",
        "ix_siko_fb_alli_name": "final_blow_alliance_name",
        "ix_siko_fb_ship_type": "final_blow_ship_type_id",
        "ix_siko_fb_ship_name": "final_blow_ship_type_name",
        "ix_siko_cached": "cached_at",
    }.items():
        op.create_index(name, "system_industrial_kill_observations", [column])


def downgrade() -> None:
    op.drop_table("system_industrial_kill_observations")
    op.drop_table("system_kill_fetch_cache")