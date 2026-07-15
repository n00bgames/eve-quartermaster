"""add manufacturing output disposition

Revision ID: 0037_mfg_output_sale
Revises: 0036_mfg_price_paid
Create Date: 2026-07-15 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0037_mfg_output_sale"
down_revision: Union[str, None] = "0036_mfg_price_paid"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE manufacturing_jobs ADD COLUMN IF NOT EXISTS output_disposition VARCHAR(40) NOT NULL DEFAULT 'pending'")
    op.execute("ALTER TABLE manufacturing_jobs ADD COLUMN IF NOT EXISTS output_sale_price NUMERIC(24, 2)")
    op.execute("ALTER TABLE manufacturing_jobs ADD COLUMN IF NOT EXISTS output_sale_notes TEXT")
    op.execute("CREATE INDEX IF NOT EXISTS ix_manufacturing_jobs_output_disposition ON manufacturing_jobs (output_disposition)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_manufacturing_jobs_output_disposition")
    op.execute("ALTER TABLE manufacturing_jobs DROP COLUMN IF EXISTS output_sale_notes")
    op.execute("ALTER TABLE manufacturing_jobs DROP COLUMN IF EXISTS output_sale_price")
    op.execute("ALTER TABLE manufacturing_jobs DROP COLUMN IF EXISTS output_disposition")
