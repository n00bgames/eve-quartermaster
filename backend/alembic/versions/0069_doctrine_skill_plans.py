"""Allow doctrines to link multiple fitting-specific skill plans.

Revision ID: 0069_doctrine_skill_plans
Revises: 0068_doctrine_fittings
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0069_doctrine_skill_plans"
down_revision: Union[str, None] = "0068_doctrine_fittings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "doctrine_skill_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("doctrine_id", sa.Integer(), sa.ForeignKey("doctrines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("skill_plan_id", sa.Integer(), sa.ForeignKey("skill_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fitting_id", sa.Integer(), sa.ForeignKey("character_fittings.id", ondelete="SET NULL")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("sort_order >= 0", name="ck_doctrine_skill_plans_sort_order"),
        sa.UniqueConstraint("doctrine_id", "skill_plan_id", name="uq_doctrine_skill_plan"),
    )
    for column in ("doctrine_id", "skill_plan_id", "fitting_id"):
        op.create_index(f"ix_doctrine_skill_plans_{column}", "doctrine_skill_plans", [column])
    op.execute(
        """
        INSERT INTO doctrine_skill_plans (doctrine_id, skill_plan_id, fitting_id, sort_order)
        SELECT id, linked_skill_plan_id, fitting_id, 0
        FROM doctrines
        WHERE linked_skill_plan_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_table("doctrine_skill_plans")
