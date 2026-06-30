"""add character sync opt out

Revision ID: 0007_character_sync_opt_out
Revises: 0006_character_skills
Create Date: 2026-06-29 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "0007_character_sync_opt_out"
down_revision = "0006_character_skills"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("eve_characters", sa.Column("sync_opt_out", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.alter_column("eve_characters", "sync_opt_out", server_default=None)


def downgrade() -> None:
    op.drop_column("eve_characters", "sync_opt_out")
