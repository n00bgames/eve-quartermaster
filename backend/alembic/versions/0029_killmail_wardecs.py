"""track wardec killmail source

Revision ID: 0029_killmail_wardecs
Revises: 0028_custom_market_hubs
Create Date: 2026-07-10 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0029_killmail_wardecs"
down_revision: Union[str, None] = "0028_custom_market_hubs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("system_industrial_kill_observations", sa.Column("war_id", sa.Integer(), nullable=True))
    op.create_index(
        "ix_system_industrial_kill_observations_war_id",
        "system_industrial_kill_observations",
        ["war_id"],
    )
    op.add_column("system_pvp_kill_observations", sa.Column("war_id", sa.Integer(), nullable=True))
    op.create_index(
        "ix_system_pvp_kill_observations_war_id",
        "system_pvp_kill_observations",
        ["war_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_system_pvp_kill_observations_war_id", table_name="system_pvp_kill_observations")
    op.drop_column("system_pvp_kill_observations", "war_id")
    op.drop_index("ix_system_industrial_kill_observations_war_id", table_name="system_industrial_kill_observations")
    op.drop_column("system_industrial_kill_observations", "war_id")