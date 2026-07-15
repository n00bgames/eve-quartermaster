"""add manufacturing activity fields

Revision ID: 0038_mfg_activity_fields
Revises: 0037_mfg_output_sale
Create Date: 2026-07-15 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0038_mfg_activity_fields"
down_revision: Union[str, None] = "0037_mfg_output_sale"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE manufacturing_jobs ADD COLUMN IF NOT EXISTS activity_flags VARCHAR(160) NOT NULL DEFAULT 'manufacturing'")
    op.execute("ALTER TABLE manufacturing_jobs ADD COLUMN IF NOT EXISTS research_runs INTEGER")
    op.execute("ALTER TABLE manufacturing_jobs ADD COLUMN IF NOT EXISTS me_start INTEGER")
    op.execute("ALTER TABLE manufacturing_jobs ADD COLUMN IF NOT EXISTS me_target INTEGER")
    op.execute("ALTER TABLE manufacturing_jobs ADD COLUMN IF NOT EXISTS te_start INTEGER")
    op.execute("ALTER TABLE manufacturing_jobs ADD COLUMN IF NOT EXISTS te_target INTEGER")
    op.execute("ALTER TABLE manufacturing_jobs ADD COLUMN IF NOT EXISTS copy_runs INTEGER")
    op.execute("ALTER TABLE manufacturing_jobs ADD COLUMN IF NOT EXISTS invention_runs INTEGER")
    op.execute("ALTER TABLE manufacturing_jobs ADD COLUMN IF NOT EXISTS invention_successes INTEGER")
    op.execute("CREATE INDEX IF NOT EXISTS ix_manufacturing_jobs_activity_flags ON manufacturing_jobs (activity_flags)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_manufacturing_jobs_activity_flags")
    op.execute("ALTER TABLE manufacturing_jobs DROP COLUMN IF EXISTS invention_successes")
    op.execute("ALTER TABLE manufacturing_jobs DROP COLUMN IF EXISTS invention_runs")
    op.execute("ALTER TABLE manufacturing_jobs DROP COLUMN IF EXISTS copy_runs")
    op.execute("ALTER TABLE manufacturing_jobs DROP COLUMN IF EXISTS te_target")
    op.execute("ALTER TABLE manufacturing_jobs DROP COLUMN IF EXISTS te_start")
    op.execute("ALTER TABLE manufacturing_jobs DROP COLUMN IF EXISTS me_target")
    op.execute("ALTER TABLE manufacturing_jobs DROP COLUMN IF EXISTS me_start")
    op.execute("ALTER TABLE manufacturing_jobs DROP COLUMN IF EXISTS research_runs")
    op.execute("ALTER TABLE manufacturing_jobs DROP COLUMN IF EXISTS activity_flags")
