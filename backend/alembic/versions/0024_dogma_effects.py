"""add dogma effects for fitting simulation

Revision ID: 0024_dogma_effects
Revises: 0023_fit_item_state
Create Date: 2026-07-04
"""

from alembic import op
import sqlalchemy as sa


revision = "0024_dogma_effects"
down_revision = "0023_fit_item_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "eve_dogma_effects",
        sa.Column("effect_id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_assistance", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_offensive", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_warp_safe", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("modifier_info", sa.JSON(), nullable=True),
    )
    op.create_index("ix_eve_dogma_effects_name", "eve_dogma_effects", ["name"])
    op.create_index("ix_eve_dogma_effects_display_name", "eve_dogma_effects", ["display_name"])
    op.create_index("ix_eve_dogma_effects_category_id", "eve_dogma_effects", ["category_id"])

    op.create_table(
        "eve_type_dogma_effects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("type_id", sa.Integer(), nullable=False),
        sa.Column("effect_id", sa.Integer(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["type_id"], ["eve_types.type_id"]),
        sa.ForeignKeyConstraint(["effect_id"], ["eve_dogma_effects.effect_id"]),
        sa.UniqueConstraint("type_id", "effect_id", name="uq_eve_type_dogma_effect"),
    )
    op.create_index("ix_eve_type_dogma_effects_type_id", "eve_type_dogma_effects", ["type_id"])
    op.create_index("ix_eve_type_dogma_effects_effect_id", "eve_type_dogma_effects", ["effect_id"])


def downgrade() -> None:
    op.drop_index("ix_eve_type_dogma_effects_effect_id", table_name="eve_type_dogma_effects")
    op.drop_index("ix_eve_type_dogma_effects_type_id", table_name="eve_type_dogma_effects")
    op.drop_table("eve_type_dogma_effects")
    op.drop_index("ix_eve_dogma_effects_category_id", table_name="eve_dogma_effects")
    op.drop_index("ix_eve_dogma_effects_display_name", table_name="eve_dogma_effects")
    op.drop_index("ix_eve_dogma_effects_name", table_name="eve_dogma_effects")
    op.drop_table("eve_dogma_effects")
