"""Private-by-default, revocable Journey aggregate snapshots."""
from alembic import op
import sqlalchemy as sa

revision = '0112_journey_analytics_views'
down_revision = '0111_local_universe'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('journey_analytics_views',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('owner_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token', sa.String(64), nullable=False, unique=True),
        sa.Column('title', sa.String(120), nullable=False),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('spec', sa.JSON(), nullable=False), sa.Column('cohort', sa.JSON(), nullable=False),
        sa.Column('report', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_journey_analytics_views_owner_user_id', 'journey_analytics_views', ['owner_user_id'])


def downgrade():
    op.drop_index('ix_journey_analytics_views_owner_user_id', table_name='journey_analytics_views')
    op.drop_table('journey_analytics_views')
