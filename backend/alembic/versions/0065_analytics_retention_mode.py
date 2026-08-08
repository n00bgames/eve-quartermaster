"""Add stable analytics metric series keys.

Revision ID: 0065_analytics_retention_mode
Revises: 0064_wallet_corporation_opt_in
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0065_analytics_retention_mode"
down_revision: Union[str, None] = "0064_wallet_corporation_opt_in"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("snapshot_metrics", sa.Column("series_key", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_snapshot_metrics_series_key"), "snapshot_metrics", ["series_key"], unique=False)
    # Preserve prior behavior for upgrades that already contain analytics history.
    # Brand-new empty installations omit the row and use the application default:
    # Changes + Daily Checkpoints.
    op.execute(
        sa.text(
            """
            INSERT INTO app_settings (key, value)
            SELECT 'analytics_retention_mode', 'full'
            WHERE EXISTS (SELECT 1 FROM snapshot_runs)
              AND NOT EXISTS (
                  SELECT 1 FROM app_settings WHERE key = 'analytics_retention_mode'
              )
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM app_settings WHERE key = 'analytics_retention_mode'"))
    op.drop_index(op.f("ix_snapshot_metrics_series_key"), table_name="snapshot_metrics")
    op.drop_column("snapshot_metrics", "series_key")
