"""Add character wallet history and privacy controls.

Revision ID: 0062_character_wallet_analytics
Revises: 0061_hypernet_tracker
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0062_character_wallet_analytics"
down_revision: Union[str, None] = "0061_hypernet_tracker"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("eve_characters", sa.Column("current_wallet_balance", sa.Numeric(24, 2)))
    op.add_column("eve_characters", sa.Column("wallet_synced_at", sa.DateTime(timezone=True)))
    op.add_column("eve_characters", sa.Column("wallet_history_opt_out", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("eve_characters", sa.Column("wallet_owner_only", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("eve_corporations", sa.Column("character_wallet_totals_visible", sa.Boolean(), nullable=False, server_default=sa.text("false")))

    op.create_table(
        "character_wallet_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("snapshot_run_id", sa.Integer(), sa.ForeignKey("snapshot_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("eve_characters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("character_eve_id", sa.Integer(), nullable=False),
        sa.Column("character_name", sa.String(255), nullable=False),
        sa.Column("corporation_id", sa.Integer(), sa.ForeignKey("eve_corporations.id", ondelete="SET NULL")),
        sa.Column("corporation_name", sa.String(255)),
        sa.Column("balance", sa.Numeric(24, 2), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for name, columns in (
        ("ix_character_wallet_snapshots_run", ["snapshot_run_id"]),
        ("ix_character_wallet_snapshots_character_time", ["character_id", "recorded_at"]),
        ("ix_character_wallet_snapshots_character_eve", ["character_eve_id"]),
        ("ix_character_wallet_snapshots_corporation_time", ["corporation_id", "recorded_at"]),
        ("ix_character_wallet_snapshots_character_name", ["character_name"]),
        ("ix_character_wallet_snapshots_corporation_name", ["corporation_name"]),
    ):
        op.create_index(name, "character_wallet_snapshots", columns)

    op.create_table(
        "character_wallet_journal_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("eve_characters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reference_id", sa.BigInteger(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reference_type", sa.String(100), nullable=False),
        sa.Column("amount", sa.Numeric(24, 2)),
        sa.Column("balance", sa.Numeric(24, 2)),
        sa.Column("description", sa.Text()),
        sa.Column("reason", sa.Text()),
        sa.Column("first_party_id", sa.BigInteger()),
        sa.Column("second_party_id", sa.BigInteger()),
        sa.Column("context_id", sa.BigInteger()),
        sa.Column("context_id_type", sa.String(80)),
        sa.Column("tax", sa.Numeric(24, 2)),
        sa.Column("tax_receiver_id", sa.BigInteger()),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("character_id", "reference_id", name="uq_character_wallet_journal_reference"),
    )
    op.create_index("ix_character_wallet_journal_character_time", "character_wallet_journal_entries", ["character_id", "occurred_at"])
    op.create_index("ix_character_wallet_journal_reference", "character_wallet_journal_entries", ["reference_id"])
    op.create_index("ix_character_wallet_journal_type", "character_wallet_journal_entries", ["reference_type"])
    op.create_index("ix_character_wallet_journal_first_party", "character_wallet_journal_entries", ["first_party_id"])
    op.create_index("ix_character_wallet_journal_second_party", "character_wallet_journal_entries", ["second_party_id"])
    op.create_index("ix_character_wallet_journal_context", "character_wallet_journal_entries", ["context_id"])


def downgrade() -> None:
    op.drop_table("character_wallet_journal_entries")
    op.drop_table("character_wallet_snapshots")
    op.drop_column("eve_corporations", "character_wallet_totals_visible")
    op.drop_column("eve_characters", "wallet_owner_only")
    op.drop_column("eve_characters", "wallet_history_opt_out")
    op.drop_column("eve_characters", "wallet_synced_at")
    op.drop_column("eve_characters", "current_wallet_balance")
