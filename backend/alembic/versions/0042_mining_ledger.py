"""add mining ledger and operation tracking

Revision ID: 0042_mining_ledger
Revises: 0041_corporation_research
Create Date: 2026-07-17 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0042_mining_ledger"
down_revision: Union[str, None] = "0041_corporation_research"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mining_operations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("solar_system_id", sa.Integer(), sa.ForeignKey("eve_systems.system_id"), nullable=True),
        sa.Column("solar_system_name", sa.String(length=255), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    for column in ("name", "solar_system_id", "solar_system_name", "start_at", "end_at", "created_by_user_id"):
        op.create_index(f"ix_mining_operations_{column}", "mining_operations", [column])

    op.create_table(
        "mining_operation_participants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("operation_id", sa.Integer(), sa.ForeignKey("mining_operations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("eve_characters.id"), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="miner"),
        sa.Column("ship_name", sa.String(length=255), nullable=True),
        sa.Column("crystal_name", sa.String(length=255), nullable=True),
        sa.UniqueConstraint("operation_id", "character_id", name="uq_mining_operation_participant"),
    )
    op.create_index("ix_mining_operation_participants_operation_id", "mining_operation_participants", ["operation_id"])
    op.create_index("ix_mining_operation_participants_character_id", "mining_operation_participants", ["character_id"])

    op.create_table(
        "mining_ledger_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("eve_characters.id"), nullable=False),
        sa.Column("operation_id", sa.Integer(), sa.ForeignKey("mining_operations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("mined_date", sa.Date(), nullable=False),
        sa.Column("mined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ore_type_id", sa.Integer(), sa.ForeignKey("eve_types.type_id"), nullable=False),
        sa.Column("solar_system_id", sa.Integer(), sa.ForeignKey("eve_systems.system_id"), nullable=False),
        sa.Column("ore_type_name", sa.String(length=255), nullable=False),
        sa.Column("solar_system_name", sa.String(length=255), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("residue_quantity", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("volume", sa.Numeric(24, 4), nullable=False, server_default="0"),
        sa.Column("residue_volume", sa.Numeric(24, 4), nullable=False, server_default="0"),
        sa.Column("estimated_price", sa.Numeric(24, 2), nullable=False, server_default="0"),
        sa.Column("estimated_residue_price", sa.Numeric(24, 2), nullable=False, server_default="0"),
        sa.Column("has_residue_data", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="esi"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("character_id", "mined_date", "ore_type_id", "solar_system_id", name="uq_mining_ledger_daily_entry"),
    )
    for column in ("character_id", "operation_id", "mined_date", "mined_at", "ore_type_id", "solar_system_id", "ore_type_name", "solar_system_name", "has_residue_data", "source"):
        op.create_index(f"ix_mining_ledger_entries_{column}", "mining_ledger_entries", [column])


def downgrade() -> None:
    op.drop_table("mining_ledger_entries")
    op.drop_table("mining_operation_participants")
    op.drop_table("mining_operations")
