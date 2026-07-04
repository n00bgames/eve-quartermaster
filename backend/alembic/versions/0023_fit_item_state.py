"""add fitting item charge and simulation state

Revision ID: 0023_fit_item_state
Revises: 0022_fitting_drafts
Create Date: 2026-07-03
"""

from alembic import op
import sqlalchemy as sa


revision = "0023_fit_item_state"
down_revision = "0022_fitting_drafts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("character_fitting_items", sa.Column("charge_type_id", sa.Integer(), nullable=True))
    op.add_column("character_fitting_items", sa.Column("simulation_state", sa.String(length=16), nullable=False, server_default="online"))
    op.create_foreign_key("fk_character_fitting_items_charge_type_id", "character_fitting_items", "eve_types", ["charge_type_id"], ["type_id"])
    op.create_index("ix_character_fitting_items_charge_type_id", "character_fitting_items", ["charge_type_id"])
    op.alter_column("character_fitting_items", "simulation_state", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_character_fitting_items_charge_type_id", table_name="character_fitting_items")
    op.drop_constraint("fk_character_fitting_items_charge_type_id", "character_fitting_items", type_="foreignkey")
    op.drop_column("character_fitting_items", "simulation_state")
    op.drop_column("character_fitting_items", "charge_type_id")
