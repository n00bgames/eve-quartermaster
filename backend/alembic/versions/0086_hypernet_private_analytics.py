"""Private, explicitly enabled HyperNet analytics per user and character."""
from alembic import op
import sqlalchemy as sa

revision = "0086_hypernet_private_analytics"
down_revision = "0085_hypernet_grid_reference"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hypernet_analytics_preferences",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("eve_characters.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade():
    op.drop_table("hypernet_analytics_preferences")
