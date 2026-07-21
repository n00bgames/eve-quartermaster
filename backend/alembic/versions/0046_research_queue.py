"""add research queue planner

Revision ID: 0046_research_queue
Revises: 0045_notes_lists
Create Date: 2026-07-20 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0046_research_queue"
down_revision: Union[str, None] = "0045_notes_lists"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "research_queue_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("blueprint_id", sa.Integer(), sa.ForeignKey("blueprints.id", ondelete="SET NULL")),
        sa.Column("blueprint_type_id", sa.Integer(), sa.ForeignKey("eve_types.type_id", ondelete="SET NULL")),
        sa.Column("blueprint_name", sa.String(255), nullable=False),
        sa.Column("blueprint_kind", sa.String(3), nullable=False),
        sa.Column("owner_name", sa.String(255)),
        sa.Column("material_efficiency", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("time_efficiency", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("runs_remaining", sa.Integer()),
        sa.Column("source_location_name", sa.String(500)),
        sa.Column("source_hangar", sa.String(500)),
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("runs", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    for column in ["blueprint_id", "blueprint_type_id", "blueprint_name", "activity_id", "status", "sort_order"]:
        op.create_index(f"ix_research_queue_items_{column}", "research_queue_items", [column])


def downgrade() -> None:
    op.drop_table("research_queue_items")
