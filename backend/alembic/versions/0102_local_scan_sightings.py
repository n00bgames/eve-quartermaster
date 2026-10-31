"""Index named-system Local Scans as durable, privacy-scoped Intel observations."""
from hashlib import sha256
from alembic import op
import sqlalchemy as sa

revision = '0102_local_scan_sightings'
down_revision = '0101_scan_highlight_colors'
branch_labels = None
depends_on = None


def upgrade():
    table = op.create_table('intel_local_scan_sightings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('source_hash', sa.String(64), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE')),
        sa.Column('is_private', sa.Boolean(), nullable=False),
        sa.Column('character_eve_id', sa.BigInteger(), nullable=False),
        sa.Column('system_id', sa.Integer(), nullable=False),
        sa.Column('system_name', sa.String(255), nullable=False),
        sa.Column('region_id', sa.Integer()),
        sa.Column('region_name', sa.String(255)),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('source_hash', 'character_eve_id', name='uq_intel_local_scan_pilot'))
    op.create_index('ix_intel_local_scan_pilot_time', 'intel_local_scan_sightings', ['character_eve_id', 'observed_at'])
    # Read saved snapshots in bounded batches, without ESI or dossier creation.
    # Already-purged reports cannot be reconstructed. Keep the original UTC time.
    bind = op.get_bind()
    metadata = sa.MetaData()
    reports = sa.Table('local_scan_reports', metadata, autoload_with=bind)
    systems = sa.Table('eve_systems', metadata, autoload_with=bind)
    constellations = sa.Table('eve_constellations', metadata, autoload_with=bind)
    regions = sa.Table('eve_regions', metadata, autoload_with=bind)
    cursor = ''
    while True:
        batch = bind.execute(sa.select(reports).where(reports.c.report_kind == 'local', reports.c.token > cursor)
            .order_by(reports.c.token).limit(100)).mappings().all()
        if not batch:
            break
        for report in batch:
            snapshot = report['payload'] or {}
            system_id = (snapshot.get('system') or {}).get('id')
            if not isinstance(system_id, int) or isinstance(system_id, bool):
                continue
            location = bind.execute(sa.select(systems.c.system_id, systems.c.name,
                regions.c.region_id, regions.c.name.label('region_name'))
                .select_from(systems.outerjoin(constellations, constellations.c.constellation_id == systems.c.constellation_id)
                .outerjoin(regions, regions.c.region_id == constellations.c.region_id))
                .where(systems.c.system_id == system_id)).mappings().first()
            if location is None:
                continue
            ids = {p['character_id'] for p in snapshot.get('pilots', [])
                if isinstance(p.get('character_id'), int) and not isinstance(p['character_id'], bool) and p['character_id'] > 0}
            rows = [dict(source_hash=sha256(report['token'].encode()).hexdigest(),
                created_by_user_id=report['created_by_user_id'], is_private=report['is_private'], character_eve_id=eve_id,
                system_id=location['system_id'], system_name=location['name'], region_id=location['region_id'], region_name=location['region_name'],
                observed_at=report['created_at'], recorded_at=report['created_at']) for eve_id in sorted(ids)]
            if rows:
                bind.execute(table.insert(), rows)
        cursor = batch[-1]['token']


def downgrade():
    op.drop_index('ix_intel_local_scan_pilot_time', table_name='intel_local_scan_sightings')
    op.drop_table('intel_local_scan_sightings')
