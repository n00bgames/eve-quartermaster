"""Private, explicitly selected character journey tracking. Disabled by default."""
from alembic import op
import sqlalchemy as sa
revision='0103_journey_history'
down_revision='0102_local_scan_sightings'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('journey_trackers',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
        sa.Column('character_id',sa.Integer(),sa.ForeignKey('eve_characters.id',ondelete='CASCADE'),nullable=False),
        sa.Column('enabled',sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column('interval_seconds',sa.Integer(),nullable=False,server_default='15'),
        sa.Column('revision',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('state',sa.String(24),nullable=False,server_default='paused'),
        sa.Column('next_poll_at',sa.DateTime(timezone=True)),
        sa.Column('checked_at',sa.DateTime(timezone=True)),
        sa.Column('last_seen_at',sa.DateTime(timezone=True)),
        sa.Column('current_visit_id',sa.Integer()),
        sa.Column('lease_token',sa.String(36)),sa.Column('lease_until',sa.DateTime(timezone=True)),
        sa.Column('failures',sa.Integer(),nullable=False,server_default='0'),
        sa.UniqueConstraint('user_id','character_id',name='uq_journey_owner_character'))
    op.create_index('ix_journey_due','journey_trackers',['enabled','next_poll_at','lease_until'])
    op.create_table('journey_visits',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('tracker_id',sa.Integer(),sa.ForeignKey('journey_trackers.id',ondelete='CASCADE'),nullable=False),
        sa.Column('system_id',sa.Integer(),nullable=False),
        sa.Column('first_seen_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('last_seen_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('samples',sa.Integer(),nullable=False,server_default='1'),
        sa.Column('gap_before',sa.Boolean(),nullable=False,server_default=sa.true()))
    op.create_index('ix_journey_visit_time','journey_visits',['tracker_id','first_seen_at'])
    op.create_index('ix_journey_visit_system','journey_visits',['tracker_id','system_id'])

def downgrade():
    op.drop_table('journey_visits')
    op.drop_table('journey_trackers')
