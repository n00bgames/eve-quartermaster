"""widen esi asset and location ids

Revision ID: 0002_widen_esi_ids
Revises: 0001_initial_schema
Create Date: 2026-06-27
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_widen_esi_ids"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("assets", "eve_item_id", existing_type=sa.Integer(), type_=sa.BigInteger(), existing_nullable=True)
    op.alter_column("locations", "eve_location_id", existing_type=sa.Integer(), type_=sa.BigInteger(), existing_nullable=True)


def downgrade() -> None:
    op.alter_column("locations", "eve_location_id", existing_type=sa.BigInteger(), type_=sa.Integer(), existing_nullable=True)
    op.alter_column("assets", "eve_item_id", existing_type=sa.BigInteger(), type_=sa.Integer(), existing_nullable=True)
