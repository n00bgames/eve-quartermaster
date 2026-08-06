"""Add market transaction details to character wallet history.

Revision ID: 0063_wallet_transaction_details
Revises: 0062_character_wallet_analytics
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0063_wallet_transaction_details"
down_revision: Union[str, None] = "0062_character_wallet_analytics"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("character_wallet_journal_entries", sa.Column("item_type_id", sa.Integer()))
    op.add_column("character_wallet_journal_entries", sa.Column("item_name", sa.String(255)))
    op.add_column("character_wallet_journal_entries", sa.Column("quantity", sa.Integer()))
    op.add_column("character_wallet_journal_entries", sa.Column("unit_price", sa.Numeric(24, 2)))
    op.add_column("character_wallet_journal_entries", sa.Column("is_buy", sa.Boolean()))
    op.create_index("ix_character_wallet_journal_item_type", "character_wallet_journal_entries", ["item_type_id"])
    op.create_index("ix_character_wallet_journal_item_name", "character_wallet_journal_entries", ["item_name"])


def downgrade() -> None:
    op.drop_index("ix_character_wallet_journal_item_name", table_name="character_wallet_journal_entries")
    op.drop_index("ix_character_wallet_journal_item_type", table_name="character_wallet_journal_entries")
    op.drop_column("character_wallet_journal_entries", "is_buy")
    op.drop_column("character_wallet_journal_entries", "unit_price")
    op.drop_column("character_wallet_journal_entries", "quantity")
    op.drop_column("character_wallet_journal_entries", "item_name")
    op.drop_column("character_wallet_journal_entries", "item_type_id")
