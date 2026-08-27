"""Retain structure type for docking eligibility.

Revision ID: 0076_location_structure_type
Revises: 0075_battle_report_shares
"""

from alembic import op
import sqlalchemy as sa


revision = "0076_location_structure_type"
down_revision = "0075_battle_report_shares"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("locations", sa.Column("type_id", sa.Integer(), sa.ForeignKey("eve_types.type_id")))
    op.create_index("ix_locations_type_id", "locations", ["type_id"])


def downgrade() -> None:
    op.drop_index("ix_locations_type_id", table_name="locations")
    op.drop_column("locations", "type_id")
