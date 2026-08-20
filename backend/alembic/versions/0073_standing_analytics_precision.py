"""Retain four-decimal standing values in analytics snapshots.

Revision ID: 0073_standing_analytics
Revises: 0072_bounty_analytics
"""

from alembic import op
import sqlalchemy as sa


revision = "0073_standing_analytics"
down_revision = "0072_bounty_analytics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "snapshot_metrics",
        "metric_value",
        existing_type=sa.Numeric(precision=24, scale=2),
        type_=sa.Numeric(precision=24, scale=4),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "snapshot_metrics",
        "metric_value",
        existing_type=sa.Numeric(precision=24, scale=4),
        type_=sa.Numeric(precision=24, scale=2),
        existing_nullable=False,
    )
