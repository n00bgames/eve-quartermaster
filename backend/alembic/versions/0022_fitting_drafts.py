"""add editable fitting drafts

Revision ID: 0022_fitting_drafts
Revises: 0021_dogma_attrs
Create Date: 2026-07-03
"""

from alembic import op
import sqlalchemy as sa


revision = "0022_fitting_drafts"
down_revision = "0021_dogma_attrs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("character_fittings", sa.Column("source_fitting_id", sa.Integer(), nullable=True))
    op.add_column("character_fittings", sa.Column("is_draft", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("character_fittings", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_character_fittings_source_fitting_id", "character_fittings", "character_fittings", ["source_fitting_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_character_fittings_source_fitting_id", "character_fittings", ["source_fitting_id"])
    op.create_index("ix_character_fittings_is_draft", "character_fittings", ["is_draft"])


def downgrade() -> None:
    op.drop_index("ix_character_fittings_is_draft", table_name="character_fittings")
    op.drop_index("ix_character_fittings_source_fitting_id", table_name="character_fittings")
    op.drop_constraint("fk_character_fittings_source_fitting_id", "character_fittings", type_="foreignkey")
    op.drop_column("character_fittings", "updated_at")
    op.drop_column("character_fittings", "is_draft")
    op.drop_column("character_fittings", "source_fitting_id")
