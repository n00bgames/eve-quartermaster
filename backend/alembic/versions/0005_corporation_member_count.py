"""add corporation member count

Revision ID: 0005_corporation_member_count
Revises: 0004_user_invites
Create Date: 2026-06-28 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "0005_corporation_member_count"
down_revision = "0004_user_invites"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("eve_corporations", sa.Column("member_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("eve_corporations", "member_count")
