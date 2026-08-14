"""Add canonical killboard storage and resumable synchronization.

Revision ID: 0070_killboard
Revises: 0069_doctrine_skill_plans
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0070_killboard"
down_revision: Union[str, None] = "0069_doctrine_skill_plans"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "killmails",
        sa.Column("killmail_id", sa.BigInteger(), primary_key=True),
        sa.Column("killmail_hash", sa.String(length=128), nullable=False),
        sa.Column("killmail_time", sa.DateTime(timezone=True), nullable=False),
        # The SDE is optional at ingestion time; name resolution joins this ID when available.
        sa.Column("solar_system_id", sa.Integer(), nullable=False),
        sa.Column("victim_character_id", sa.BigInteger()),
        sa.Column("victim_corporation_id", sa.BigInteger()),
        sa.Column("victim_alliance_id", sa.BigInteger()),
        sa.Column("victim_faction_id", sa.BigInteger()),
        sa.Column("victim_ship_type_id", sa.Integer()),
        sa.Column("damage_taken", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("war_id", sa.BigInteger()),
        sa.Column("canonical_esi_payload", sa.JSON(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    for column in ("killmail_time", "solar_system_id", "victim_character_id", "victim_corporation_id", "victim_alliance_id", "victim_faction_id", "victim_ship_type_id", "war_id", "last_updated_at"):
        op.create_index(f"ix_killmails_{column}", "killmails", [column])

    op.create_table(
        "killmail_attackers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("killmail_id", sa.BigInteger(), sa.ForeignKey("killmails.killmail_id", ondelete="CASCADE"), nullable=False),
        sa.Column("attacker_index", sa.Integer(), nullable=False),
        sa.Column("character_id", sa.BigInteger()), sa.Column("corporation_id", sa.BigInteger()),
        sa.Column("alliance_id", sa.BigInteger()), sa.Column("faction_id", sa.BigInteger()),
        sa.Column("ship_type_id", sa.Integer()), sa.Column("weapon_type_id", sa.Integer()),
        sa.Column("damage_done", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("final_blow", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("security_status", sa.Float()),
        sa.UniqueConstraint("killmail_id", "attacker_index", name="uq_killmail_attacker_index"),
    )
    for column in ("killmail_id", "character_id", "corporation_id", "alliance_id", "faction_id", "ship_type_id", "weapon_type_id", "final_blow"):
        op.create_index(f"ix_killmail_attackers_{column}", "killmail_attackers", [column])

    op.create_table(
        "killmail_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("killmail_id", sa.BigInteger(), sa.ForeignKey("killmails.killmail_id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_index", sa.Integer(), nullable=False), sa.Column("parent_item_index", sa.Integer()),
        sa.Column("item_type_id", sa.Integer(), nullable=False), sa.Column("flag", sa.Integer(), nullable=False),
        sa.Column("singleton", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quantity_destroyed", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("quantity_dropped", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("raw_payload", sa.JSON()),
        sa.UniqueConstraint("killmail_id", "item_index", name="uq_killmail_item_index"),
    )
    for column in ("killmail_id", "item_type_id", "flag"):
        op.create_index(f"ix_killmail_items_{column}", "killmail_items", [column])

    op.create_table(
        "zkill_enrichment",
        sa.Column("killmail_id", sa.BigInteger(), sa.ForeignKey("killmails.killmail_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("estimated_total_value", sa.Numeric(24, 2)), sa.Column("points", sa.Integer()),
        sa.Column("solo", sa.Boolean()), sa.Column("npc", sa.Boolean()), sa.Column("awox", sa.Boolean()),
        sa.Column("zkill_url", sa.String(length=500), nullable=False),
        sa.Column("raw_enrichment_payload", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_table(
        "killmail_discoveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("killmail_id", sa.BigInteger(), sa.ForeignKey("killmails.killmail_id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_type", sa.String(length=32), nullable=False), sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("feed", sa.String(length=16), nullable=False),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("killmail_id", "owner_type", "owner_id", "feed", name="uq_killmail_discovery_owner_feed"),
    )
    for column in ("killmail_id", "owner_type", "owner_id", "feed"):
        op.create_index(f"ix_killmail_discoveries_{column}", "killmail_discoveries", [column])

    op.create_table(
        "killboard_sync_runs",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("initiated_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="queued"),
        sa.Column("targets_json", sa.JSON(), nullable=False), sa.Column("target_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("feed", sa.String(length=16), nullable=False, server_default="kills"), sa.Column("page", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("lookback_days", sa.Integer(), nullable=False),
        sa.Column("discovered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    for column in ("initiated_by_user_id", "status", "updated_at"):
        op.create_index(f"ix_killboard_sync_runs_{column}", "killboard_sync_runs", [column])


def downgrade() -> None:
    op.drop_table("killboard_sync_runs")
    op.drop_table("killmail_discoveries")
    op.drop_table("zkill_enrichment")
    op.drop_table("killmail_items")
    op.drop_table("killmail_attackers")
    op.drop_table("killmails")
