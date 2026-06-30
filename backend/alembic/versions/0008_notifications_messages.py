"""add notifications audit and messages

Revision ID: 0008_notifications_messages
Revises: 0007_character_sync_opt_out
Create Date: 2026-06-29 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "0008_notifications_messages"
down_revision = "0007_character_sync_opt_out"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=120), primary_key=True),
        sa.Column("value", sa.String(length=255), nullable=False),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_kind", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("recipient_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("eve_characters.id"), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_events_event_kind", "audit_events", ["event_kind"])
    op.create_index("ix_audit_events_actor_user_id", "audit_events", ["actor_user_id"])
    op.create_index("ix_audit_events_recipient_user_id", "audit_events", ["recipient_user_id"])
    op.create_index("ix_audit_events_character_id", "audit_events", ["character_id"])
    op.create_table(
        "private_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sender_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("recipient_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_private_messages_sender_user_id", "private_messages", ["sender_user_id"])
    op.create_index("ix_private_messages_recipient_user_id", "private_messages", ["recipient_user_id"])


def downgrade() -> None:
    op.drop_index("ix_private_messages_recipient_user_id", table_name="private_messages")
    op.drop_index("ix_private_messages_sender_user_id", table_name="private_messages")
    op.drop_table("private_messages")
    op.drop_index("ix_audit_events_character_id", table_name="audit_events")
    op.drop_index("ix_audit_events_recipient_user_id", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_user_id", table_name="audit_events")
    op.drop_index("ix_audit_events_event_kind", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_table("app_settings")