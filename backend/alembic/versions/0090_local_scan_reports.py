"""Public local-scan reports with creator/corporation scope and retention."""
from alembic import op
import sqlalchemy as sa

revision = "0090_local_scan_reports"
down_revision = "0089_intel_reports"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("local_scan_reports",
        sa.Column("token", sa.String(48), primary_key=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("corporation_id", sa.Integer()),
        sa.Column("account_name", sa.String(120), nullable=False),
        sa.Column("application_version", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("retention", sa.String(16), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False))
    for name in ("created_by_user_id", "corporation_id", "created_at", "expires_at"):
        op.create_index(f"ix_local_scan_reports_{name}", "local_scan_reports", [name])
    op.create_index("ix_local_scan_owner_created", "local_scan_reports", ["created_by_user_id", "created_at"])
    op.create_table("scan_highlights",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("eve_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.UniqueConstraint("user_id", "kind", "eve_id", name="uq_scan_highlight_owner_entity"),
        sa.CheckConstraint("kind IN ('corporation','alliance')", name="ck_scan_highlight_kind"))
    op.create_index("ix_scan_highlights_user_id", "scan_highlights", ["user_id"])


def downgrade():
    op.drop_table("scan_highlights")
    op.drop_table("local_scan_reports")
