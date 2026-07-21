"""add notes and resupply lists

Revision ID: 0045_notes_lists
Revises: 0044_user_soft_delete
Create Date: 2026-07-18 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0045_notes_lists"
down_revision: Union[str, None] = "0044_user_soft_delete"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("note_type", sa.String(20), nullable=False, server_default="freeform"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text()),
        sa.Column("destination_system_id", sa.Integer(), sa.ForeignKey("eve_systems.system_id", ondelete="SET NULL")),
        sa.Column("destination_location_id", sa.Integer(), sa.ForeignKey("locations.id", ondelete="SET NULL")),
        sa.Column("source_market_hub_key", sa.String(120)),
        sa.Column("tags", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    for column in ["owner_user_id", "note_type", "title", "destination_system_id", "destination_location_id", "deleted_at"]:
        op.create_index(f"ix_notes_{column}", "notes", [column])
    op.create_table(
        "note_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("note_id", sa.Integer(), sa.ForeignKey("notes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type_id", sa.Integer(), sa.ForeignKey("eve_types.type_id", ondelete="SET NULL")),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("canonical_name", sa.String(255), nullable=False),
        sa.Column("requested_quantity", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(24), nullable=False, server_default="needed"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for column in ["note_id", "type_id", "canonical_name", "status"]:
        op.create_index(f"ix_note_items_{column}", "note_items", [column])


def downgrade() -> None:
    op.drop_table("note_items")
    op.drop_table("notes")