"""add smartbomb kill badges

Revision ID: 0018_smartbombs
Revises: 0017_pvp_intel
Create Date: 2026-07-02 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0018_smartbombs"
down_revision: Union[str, None] = "0017_pvp_intel"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table_name, index_name in {
        "system_industrial_kill_observations": "ix_siko_smartbombs",
        "system_pvp_kill_observations": "ix_spko_smartbombs",
    }.items():
        op.add_column(table_name, sa.Column("smartbomb_used", sa.Boolean(), nullable=False, server_default=sa.false()))
        op.create_index(index_name, table_name, ["smartbomb_used"])


def downgrade() -> None:
    for table_name, index_name in {
        "system_industrial_kill_observations": "ix_siko_smartbombs",
        "system_pvp_kill_observations": "ix_spko_smartbombs",
    }.items():
        op.drop_index(index_name, table_name=table_name)
        op.drop_column(table_name, "smartbomb_used")
