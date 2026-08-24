"""Add immutable public battle report snapshots.

Revision ID: 0075_battle_report_shares
Revises: 0074_jump_clone_bigint
"""

from alembic import op
import sqlalchemy as sa


revision = "0075_battle_report_shares"
down_revision = "0074_jump_clone_bigint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "battle_report_shares",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("share_token", sa.String(64), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("selected_character_id", sa.BigInteger(), nullable=False),
        sa.Column("selected_character_name", sa.String(255), nullable=False),
        sa.Column("report_payload", sa.JSON(), nullable=False),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_battle_report_shares_share_token", "battle_report_shares", ["share_token"], unique=True)
    op.create_index("ix_battle_report_shares_created_by_user_id", "battle_report_shares", ["created_by_user_id"])
    op.create_index("ix_battle_report_shares_selected_character_id", "battle_report_shares", ["selected_character_id"])
    op.create_index("ix_battle_report_shares_created_at", "battle_report_shares", ["created_at"])
    op.create_index("ix_battle_report_shares_revoked_at", "battle_report_shares", ["revoked_at"])


def downgrade() -> None:
    op.drop_index("ix_battle_report_shares_revoked_at", table_name="battle_report_shares")
    op.drop_index("ix_battle_report_shares_created_at", table_name="battle_report_shares")
    op.drop_index("ix_battle_report_shares_selected_character_id", table_name="battle_report_shares")
    op.drop_index("ix_battle_report_shares_created_by_user_id", table_name="battle_report_shares")
    op.drop_index("ix_battle_report_shares_share_token", table_name="battle_report_shares")
    op.drop_table("battle_report_shares")
