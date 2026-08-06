"""Require explicit consent for corporation wallet analytics.

Revision ID: 0064_wallet_corporation_opt_in
Revises: 0063_wallet_transaction_details
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0064_wallet_corporation_opt_in"
down_revision: Union[str, None] = "0063_wallet_transaction_details"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Deliberately default every existing and future character to excluded.
    # Prior privacy flags are not interpreted as consent.
    op.add_column(
        "eve_characters",
        sa.Column("wallet_corporation_analytics_opt_in", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.drop_column("eve_characters", "wallet_owner_only")


def downgrade() -> None:
    op.add_column(
        "eve_characters",
        sa.Column("wallet_owner_only", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.drop_column("eve_characters", "wallet_corporation_analytics_opt_in")
