"""Reversible, owner-only account and character HyperNet recording pauses."""
from alembic import op
import sqlalchemy as sa

revision = "0087_hypernet_pause"
down_revision = "0086_hypernet_private_analytics"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("hypernet_settings", sa.Column("paused", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        "hypernet_character_pauses",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("eve_characters.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("paused", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade():
    op.drop_table("hypernet_character_pauses")
    op.drop_column("hypernet_settings", "paused")
