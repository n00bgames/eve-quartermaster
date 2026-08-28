"""Complete HyperNet bid tracking fields and constraints.

Revision ID: 0078_hypernet_bid_tracking
Revises: 0077_system_activity_kills
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0078_hypernet_bid_tracking"
down_revision: Union[str, None] = "0077_system_activity_kills"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("hypernet_participation", sa.Column("location_name_snapshot", sa.String(length=500)))
    op.add_column("hypernet_participation", sa.Column("total_nodes", sa.Integer(), nullable=True))
    op.execute("UPDATE hypernet_participation SET total_nodes = nodes_purchased WHERE total_nodes IS NULL")
    op.alter_column("hypernet_participation", "total_nodes", nullable=False)
    op.create_check_constraint("ck_hypernet_participation_total_nodes", "hypernet_participation", "total_nodes > 0")
    op.create_check_constraint(
        "ck_hypernet_participation_nodes",
        "hypernet_participation",
        "nodes_purchased > 0 AND nodes_purchased <= total_nodes",
    )
    op.create_check_constraint(
        "ck_hypernet_participation_spend",
        "hypernet_participation",
        "node_price >= 0 AND total_spent >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_hypernet_participation_spend", "hypernet_participation", type_="check")
    op.drop_constraint("ck_hypernet_participation_nodes", "hypernet_participation", type_="check")
    op.drop_constraint("ck_hypernet_participation_total_nodes", "hypernet_participation", type_="check")
    op.drop_column("hypernet_participation", "total_nodes")
    op.drop_column("hypernet_participation", "location_name_snapshot")
