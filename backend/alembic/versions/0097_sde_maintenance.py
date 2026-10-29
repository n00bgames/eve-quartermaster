"""Durable worker-backed SDE maintenance with one active operation."""
from alembic import op
import sqlalchemy as sa
revision = "0097_sde_maintenance"
down_revision = "0096_password_recovery"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("sde_maintenance_jobs",sa.Column("id",sa.String(36),primary_key=True),
        sa.Column("active_key",sa.String(16),unique=True),sa.Column("action",sa.String(16),nullable=False),
        sa.Column("status",sa.String(16),nullable=False),sa.Column("stage",sa.String(120),nullable=False),
        sa.Column("created_by_user_id",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("source_path",sa.Text()),sa.Column("options",sa.JSON(),nullable=False),
        sa.Column("progress",sa.JSON(),nullable=False),sa.Column("archive",sa.JSON(),nullable=False),sa.Column("error",sa.Text()),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("started_at",sa.DateTime(timezone=True)),sa.Column("completed_at",sa.DateTime(timezone=True)))

def downgrade():
    op.drop_table("sde_maintenance_jobs")
