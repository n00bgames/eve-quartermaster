"""add pvp kill intel cache

Revision ID: 0017_pvp_intel
Revises: 0016_jf_planner
Create Date: 2026-07-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0017_pvp_intel"
down_revision: Union[str, None] = "0016_jf_planner"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "system_pvp_kill_observations",
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
        "ix_spko_killmail": "killmail_id",
        "ix_spko_system": "system_id",
        "ix_spko_time": "killmail_time",
        "ix_spko_v_ship_type": "victim_ship_type_id",
        "ix_spko_v_hull": "victim_hull",
        "ix_spko_v_char_id": "victim_character_id",
        "ix_spko_v_char_name": "victim_character_name",
        "ix_spko_v_corp_id": "victim_corporation_id",
        "ix_spko_v_corp_name": "victim_corporation_name",
        "ix_spko_v_alli_id": "victim_alliance_id",
        "ix_spko_v_alli_name": "victim_alliance_name",
        "ix_spko_attackers": "attacker_count",
        "ix_spko_location_id": "location_id",
        "ix_spko_location_kind": "location_kind",
        "ix_spko_location_name": "location_name",
        "ix_spko_fb_char_id": "final_blow_character_id",
        "ix_spko_fb_char_name": "final_blow_character_name",
        "ix_spko_fb_corp_id": "final_blow_corporation_id",
        "ix_spko_fb_corp_name": "final_blow_corporation_name",
        "ix_spko_fb_alli_id": "final_blow_alliance_id",
        "ix_spko_fb_alli_name": "final_blow_alliance_name",
        "ix_spko_fb_ship_type": "final_blow_ship_type_id",
        "ix_spko_fb_ship_name": "final_blow_ship_type_name",
        "ix_spko_cached": "cached_at",
    }.items():
        op.create_index(name, "system_pvp_kill_observations", [column])


def downgrade() -> None:
    op.drop_table("system_pvp_kill_observations")
