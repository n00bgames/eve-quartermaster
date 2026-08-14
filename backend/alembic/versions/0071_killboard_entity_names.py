"""Cache public EVE entity names used by killboard analytics.

Revision ID: 0071_killboard_entity_names
Revises: 0070_killboard
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0071_killboard_entity_names"
down_revision: Union[str, None] = "0070_killboard"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "killboard_entity_names",
        sa.Column("eve_id", sa.BigInteger(), primary_key=True),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255)),
        sa.Column("resolution_status", sa.String(length=24), nullable=False, server_default="resolved"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
    )
    for column in ("category", "name", "resolution_status", "last_attempt_at"):
        op.create_index(f"ix_killboard_entity_names_{column}", "killboard_entity_names", [column])


def downgrade() -> None:
    op.drop_table("killboard_entity_names")
