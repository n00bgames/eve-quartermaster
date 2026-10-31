"""Record resolved local pilots without creating dossiers, combat evidence or ESI jobs."""
from hashlib import sha256
from sqlalchemy import insert, select
from app.models import EveSystem, EveConstellation, EveRegion
from app.models.intel import LocalScanSighting


def record(db, report):
    snapshot = report.payload
    system = snapshot.get('system') or {}
    if report.report_kind not in (None, 'local') or not system.get('id'):
        return 0
    location = db.execute(select(EveSystem, EveRegion)
        .outerjoin(EveConstellation, EveConstellation.constellation_id == EveSystem.constellation_id)
        .outerjoin(EveRegion, EveRegion.region_id == EveConstellation.region_id)
        .where(EveSystem.system_id == system['id'])).first()
    if location is None:
        return 0
    solar_system, region = location
    fingerprint = sha256(report.token.encode()).hexdigest()
    previous = set(db.scalars(select(LocalScanSighting.character_eve_id)
        .where(LocalScanSighting.source_hash == fingerprint)))
    ids = {p['character_id'] for p in snapshot.get('pilots', [])
        if isinstance(p.get('character_id'), int) and not isinstance(p['character_id'], bool) and p['character_id'] > 0}
    rows = [dict(source_hash=fingerprint, created_by_user_id=report.created_by_user_id,
        is_private=report.is_private, character_eve_id=eve_id,
        system_id=solar_system.system_id, system_name=solar_system.name,
        region_id=region.region_id if region else None, region_name=region.name if region else None,
        observed_at=report.created_at, recorded_at=report.created_at)
        for eve_id in sorted(ids - previous)]
    if rows:
        db.execute(insert(LocalScanSighting), rows)
    return len(rows)
