"""Add hourly ship and pod kill counts to system activity observations.

Revision ID: 0077_system_activity_kills
Revises: 0076_location_structure_type
"""

from alembic import op
import sqlalchemy as sa


revision = "0077_system_activity_kills"
down_revision = "0076_location_structure_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("system_jump_observations", sa.Column("ship_kills", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("system_jump_observations", sa.Column("pod_kills", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("system_jump_observations", sa.Column("npc_kills", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("system_jump_observations", "npc_kills")
    op.drop_column("system_jump_observations", "pod_kills")
    op.drop_column("system_jump_observations", "ship_kills")
