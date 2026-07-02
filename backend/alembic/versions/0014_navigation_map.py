"""add navigation map graph

Revision ID: 0014_nav_map
Revises: 0013_analytics
Create Date: 2026-07-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0014_nav_map"
down_revision: Union[str, None] = "0013_analytics"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("eve_systems", sa.Column("security_class", sa.String(length=8), nullable=True))
    op.add_column("eve_systems", sa.Column("x", sa.Float(), nullable=True))
    op.add_column("eve_systems", sa.Column("y", sa.Float(), nullable=True))
    op.add_column("eve_systems", sa.Column("z", sa.Float(), nullable=True))
    op.create_index("ix_eve_systems_security_class", "eve_systems", ["security_class"])

    op.create_table(
        "eve_stargates",
        sa.Column("stargate_id", sa.Integer(), primary_key=True),
        sa.Column("system_id", sa.Integer(), sa.ForeignKey("eve_systems.system_id"), nullable=False),
        sa.Column("destination_system_id", sa.Integer(), sa.ForeignKey("eve_systems.system_id"), nullable=True),
        sa.Column("destination_stargate_id", sa.Integer(), nullable=True),
        sa.Column("type_id", sa.Integer(), nullable=True),
        sa.Column("x", sa.Float(), nullable=True),
        sa.Column("y", sa.Float(), nullable=True),
        sa.Column("z", sa.Float(), nullable=True),
    )
    op.create_index("ix_eve_stargates_system_id", "eve_stargates", ["system_id"])
    op.create_index("ix_eve_stargates_destination_system_id", "eve_stargates", ["destination_system_id"])
    op.create_index("ix_eve_stargates_destination_stargate_id", "eve_stargates", ["destination_stargate_id"])
    op.create_index("ix_eve_stargates_type_id", "eve_stargates", ["type_id"])


def downgrade() -> None:
    op.drop_index("ix_eve_stargates_type_id", table_name="eve_stargates")
    op.drop_index("ix_eve_stargates_destination_stargate_id", table_name="eve_stargates")
    op.drop_index("ix_eve_stargates_destination_system_id", table_name="eve_stargates")
    op.drop_index("ix_eve_stargates_system_id", table_name="eve_stargates")
    op.drop_table("eve_stargates")
    op.drop_index("ix_eve_systems_security_class", table_name="eve_systems")
    op.drop_column("eve_systems", "z")
    op.drop_column("eve_systems", "y")
    op.drop_column("eve_systems", "x")
    op.drop_column("eve_systems", "security_class")