"""Private PLEX ledger and shared public market cache."""
from alembic import op
import sqlalchemy as sa

revision = "0083_plex_tracker"
down_revision = "0082_hypernet_node_positions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "plex_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(24, 2), nullable=True),
        sa.Column("fees", sa.Numeric(24, 2), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_plex_quantity"),
        sa.CheckConstraint("unit_price IS NULL OR unit_price >= 0", name="ck_plex_price"),
        sa.CheckConstraint("fees >= 0", name="ck_plex_fees"),
        sa.CheckConstraint("kind IN ('buy', 'opening', 'sell', 'consume')", name="ck_plex_kind"),
    )
    op.create_index("ix_plex_transactions_owner_user_id", "plex_transactions", ["owner_user_id"])
    op.create_index("ix_plex_transactions_occurred_at", "plex_transactions", ["occurred_at"])
    op.create_table("plex_market_cache", sa.Column("key", sa.String(20), primary_key=True),
                    sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("payload", sa.JSON(), nullable=False))


def downgrade():
    op.drop_table("plex_market_cache")
    op.drop_table("plex_transactions")
