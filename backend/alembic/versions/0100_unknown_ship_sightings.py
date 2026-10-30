"""Allow location sightings without an identified hull."""
from alembic import op
import sqlalchemy as sa
revision='0100_unknown_ship_sightings'
down_revision='0099_intel_sightings'
branch_labels=None
depends_on=None

def upgrade():
    with op.batch_alter_table('intel_sightings') as batch:
        batch.alter_column('ship_type_id',existing_type=sa.Integer(),nullable=True)

def downgrade():
    # Unknown sightings cannot be represented by 0099; never silently discard them.
    connection=op.get_bind()
    if connection.execute(sa.text('SELECT COUNT(*) FROM intel_sightings WHERE ship_type_id IS NULL')).scalar():
        raise RuntimeError('Cannot downgrade while unknown-ship sightings exist; retain/export or identify those sightings first')
    with op.batch_alter_table('intel_sightings') as batch:
        batch.alter_column('ship_type_id',existing_type=sa.Integer(),nullable=False)
