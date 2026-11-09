"""Public reported-hour activity for Intel Reports."""
from alembic import op
import sqlalchemy as sa
revision = "0109_intel_activity"
down_revision = "0108_intel_subject_browser"
branch_labels = None
depends_on = None
def upgrade():
    op.create_table("intel_activity_samples",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("system_id",sa.Integer(),sa.ForeignKey("eve_systems.system_id",ondelete="CASCADE"),nullable=False),
        sa.Column("feed",sa.String(8),nullable=False),
        sa.Column("observed_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("fetched_at",sa.DateTime(timezone=True),nullable=False),
        *(sa.Column(key,sa.Integer(),nullable=True) for key in ("jumps","ship_kills","pod_kills","npc_kills")),
        sa.UniqueConstraint("system_id","feed","observed_at",name="uq_intel_activity_feed_hour"))
    op.create_index("ix_intel_activity_samples_system_id","intel_activity_samples",["system_id"])
    op.create_index("ix_intel_activity_samples_observed_at","intel_activity_samples",["observed_at"])
def downgrade():
    op.drop_table("intel_activity_samples")
