"""add ESI research project history

Revision ID: 0040_research_projects
Revises: 0039_contract_analytics
Create Date: 2026-07-17 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0040_research_projects"
down_revision: Union[str, None] = "0039_contract_analytics"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "research_projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("eve_characters.id"), nullable=False),
        sa.Column("installer_character_id", sa.BigInteger()),
        sa.Column("completed_character_id", sa.BigInteger()),
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("blueprint_id", sa.BigInteger()),
        sa.Column("blueprint_type_id", sa.Integer(), sa.ForeignKey("eve_types.type_id")),
        sa.Column("product_type_id", sa.Integer(), sa.ForeignKey("eve_types.type_id")),
        sa.Column("facility_id", sa.BigInteger()),
        sa.Column("station_id", sa.BigInteger()),
        sa.Column("facility_name", sa.String(length=500)),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("runs", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("licensed_runs", sa.Integer()),
        sa.Column("successful_runs", sa.Integer()),
        sa.Column("probability", sa.Numeric(10, 6)),
        sa.Column("cost", sa.Numeric(20, 2)),
        sa.Column("duration", sa.Integer()),
        sa.Column("start_date", sa.DateTime(timezone=True)),
        sa.Column("end_date", sa.DateTime(timezone=True)),
        sa.Column("pause_date", sa.DateTime(timezone=True)),
        sa.Column("completed_date", sa.DateTime(timezone=True)),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("job_id"),
    )
    for column in ("character_id", "installer_character_id", "activity_id", "blueprint_type_id", "product_type_id", "status", "start_date", "end_date"):
        op.create_index(f"ix_research_projects_{column}", "research_projects", [column])


def downgrade() -> None:
    op.drop_table("research_projects")
