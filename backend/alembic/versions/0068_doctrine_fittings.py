"""Allow doctrines to contain multiple fittings.

Revision ID: 0068_doctrine_fittings
Revises: 0067_srp_loss_analytics
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0068_doctrine_fittings"
down_revision: Union[str, None] = "0067_srp_loss_analytics"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "doctrine_fittings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("doctrine_id", sa.Integer(), sa.ForeignKey("doctrines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fitting_id", sa.Integer(), sa.ForeignKey("character_fittings.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fitting_snapshot", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("sort_order >= 0", name="ck_doctrine_fittings_sort_order"),
        sa.UniqueConstraint("doctrine_id", "fitting_id", name="uq_doctrine_fitting"),
    )
    for column in ("doctrine_id", "fitting_id", "is_primary"):
        op.create_index(f"ix_doctrine_fittings_{column}", "doctrine_fittings", [column])
    op.execute(
        """
        INSERT INTO doctrine_fittings (doctrine_id, fitting_id, is_primary, sort_order, fitting_snapshot)
        SELECT id, fitting_id, true, 0, fitting_snapshot
        FROM doctrines
        WHERE fitting_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_table("doctrine_fittings")
