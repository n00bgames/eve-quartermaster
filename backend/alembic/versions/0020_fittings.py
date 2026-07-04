"""add character fittings

Revision ID: 0020_fittings
Revises: 0019_user_tz
Create Date: 2026-07-03 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0020_fittings"
down_revision = "0019_user_tz"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "character_fittings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("eve_fitting_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("ship_type_id", sa.Integer(), nullable=False),
        sa.Column("is_shared", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["eve_characters.id"]),
        sa.ForeignKeyConstraint(["ship_type_id"], ["eve_types.type_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("character_id", "eve_fitting_id", name="uq_character_fitting_esi_id"),
    )
    op.create_index("ix_character_fittings_character_id", "character_fittings", ["character_id"])
    op.create_index("ix_character_fittings_eve_fitting_id", "character_fittings", ["eve_fitting_id"])
    op.create_index("ix_character_fittings_is_shared", "character_fittings", ["is_shared"])
    op.create_index("ix_character_fittings_name", "character_fittings", ["name"])
    op.create_index("ix_character_fittings_ship_type_id", "character_fittings", ["ship_type_id"])

    op.create_table(
        "character_fitting_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fitting_id", sa.Integer(), nullable=False),
        sa.Column("type_id", sa.Integer(), nullable=False),
        sa.Column("flag", sa.String(length=64), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["fitting_id"], ["character_fittings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["type_id"], ["eve_types.type_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_character_fitting_items_fitting_id", "character_fitting_items", ["fitting_id"])
    op.create_index("ix_character_fitting_items_flag", "character_fitting_items", ["flag"])
    op.create_index("ix_character_fitting_items_type_id", "character_fitting_items", ["type_id"])


def downgrade() -> None:
    op.drop_index("ix_character_fitting_items_type_id", table_name="character_fitting_items")
    op.drop_index("ix_character_fitting_items_flag", table_name="character_fitting_items")
    op.drop_index("ix_character_fitting_items_fitting_id", table_name="character_fitting_items")
    op.drop_table("character_fitting_items")
    op.drop_index("ix_character_fittings_ship_type_id", table_name="character_fittings")
    op.drop_index("ix_character_fittings_name", table_name="character_fittings")
    op.drop_index("ix_character_fittings_is_shared", table_name="character_fittings")
    op.drop_index("ix_character_fittings_eve_fitting_id", table_name="character_fittings")
    op.drop_index("ix_character_fittings_character_id", table_name="character_fittings")
    op.drop_table("character_fittings")