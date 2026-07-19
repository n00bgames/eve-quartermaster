"""add mining settlement snapshots

Revision ID: 0043_mining_settlements
Revises: 0042_mining_ledger
Create Date: 2026-07-18 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0043_mining_settlements"
down_revision: Union[str, None] = "0042_mining_ledger"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mining_settlements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("operation_id", sa.Integer(), sa.ForeignKey("mining_operations.id", ondelete="SET NULL")),
        sa.Column("source_type", sa.String(24), nullable=False),
        sa.Column("source_signature", sa.String(64), nullable=False),
        sa.Column("source_filter_json", sa.JSON(), nullable=False),
        sa.Column("range_start", sa.DateTime(timezone=True)),
        sa.Column("range_end", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("contribution_basis", sa.String(40), nullable=False),
        sa.Column("settlement_mode", sa.String(20), nullable=False, server_default="isk"),
        sa.Column("price_source", sa.String(40), nullable=False, server_default="manual"),
        sa.Column("reserve_method", sa.String(30), nullable=False, server_default="none"),
        sa.Column("reserve_entered_value", sa.Numeric(24, 8), nullable=False, server_default="0"),
        sa.Column("reserve_normalized_percentage", sa.Numeric(12, 10)),
        sa.Column("refining_pilot_name", sa.String(255)),
        sa.Column("refining_pilot_character_id", sa.Integer(), sa.ForeignKey("eve_characters.id", ondelete="SET NULL")),
        sa.Column("refining_location", sa.String(500)),
        sa.Column("stated_refine_percent", sa.Numeric(12, 10)),
        sa.Column("gross_value", sa.Numeric(24, 2), nullable=False, server_default="0"),
        sa.Column("reserve_value", sa.Numeric(24, 2), nullable=False, server_default="0"),
        sa.Column("deduction_total", sa.Numeric(24, 2), nullable=False, server_default="0"),
        sa.Column("distributable_value", sa.Numeric(24, 2), nullable=False, server_default="0"),
        sa.Column("fixed_payout_total", sa.Numeric(24, 2), nullable=False, server_default="0"),
        sa.Column("share_pool_value", sa.Numeric(24, 2), nullable=False, server_default="0"),
        sa.Column("participant_payout_total", sa.Numeric(24, 2), nullable=False, server_default="0"),
        sa.Column("unallocated_remainder", sa.Numeric(24, 2), nullable=False, server_default="0"),
        sa.Column("warnings_json", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finalized_at", sa.DateTime(timezone=True)),
    )
    for column in ("name", "operation_id", "source_type", "source_signature", "range_start", "range_end", "status", "refining_pilot_character_id", "created_by_user_id", "finalized_at"):
        op.create_index(f"ix_mining_settlements_{column}", "mining_settlements", [column])

    op.create_table(
        "mining_settlement_outputs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("settlement_id", sa.Integer(), sa.ForeignKey("mining_settlements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type_id", sa.Integer(), sa.ForeignKey("eve_types.type_id"), nullable=False),
        sa.Column("type_name_snapshot", sa.String(255), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("unit_price", sa.Numeric(24, 4), nullable=False, server_default="0"),
        sa.Column("total_value", sa.Numeric(24, 2), nullable=False, server_default="0"),
        sa.Column("stated_refine_percent", sa.Numeric(12, 10)),
        sa.Column("price_source", sa.String(40), nullable=False, server_default="manual"),
        sa.Column("price_overridden", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("settlement_id", "type_id", name="uq_mining_settlement_output_type"),
    )
    op.create_index("ix_mining_settlement_outputs_settlement_id", "mining_settlement_outputs", ["settlement_id"])
    op.create_index("ix_mining_settlement_outputs_type_id", "mining_settlement_outputs", ["type_id"])

    op.create_table(
        "mining_settlement_participants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("settlement_id", sa.Integer(), sa.ForeignKey("mining_settlements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("eve_characters.id", ondelete="SET NULL")),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(80), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("ore_types_snapshot", sa.JSON(), nullable=False),
        sa.Column("contribution_quantity", sa.Numeric(30, 4), nullable=False, server_default="0"),
        sa.Column("contribution_volume", sa.Numeric(24, 4), nullable=False, server_default="0"),
        sa.Column("contribution_value", sa.Numeric(24, 2), nullable=False, server_default="0"),
        sa.Column("contribution_basis_value", sa.Numeric(30, 4), nullable=False, server_default="0"),
        sa.Column("contribution_percentage", sa.Numeric(12, 10), nullable=False, server_default="0"),
        sa.Column("compensation_method", sa.String(20), nullable=False),
        sa.Column("fixed_percentage", sa.Numeric(12, 10)),
        sa.Column("share_weight", sa.Numeric(30, 8)),
        sa.Column("share_weight_overridden", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("payout_ratio", sa.Numeric(12, 10), nullable=False, server_default="0"),
        sa.Column("payout_isk", sa.Numeric(24, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text()),
    )
    for column in ("settlement_id", "character_id", "display_name", "role", "source"):
        op.create_index(f"ix_mining_settlement_participants_{column}", "mining_settlement_participants", [column])

    op.create_table(
        "mining_settlement_deductions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("settlement_id", sa.Integer(), sa.ForeignKey("mining_settlements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("deduction_type", sa.String(40), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("calculation_method", sa.String(20), nullable=False),
        sa.Column("entered_value", sa.Numeric(24, 8), nullable=False, server_default="0"),
        sa.Column("normalized_percentage", sa.Numeric(12, 10)),
        sa.Column("calculated_amount", sa.Numeric(24, 2), nullable=False, server_default="0"),
    )
    op.create_index("ix_mining_settlement_deductions_settlement_id", "mining_settlement_deductions", ["settlement_id"])
    op.create_index("ix_mining_settlement_deductions_deduction_type", "mining_settlement_deductions", ["deduction_type"])

    op.create_table(
        "mining_settlement_ledger_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("settlement_id", sa.Integer(), sa.ForeignKey("mining_settlements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ledger_entry_id", sa.Integer(), sa.ForeignKey("mining_ledger_entries.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("eve_characters.id", ondelete="SET NULL")),
        sa.Column("contribution_snapshot_json", sa.JSON(), nullable=False),
        sa.UniqueConstraint("settlement_id", "ledger_entry_id", name="uq_mining_settlement_ledger_entry"),
    )
    for column in ("settlement_id", "ledger_entry_id", "character_id"):
        op.create_index(f"ix_mining_settlement_ledger_entries_{column}", "mining_settlement_ledger_entries", [column])


def downgrade() -> None:
    op.drop_table("mining_settlement_ledger_entries")
    op.drop_table("mining_settlement_deductions")
    op.drop_table("mining_settlement_participants")
    op.drop_table("mining_settlement_outputs")
    op.drop_table("mining_settlements")
