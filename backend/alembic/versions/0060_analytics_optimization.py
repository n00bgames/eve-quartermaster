"""Optimize analytics snapshots and query indexes.

Revision ID: 0060_analytics_optimization
Revises: 0059_calendar_events
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0060_analytics_optimization"
down_revision: Union[str, None] = "0059_calendar_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "snapshot_runs",
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("ix_snapshot_runs_schema_version", "snapshot_runs", ["schema_version"])
    op.alter_column("snapshot_runs", "schema_version", server_default="2")

    op.create_index(
        "ix_snapshot_runs_scope_source_status_started",
        "snapshot_runs",
        ["scope_type", "scope_id", "source", "status", "started_at"],
    )
    op.create_index(
        "ix_character_skill_snapshots_character_category_recorded",
        "character_skill_snapshots",
        ["character_id", "category_name", "recorded_at", "id"],
    )
    op.create_index(
        "ix_corporation_snapshots_corporation_recorded",
        "corporation_snapshots",
        ["corporation_id", "recorded_at", "id"],
    )
    op.create_index(
        "ix_blueprint_snapshots_run_owner",
        "blueprint_snapshots",
        ["snapshot_run_id", "ownership_entity_id"],
    )
    op.create_index(
        "ix_snapshot_metrics_owner_recorded_metric",
        "snapshot_metrics",
        ["owner_type", "owner_id", "recorded_at", "metric_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_snapshot_metrics_owner_recorded_metric", table_name="snapshot_metrics")
    op.drop_index("ix_blueprint_snapshots_run_owner", table_name="blueprint_snapshots")
    op.drop_index("ix_corporation_snapshots_corporation_recorded", table_name="corporation_snapshots")
    op.drop_index("ix_character_skill_snapshots_character_category_recorded", table_name="character_skill_snapshots")
    op.drop_index("ix_snapshot_runs_scope_source_status_started", table_name="snapshot_runs")
    op.drop_index("ix_snapshot_runs_schema_version", table_name="snapshot_runs")
    op.drop_column("snapshot_runs", "schema_version")