"""corporation wallet divisions

Revision ID: 0012_corp_wallets
Revises: 0011_custom_roles
Create Date: 2026-06-30 02:55:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0012_corp_wallets"
down_revision: Union[str, None] = "0011_custom_roles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "corporation_wallet_divisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("corporation_id", sa.Integer(), nullable=False),
        sa.Column("division", sa.Integer(), nullable=False),
        sa.Column("balance", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["corporation_id"], ["eve_corporations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("corporation_id", "division"),
    )
    op.create_index(op.f("ix_corporation_wallet_divisions_corporation_id"), "corporation_wallet_divisions", ["corporation_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_corporation_wallet_divisions_corporation_id"), table_name="corporation_wallet_divisions")
    op.drop_table("corporation_wallet_divisions")

