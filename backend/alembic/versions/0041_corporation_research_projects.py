"""add corporation-owned research projects

Revision ID: 0041_corporation_research
Revises: 0040_research_projects
Create Date: 2026-07-17 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0041_corporation_research"
down_revision: Union[str, None] = "0040_research_projects"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("research_projects", "character_id", existing_type=sa.Integer(), nullable=True)
    op.add_column("research_projects", sa.Column("corporation_id", sa.Integer(), nullable=True))
    op.add_column("research_projects", sa.Column("source_type", sa.String(length=20), nullable=False, server_default="character"))
    op.add_column("research_projects", sa.Column("installer_name", sa.String(length=255), nullable=True))
    op.create_foreign_key(
        "fk_research_projects_corporation_id_eve_corporations",
        "research_projects",
        "eve_corporations",
        ["corporation_id"],
        ["id"],
    )
    op.create_index("ix_research_projects_corporation_id", "research_projects", ["corporation_id"])
    op.create_index("ix_research_projects_source_type", "research_projects", ["source_type"])
    op.alter_column("research_projects", "source_type", server_default=None)


def downgrade() -> None:
    op.execute("DELETE FROM research_projects WHERE character_id IS NULL")
    op.drop_index("ix_research_projects_source_type", table_name="research_projects")
    op.drop_index("ix_research_projects_corporation_id", table_name="research_projects")
    op.drop_constraint("fk_research_projects_corporation_id_eve_corporations", "research_projects", type_="foreignkey")
    op.drop_column("research_projects", "installer_name")
    op.drop_column("research_projects", "source_type")
    op.drop_column("research_projects", "corporation_id")
    op.alter_column("research_projects", "character_id", existing_type=sa.Integer(), nullable=False)
