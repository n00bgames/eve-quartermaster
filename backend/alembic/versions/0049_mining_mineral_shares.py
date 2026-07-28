"""store mineral-share payout snapshots

Revision ID: 0049_mining_mineral_shares
Revises: 0048_eve_type_mass
Create Date: 2026-07-22 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0049_mining_mineral_shares"
down_revision: Union[str, None] = "0048_eve_type_mass"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "mining_settlement_outputs",
        sa.Column("distributed_quantity", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "mining_settlement_outputs",
        sa.Column("retained_quantity", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "mining_settlement_participants",
        sa.Column("mineral_payouts_json", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("mining_settlement_participants", "mineral_payouts_json")
    op.drop_column("mining_settlement_outputs", "retained_quantity")
    op.drop_column("mining_settlement_outputs", "distributed_quantity")