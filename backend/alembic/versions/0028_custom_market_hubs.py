"""custom market hubs

Revision ID: 0028_custom_market_hubs
Revises: 0027_station_names
Create Date: 2026-07-08 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0028_custom_market_hubs"
down_revision: Union[str, None] = "0027_station_names"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "custom_market_hubs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("system_name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_custom_market_hubs_key", "custom_market_hubs", ["key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_custom_market_hubs_key", table_name="custom_market_hubs")
    op.drop_table("custom_market_hubs")
