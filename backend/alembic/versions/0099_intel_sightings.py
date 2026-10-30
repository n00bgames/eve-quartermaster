"""Timestamped analyst ship sightings, separate from combat killmails."""
from alembic import op
import sqlalchemy as sa
revision='0099_intel_sightings'
down_revision='0098_account_sso'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('intel_sightings',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('subject_id',sa.Integer(),sa.ForeignKey('intel_subjects.id',ondelete='CASCADE'),nullable=False),
        sa.Column('observer_user_id',sa.Integer(),sa.ForeignKey('users.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('request_id',sa.String(36),nullable=False),
        sa.Column('recorded_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column('manual_time',sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column('system_id',sa.Integer(),sa.ForeignKey('eve_systems.system_id'),nullable=False),
        sa.Column('system_name',sa.String(255),nullable=False),
        sa.Column('region_id',sa.Integer()),sa.Column('region_name',sa.String(255)),
        sa.Column('ship_type_id',sa.Integer(),sa.ForeignKey('eve_types.type_id'),nullable=False),
        sa.Column('ship_type_name',sa.String(255),nullable=False),
        sa.Column('observed_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('subject_id','observer_user_id','request_id',name='uq_intel_sighting_request'))
    op.create_index('ix_intel_sightings_subject_time','intel_sightings',['subject_id','observed_at'])

def downgrade():op.drop_table('intel_sightings')
