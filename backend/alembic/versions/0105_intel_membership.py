"""Daily public corporation/alliance membership observations and monitoring leases."""
from alembic import op
import sqlalchemy as sa

revision = "0105_intel_membership"
down_revision = "0104_journey_ship_history"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("intel_membership_monitors",
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("intel_subjects.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("requested_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("next_poll_at", sa.DateTime(timezone=True)),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(24), nullable=False, server_default="idle"),
        sa.Column("notice", sa.String(255)),
        sa.Column("failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lease_token", sa.String(36)), sa.Column("lease_until", sa.DateTime(timezone=True)))
    op.create_index("ix_intel_membership_monitors_next_poll_at", "intel_membership_monitors", ["next_poll_at"])
    op.create_table("intel_membership_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("intel_subjects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("utc_day", sa.String(10), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("member_count", sa.Integer()), sa.Column("corporation_count", sa.Integer()),
        sa.Column("resolved_corporations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("known_member_count", sa.Integer()), sa.Column("corporations", sa.JSON(), nullable=False),
        sa.UniqueConstraint("subject_id", "utc_day", name="uq_intel_membership_day"),
        sa.CheckConstraint("member_count IS NULL OR member_count >= 0", name="ck_intel_membership_count"))
    op.create_index("ix_intel_membership_subject_time", "intel_membership_snapshots", ["subject_id", "observed_at"])


def downgrade():
    op.drop_table("intel_membership_snapshots")
    op.drop_table("intel_membership_monitors")
