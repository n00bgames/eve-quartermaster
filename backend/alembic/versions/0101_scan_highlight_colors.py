"""Persist per-account organization colors for Local Scan and linked D-Scan."""
from alembic import op
import sqlalchemy as sa

revision = '0101_scan_highlight_colors'
down_revision = '0100_unknown_ship_sightings'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('scan_color_settings',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('character_id', sa.Integer(), sa.ForeignKey('eve_characters.id', ondelete='SET NULL'), nullable=True),
        sa.Column('contact_colors', sa.JSON(), server_default='[]', nullable=False),
        sa.Column('synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revision', sa.Integer(), server_default='0', nullable=False))
    with op.batch_alter_table('scan_highlights') as batch:
        batch.add_column(sa.Column('color', sa.String(16), server_default='red', nullable=False))
        batch.create_check_constraint('ck_scan_highlight_color', "color IN ('red','orange','blue','light_blue','green','purple','gray')")


def downgrade():
    op.drop_table('scan_color_settings')
    with op.batch_alter_table('scan_highlights') as batch:
        batch.drop_constraint('ck_scan_highlight_color', type_='check')
        batch.drop_column('color')
