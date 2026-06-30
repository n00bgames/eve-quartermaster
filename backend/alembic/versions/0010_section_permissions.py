"""add section permissions

Revision ID: 0010_section_permissions
Revises: 0009_private_message_deletion
Create Date: 2026-06-29 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "0010_section_permissions"
down_revision = "0009_private_message_deletion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "role_section_permissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("section", sa.String(length=80), nullable=False),
        sa.Column("can_view", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.UniqueConstraint("role", "section"),
    )
    op.create_index("ix_role_section_permissions_role", "role_section_permissions", ["role"])
    op.create_index("ix_role_section_permissions_section", "role_section_permissions", ["section"])
    op.create_table(
        "user_section_permissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("section", sa.String(length=80), nullable=False),
        sa.Column("can_view", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.UniqueConstraint("user_id", "section"),
    )
    op.create_index("ix_user_section_permissions_user_id", "user_section_permissions", ["user_id"])
    op.create_index("ix_user_section_permissions_section", "user_section_permissions", ["section"])


def downgrade() -> None:
    op.drop_index("ix_user_section_permissions_section", table_name="user_section_permissions")
    op.drop_index("ix_user_section_permissions_user_id", table_name="user_section_permissions")
    op.drop_table("user_section_permissions")
    op.drop_index("ix_role_section_permissions_section", table_name="role_section_permissions")
    op.drop_index("ix_role_section_permissions_role", table_name="role_section_permissions")
    op.drop_table("role_section_permissions")
