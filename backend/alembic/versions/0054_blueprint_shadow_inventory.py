"""track blueprint identity across research jobs

Revision ID: 0054_blueprint_shadow_inventory
Revises: 0053_planetary_industry
Create Date: 2026-07-28 11:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0054_blueprint_shadow_inventory"
down_revision: Union[str, None] = "0053_planetary_industry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("blueprint_snapshots", sa.Column("blueprint_item_id", sa.BigInteger(), nullable=True))
    op.add_column(
        "blueprint_snapshots",
        sa.Column("inventory_state", sa.String(length=30), server_default="inventory", nullable=False),
    )
    op.add_column("blueprint_snapshots", sa.Column("research_job_id", sa.BigInteger(), nullable=True))
    op.create_index(
        op.f("ix_blueprint_snapshots_blueprint_item_id"),
        "blueprint_snapshots",
        ["blueprint_item_id"],
    )
    op.create_index(
        op.f("ix_blueprint_snapshots_inventory_state"),
        "blueprint_snapshots",
        ["inventory_state"],
    )
    op.create_index(
        op.f("ix_blueprint_snapshots_research_job_id"),
        "blueprint_snapshots",
        ["research_job_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_blueprint_snapshots_research_job_id"), table_name="blueprint_snapshots")
    op.drop_index(op.f("ix_blueprint_snapshots_inventory_state"), table_name="blueprint_snapshots")
    op.drop_index(op.f("ix_blueprint_snapshots_blueprint_item_id"), table_name="blueprint_snapshots")
    op.drop_column("blueprint_snapshots", "research_job_id")
    op.drop_column("blueprint_snapshots", "inventory_state")
    op.drop_column("blueprint_snapshots", "blueprint_item_id")
