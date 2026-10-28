"""Separate directional-scan snapshots within the shared report lifecycle."""
from alembic import op
import sqlalchemy as sa

revision = "0092_dscan_reports"
down_revision = "0091_multiple_account_roles"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("local_scan_reports", sa.Column("report_kind", sa.String(16), nullable=False, server_default="local"))
    op.create_index("ix_local_scan_reports_report_kind", "local_scan_reports", ["report_kind"])


def downgrade():
    # D-scan snapshots have no interpretation in the older Local Scan application.
    op.execute("DELETE FROM local_scan_reports WHERE report_kind = 'dscan'")
    op.drop_index("ix_local_scan_reports_report_kind", table_name="local_scan_reports")
    with op.batch_alter_table("local_scan_reports") as batch:
        batch.drop_column("report_kind")
