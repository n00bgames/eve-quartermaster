"""Main-character attribution and authenticated private reports."""
from alembic import op
import sqlalchemy as sa
revision = "0093_report_privacy"
down_revision = "0092_dscan_reports"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("users", sa.Column("main_character_id", sa.Integer(), nullable=True))
    for table in ("local_scan_reports", "battle_report_shares"):
        op.add_column(table, sa.Column("is_private", sa.Boolean(), nullable=False, server_default=sa.false()))
        op.add_column(table, sa.Column("anonymous", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("local_scan_reports", sa.Column("dynamic", sa.Boolean(), nullable=False, server_default=sa.false()))
    # Historical scan labels were account names. Never continue exposing those.
    op.execute("UPDATE local_scan_reports SET account_name = 'Anonymous'")
    op.add_column("battle_report_shares", sa.Column("creator_name", sa.String(120), nullable=False, server_default="Anonymous"))
    op.add_column("battle_report_shares", sa.Column("application_version", sa.String(32), nullable=False, server_default="2.0.0"))
    op.add_column("battle_report_shares", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_battle_report_shares_expires_at", "battle_report_shares", ["expires_at"])

def downgrade():
    # Older versions cannot enforce private access: discard private records first.
    op.execute("DELETE FROM local_scan_reports WHERE is_private = true OR report_kind = 'industry'")
    op.execute("DELETE FROM battle_report_shares WHERE is_private = true")
    op.drop_index("ix_battle_report_shares_expires_at", table_name="battle_report_shares")
    for table, names in (("users", ["main_character_id"]),
                         ("local_scan_reports", ["dynamic", "anonymous", "is_private"]),
                         ("battle_report_shares", ["expires_at", "application_version", "creator_name", "anonymous", "is_private"])):
        with op.batch_alter_table(table) as batch:
            for name in names: batch.drop_column(name)
