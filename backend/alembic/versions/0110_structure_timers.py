"""Opt-in structure calendar timers and reminder deliveries."""
from alembic import op
import sqlalchemy as sa
revision = '0110_structure_timers'
down_revision = '0109_intel_activity'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('structure_timer_configs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('owner_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('source', sa.String(16), nullable=False),
        sa.Column('source_id', sa.String(36), nullable=False),
        sa.Column('token_key', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('roles', sa.JSON(), nullable=False),
        sa.Column('minutes', sa.JSON(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(160), nullable=False),
        sa.Column('checked_at', sa.DateTime(timezone=True)),
        sa.UniqueConstraint('owner_user_id', 'source', 'source_id', 'token_key'))
    op.create_index('ix_structure_timer_configs_owner_user_id', 'structure_timer_configs', ['owner_user_id'])
    op.create_table('structure_timers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('config_id', sa.Integer(), sa.ForeignKey('structure_timer_configs.id'), nullable=False),
        sa.Column('kind', sa.String(20), nullable=False),
        sa.Column('deadline', sa.DateTime(timezone=True)),
        sa.Column('generation', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), sa.ForeignKey('events.id'), nullable=False, unique=True),
        sa.UniqueConstraint('config_id', 'kind'))
    op.create_index('ix_structure_timers_config_id', 'structure_timers', ['config_id'])
    op.create_table('structure_timer_deliveries',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('timer_id', sa.Integer(), sa.ForeignKey('structure_timers.id'), nullable=False),
        sa.Column('generation', sa.Integer(), nullable=False),
        sa.Column('minutes', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('notice_id', sa.Integer(), sa.ForeignKey('audit_events.id'), nullable=False, unique=True),
        sa.Column('dismissed', sa.Boolean(), nullable=False),
        sa.UniqueConstraint('timer_id', 'generation', 'minutes', 'user_id'))
    op.create_index('ix_structure_timer_deliveries_timer_id', 'structure_timer_deliveries', ['timer_id'])
    op.create_index('ix_structure_timer_deliveries_user_id', 'structure_timer_deliveries', ['user_id'])


def downgrade():
    # Calendar rows are generated, never user-authored events.
    ids = list(op.get_bind().execute(sa.text('SELECT event_id FROM structure_timers')).scalars())
    op.drop_table('structure_timer_deliveries')
    op.drop_table('structure_timers')
    op.drop_table('structure_timer_configs')
    for event_id in ids:
        op.get_bind().execute(sa.text('DELETE FROM events WHERE id = :id'), {'id': event_id})
