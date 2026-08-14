from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EveCharacter, EveCorporation, SnapshotRun, User
from app.services.analytics import RETENTION_MODE_CHANGES, add_metric, analytics_retention_mode, snapshot_run_has_observations
from app.services.killboard_analytics import build_killboard_analytics


METRIC_FIELDS = {
    "killboard.kills": "kills",
    "killboard.losses": "losses",
    "killboard.isk_destroyed": "isk_destroyed",
    "killboard.isk_lost": "isk_lost",
    "killboard.solo_kills": "solo_kills",
    "killboard.final_blows": "final_blows",
}


def snapshot_killboard_targets(db: Session, user: User, targets: list[dict[str, Any]]) -> SnapshotRun:
    """Record one coalesced gauge per normalized owner using EQM's existing snapshot registry."""
    run = SnapshotRun(
        scope_type="killboard",
        scope_id=user.id,
        source="killboard_sync",
        status="running",
        message="Killboard totals after canonical ESI synchronization.",
    )
    db.add(run)
    db.flush()
    retention_mode = analytics_retention_mode(db)
    seen: set[tuple[str, int]] = set()
    try:
        for target in targets:
            owner_type = str(target.get("owner_type") or "")
            eve_id = int(target.get("owner_id") or 0)
            key = (owner_type, eve_id)
            if eve_id <= 0 or key in seen or owner_type not in {"character", "corporation"}:
                continue
            seen.add(key)
            if owner_type == "character":
                owner = db.scalar(select(EveCharacter).where(EveCharacter.character_id == eve_id))
                internal_id = owner.id if owner else None
            else:
                owner = db.scalar(select(EveCorporation).where(EveCorporation.corporation_id == eve_id))
                internal_id = owner.id if owner else None
            if owner is None or internal_id is None:
                continue
            analytics = build_killboard_analytics(db, user, scope_type=owner_type, scope_id=eve_id, days=3650)
            summary = analytics["summary"]
            for metric_key, field in METRIC_FIELDS.items():
                add_metric(
                    db,
                    run,
                    owner_type=owner_type,
                    owner_id=internal_id,
                    owner_name=owner.name,
                    metric_key=metric_key,
                    metric_value=summary[field],
                    retention_mode=retention_mode,
                )
        run.status = "unchanged" if retention_mode == RETENTION_MODE_CHANGES and not snapshot_run_has_observations(db, run.id) else "success"
        run.completed_at = datetime.now(timezone.utc)
        return run
    except Exception as exc:
        run.status = "failed"
        run.message = f"Killboard snapshot failed without affecting canonical killmails: {exc}"
        run.completed_at = datetime.now(timezone.utc)
        raise
