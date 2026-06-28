"""add user invites

Revision ID: 0004_user_invites
Revises: 0003_character_visibility
Create Date: 2026-06-28 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "0004_user_invites"
down_revision = "0003_character_visibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_invites",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("accepted_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["accepted_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_invites_email"), "user_invites", ["email"], unique=False)
    op.create_index(op.f("ix_user_invites_token_hash"), "user_invites", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_invites_token_hash"), table_name="user_invites")
    op.drop_index(op.f("ix_user_invites_email"), table_name="user_invites")
    op.drop_table("user_invites")
