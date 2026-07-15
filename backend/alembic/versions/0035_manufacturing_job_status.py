"""add manufacturing job status

Revision ID: 0035_manufacturing_job_status
Revises: 0034_manufacturing_ledger
Create Date: 2026-07-14 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0035_manufacturing_job_status"
down_revision: Union[str, None] = "0034_manufacturing_ledger"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE manufacturing_jobs ADD COLUMN IF NOT EXISTS status VARCHAR(40) NOT NULL DEFAULT 'draft'")
    op.execute("CREATE INDEX IF NOT EXISTS ix_manufacturing_jobs_status ON manufacturing_jobs (status)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_manufacturing_jobs_status")
    op.execute("ALTER TABLE manufacturing_jobs DROP COLUMN IF EXISTS status")
