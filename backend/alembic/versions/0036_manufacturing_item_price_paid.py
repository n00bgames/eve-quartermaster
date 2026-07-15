"""add manufacturing item price paid

Revision ID: 0036_mfg_price_paid
Revises: 0035_manufacturing_job_status
Create Date: 2026-07-14 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0036_mfg_price_paid"
down_revision: Union[str, None] = "0035_manufacturing_job_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE manufacturing_job_items ADD COLUMN IF NOT EXISTS price_paid NUMERIC(24, 2)")


def downgrade() -> None:
    op.execute("ALTER TABLE manufacturing_job_items DROP COLUMN IF EXISTS price_paid")

