"""Single-use recovery links and revocable account sessions."""
from alembic import op
import sqlalchemy as sa
revision = "0096_password_recovery"
down_revision = "0095_appearance"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("users", sa.Column("auth_version", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("password_reset_required", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table("password_resets",
        sa.Column("token_hash",sa.String(64),primary_key=True),
        sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),
        sa.Column("auth_version",sa.Integer(),nullable=False),sa.Column("email",sa.String(320),nullable=False),
        sa.Column("expires_at",sa.DateTime(timezone=True),nullable=False),sa.Column("consumed_at",sa.DateTime(timezone=True)))
    op.create_index("ix_password_resets_user_id","password_resets",["user_id"])
    op.create_index("ix_password_resets_expires_at","password_resets",["expires_at"])
    op.create_table("recovery_rate_limits",sa.Column("bucket",sa.String(64),primary_key=True),
        sa.Column("attempts",sa.Integer(),nullable=False),sa.Column("expires_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_recovery_rate_limits_expires_at","recovery_rate_limits",["expires_at"])

def downgrade():
    op.drop_table("recovery_rate_limits")
    op.drop_table("password_resets")
    op.drop_column("users","password_reset_required")
    op.drop_column("users","auth_version")
