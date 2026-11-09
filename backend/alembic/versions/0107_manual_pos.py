"""Private manual POS records; no ESI collection or shared navigation data."""
from alembic import op
import sqlalchemy as sa

revision = "0107_manual_pos"
down_revision = "0106_scan_character_notes"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("manual_pos",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("tower_type", sa.String(160), nullable=False),
        sa.Column("corporation_name", sa.String(160), nullable=False),
        sa.Column("location", sa.String(240), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("fuel_blocks", sa.Integer()),
        sa.Column("fuel_per_hour", sa.Float(), nullable=False),
        sa.Column("stront_units", sa.Integer()),
        sa.Column("stront_per_hour", sa.Float(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reinforced_until", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_manual_pos_owner_user_id", "manual_pos", ["owner_user_id"])


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM manual_pos")):
        raise RuntimeError("Export and explicitly remove manual POS records before downgrading 0107")
    op.drop_index("ix_manual_pos_owner_user_id", table_name="manual_pos")
    op.drop_table("manual_pos")
