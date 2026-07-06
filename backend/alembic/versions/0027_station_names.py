"""preserve npc station display fields

Revision ID: 0027_station_names
Revises: 0026_system_jumps
Create Date: 2026-07-05 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0027_station_names"
down_revision: Union[str, None] = "0026_system_jumps"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("eve_stations", sa.Column("owner_name", sa.String(length=255), nullable=True))
    op.add_column("eve_stations", sa.Column("celestial_index", sa.Integer(), nullable=True))
    op.add_column("eve_stations", sa.Column("orbit_index", sa.Integer(), nullable=True))
    op.create_index("ix_est_owner_name", "eve_stations", ["owner_name"])
    op.create_index("ix_est_celestial_index", "eve_stations", ["celestial_index"])
    op.create_index("ix_est_orbit_index", "eve_stations", ["orbit_index"])


def downgrade() -> None:
    op.drop_index("ix_est_orbit_index", table_name="eve_stations")
    op.drop_index("ix_est_celestial_index", table_name="eve_stations")
    op.drop_index("ix_est_owner_name", table_name="eve_stations")
    op.drop_column("eve_stations", "orbit_index")
    op.drop_column("eve_stations", "celestial_index")
    op.drop_column("eve_stations", "owner_name")