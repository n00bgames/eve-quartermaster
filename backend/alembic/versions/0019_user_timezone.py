"""Add user timezone preference.

Revision ID: 0019_user_tz
Revises: 0018_smartbombs
Create Date: 2026-07-01 21:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0019_user_tz"
down_revision = "0018_smartbombs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"))
    op.alter_column("users", "timezone", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "timezone")