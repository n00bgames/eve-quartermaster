"""Store jump clone location IDs as 64-bit EVE identifiers.

Revision ID: 0074_jump_clone_bigint
Revises: 0073_standing_analytics
"""

from alembic import op
import sqlalchemy as sa


revision = "0074_jump_clone_bigint"
down_revision = "0073_standing_analytics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "character_jump_clones",
        "location_id",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "character_jump_clones",
        "location_id",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
    )
