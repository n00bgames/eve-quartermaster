"""add character NPC standings

Revision ID: 0052_character_standings
Revises: 0051_recruiting_public_polish
Create Date: 2026-07-27 10:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0052_character_standings"
down_revision: Union[str, None] = "0051_recruiting_public_polish"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "eve_characters",
        sa.Column("standings_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "character_standings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=24), nullable=False),
        sa.Column("source_eve_id", sa.Integer(), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("standing", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["eve_characters.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "character_id",
            "source_type",
            "source_eve_id",
            name="uq_character_standing_source",
        ),
    )
    op.create_index(
        op.f("ix_character_standings_character_id"),
        "character_standings",
        ["character_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_character_standings_source_eve_id"),
        "character_standings",
        ["source_eve_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_character_standings_source_name"),
        "character_standings",
        ["source_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_character_standings_source_type"),
        "character_standings",
        ["source_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_character_standings_source_type"), table_name="character_standings")
    op.drop_index(op.f("ix_character_standings_source_name"), table_name="character_standings")
    op.drop_index(op.f("ix_character_standings_source_eve_id"), table_name="character_standings")
    op.drop_index(op.f("ix_character_standings_character_id"), table_name="character_standings")
    op.drop_table("character_standings")
    op.drop_column("eve_characters", "standings_synced_at")
