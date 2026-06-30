"""add per-user private message deletion

Revision ID: 0009_private_message_deletion
Revises: 0008_notifications_messages
Create Date: 2026-06-29 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "0009_private_message_deletion"
down_revision = "0008_notifications_messages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("private_messages", sa.Column("sender_deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("private_messages", sa.Column("recipient_deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("private_messages", "recipient_deleted_at")
    op.drop_column("private_messages", "sender_deleted_at")