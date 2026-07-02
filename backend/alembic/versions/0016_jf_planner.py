"""add npc stations for jump planning

Revision ID: 0016_jf_planner
Revises: 0015_industrial_kill_cache
Create Date: 2026-07-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0016_jf_planner"
down_revision: Union[str, None] = "0015_industrial_kill_cache"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "eve_stations",
        sa.Column("station_id", sa.Integer(), primary_key=True),
        sa.Column("system_id", sa.Integer(), sa.ForeignKey("eve_systems.system_id"), nullable=False),
        sa.Column("type_id", sa.Integer(), sa.ForeignKey("eve_types.type_id"), nullable=True),
        sa.Column("operation_id", sa.Integer(), nullable=True),
        sa.Column("operation_name", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("orbit_id", sa.Integer(), nullable=True),
        sa.Column("x", sa.Float(), nullable=True),
        sa.Column("y", sa.Float(), nullable=True),
        sa.Column("z", sa.Float(), nullable=True),
    )
    for name, column in {
        "ix_est_system": "system_id",
        "ix_est_type": "type_id",
        "ix_est_operation": "operation_id",
        "ix_est_operation_name": "operation_name",
        "ix_est_name": "name",
        "ix_est_owner": "owner_id",
        "ix_est_orbit": "orbit_id",
    }.items():
        op.create_index(name, "eve_stations", [column])


def downgrade() -> None:
    op.drop_table("eve_stations")
