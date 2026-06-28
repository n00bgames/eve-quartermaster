"""add character asset visibility flag

Revision ID: 0003_character_visibility
Revises: 0002_widen_esi_ids
Create Date: 2026-06-28
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_character_visibility"
down_revision = "0002_widen_esi_ids"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("eve_characters", sa.Column("public_assets_visible", sa.Boolean(), nullable=False, server_default=sa.text("false")))


def downgrade() -> None:
    op.drop_column("eve_characters", "public_assets_visible")
