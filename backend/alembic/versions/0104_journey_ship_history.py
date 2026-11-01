"""Explicit opt-in private journey hull history; never infer historical ships."""
from alembic import op
import sqlalchemy as sa
revision='0104_journey_ship_history'
down_revision='0103_journey_history'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('journey_trackers',sa.Column('track_ship',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.add_column('journey_trackers',sa.Column('current_ship_segment_id',sa.Integer()))
    op.create_table('journey_ship_segments',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('visit_id',sa.Integer(),sa.ForeignKey('journey_visits.id',ondelete='CASCADE'),nullable=False),
        sa.Column('ship_type_id',sa.Integer(),nullable=False),
        sa.Column('first_seen_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('last_seen_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('samples',sa.Integer(),nullable=False,server_default='1'),
        sa.Column('gap_before',sa.Boolean(),nullable=False,server_default=sa.true()))
    op.create_index('ix_journey_ship_visit_time','journey_ship_segments',['visit_id','first_seen_at'])

def downgrade():
    op.drop_table('journey_ship_segments')
    op.drop_column('journey_trackers','current_ship_segment_id')
    op.drop_column('journey_trackers','track_ship')
