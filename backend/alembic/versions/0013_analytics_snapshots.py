"""add historical analytics snapshots

Revision ID: 0013_analytics
Revises: 0012_corp_wallets
Create Date: 2026-06-30 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0013_analytics"
down_revision: Union[str, None] = "0012_corp_wallets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "snapshot_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scope_type", sa.String(length=40), nullable=False),
        sa.Column("scope_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
    )
    op.create_index("ix_snapshot_runs_scope_type", "snapshot_runs", ["scope_type"])
    op.create_index("ix_snapshot_runs_scope_id", "snapshot_runs", ["scope_id"])
    op.create_index("ix_snapshot_runs_source", "snapshot_runs", ["source"])
    op.create_index("ix_snapshot_runs_status", "snapshot_runs", ["status"])

    op.create_table(
        "snapshot_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("snapshot_run_id", sa.Integer(), sa.ForeignKey("snapshot_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_type", sa.String(length=40), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("owner_name", sa.String(length=255), nullable=True),
        sa.Column("metric_key", sa.String(length=120), nullable=False),
        sa.Column("metric_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("metric_value", sa.Numeric(24, 2), nullable=False),
        sa.Column("dimensions_json", sa.JSON(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    for column in ["snapshot_run_id", "owner_type", "owner_id", "owner_name", "metric_key", "metric_version", "recorded_at"]:
        op.create_index(f"ix_snapshot_metrics_{column}", "snapshot_metrics", [column])

    op.create_table(
        "character_skill_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("snapshot_run_id", sa.Integer(), sa.ForeignKey("snapshot_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("eve_characters.id"), nullable=False),
        sa.Column("character_eve_id", sa.Integer(), nullable=False),
        sa.Column("character_name", sa.String(length=255), nullable=False),
        sa.Column("total_skill_points", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("unallocated_skill_points", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("skill_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("queue_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("category_name", sa.String(length=255), nullable=True),
        sa.Column("category_skill_points", sa.BigInteger(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    for column in ["snapshot_run_id", "character_id", "character_eve_id", "character_name", "category_name", "recorded_at"]:
        op.create_index(f"ix_character_skill_snapshots_{column}", "character_skill_snapshots", [column])

    op.create_table(
        "corporation_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("snapshot_run_id", sa.Integer(), sa.ForeignKey("snapshot_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("corporation_id", sa.Integer(), sa.ForeignKey("eve_corporations.id"), nullable=False),
        sa.Column("corporation_eve_id", sa.Integer(), nullable=False),
        sa.Column("corporation_name", sa.String(length=255), nullable=False),
        sa.Column("member_count", sa.Integer(), nullable=True),
        sa.Column("wallet_balance", sa.Numeric(24, 2), nullable=False, server_default="0"),
        sa.Column("asset_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("asset_units", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("blueprint_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    for column in ["snapshot_run_id", "corporation_id", "corporation_eve_id", "corporation_name", "recorded_at"]:
        op.create_index(f"ix_corporation_snapshots_{column}", "corporation_snapshots", [column])

    op.create_table(
        "corporation_wallet_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("snapshot_run_id", sa.Integer(), sa.ForeignKey("snapshot_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("corporation_id", sa.Integer(), sa.ForeignKey("eve_corporations.id"), nullable=False),
        sa.Column("corporation_eve_id", sa.Integer(), nullable=False),
        sa.Column("corporation_name", sa.String(length=255), nullable=False),
        sa.Column("division", sa.Integer(), nullable=False),
        sa.Column("balance", sa.Numeric(24, 2), nullable=False, server_default="0"),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    for column in ["snapshot_run_id", "corporation_id", "corporation_eve_id", "corporation_name", "division", "recorded_at"]:
        op.create_index(f"ix_corporation_wallet_snapshots_{column}", "corporation_wallet_snapshots", [column])

    op.create_table(
        "blueprint_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("snapshot_run_id", sa.Integer(), sa.ForeignKey("snapshot_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ownership_entity_id", sa.Integer(), sa.ForeignKey("ownership_entities.id"), nullable=False),
        sa.Column("owner_name", sa.String(length=255), nullable=False),
        sa.Column("blueprint_type_id", sa.Integer(), nullable=False),
        sa.Column("blueprint_type_name", sa.String(length=255), nullable=False),
        sa.Column("material_efficiency", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("time_efficiency", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("runs_remaining", sa.Integer(), nullable=True),
        sa.Column("is_copy", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    for column in ["snapshot_run_id", "ownership_entity_id", "owner_name", "blueprint_type_id", "blueprint_type_name", "is_copy", "recorded_at"]:
        op.create_index(f"ix_blueprint_snapshots_{column}", "blueprint_snapshots", [column])


def downgrade() -> None:
    op.drop_table("blueprint_snapshots")
    op.drop_table("corporation_wallet_snapshots")
    op.drop_table("corporation_snapshots")
    op.drop_table("character_skill_snapshots")
    op.drop_table("snapshot_metrics")
    op.drop_table("snapshot_runs")


