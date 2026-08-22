from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass(frozen=True)
class SyncDataset:
    key: str
    label: str
    required_scopes: tuple[str, ...]
    stale_after_hours: int = 26


CHARACTER_SYNC_DATASETS: tuple[SyncDataset, ...] = (
    SyncDataset("character_assets", "Assets", ("esi-assets.read_assets.v1",)),
    SyncDataset("character_skills", "Skills", ("esi-skills.read_skills.v1", "esi-skills.read_skillqueue.v1")),
    SyncDataset("character_fittings", "Fittings", ("esi-fittings.read_fittings.v1",)),
    SyncDataset("character_wallet", "Wallet", ("esi-wallet.read_character_wallet.v1",)),
    SyncDataset("character_contracts", "Contracts", ("esi-contracts.read_character_contracts.v1",)),
    SyncDataset("character_research_projects", "Industry", ("esi-industry.read_character_jobs.v1",)),
    SyncDataset("character_mining_ledger", "Mining", ("esi-industry.read_character_mining.v1",)),
    SyncDataset("character_planetary_industry", "Planetary Industry", ("esi-planets.manage_planets.v1",)),
    SyncDataset("character_standings", "Standings", ("esi-characters.read_standings.v1",)),
    SyncDataset("character_jump_clones", "Jump Clones", ("esi-clones.read_clones.v1", "esi-clones.read_implants.v1")),
)


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def dataset_freshness(
    dataset: SyncDataset,
    *,
    granted_scopes: set[str],
    job: Any | None,
    now: datetime | None = None,
    disabled_reason: str | None = None,
) -> dict[str, Any]:
    checked_at = as_utc(now) or datetime.now(timezone.utc)
    missing = sorted(set(dataset.required_scopes) - granted_scopes)
    last_at = None
    status = None
    message = None
    job_id = None

    if job is not None:
        raw_status = getattr(job, "status", None)
        status = getattr(raw_status, "value", raw_status)
        last_at = as_utc(getattr(job, "finished_at", None) or getattr(job, "started_at", None) or getattr(job, "created_at", None))
        message = getattr(job, "message", None)
        job_id = getattr(job, "id", None)

    if disabled_reason:
        health = "disabled"
    elif missing:
        health = "missing_scope"
    elif status in {"queued", "running"}:
        health = "active"
    elif status == "failed":
        health = "failed"
    elif last_at is None:
        health = "never_synced"
    elif status == "skipped":
        health = "skipped"
    elif checked_at - last_at > timedelta(hours=dataset.stale_after_hours):
        health = "stale"
    else:
        health = "current"

    age_seconds = max(0, int((checked_at - last_at).total_seconds())) if last_at else None
    return {
        "key": dataset.key,
        "label": dataset.label,
        "health": health,
        "status": status,
        "last_sync_at": last_at.isoformat() if last_at else None,
        "age_seconds": age_seconds,
        "stale_after_hours": dataset.stale_after_hours,
        "missing_scopes": missing,
        "disabled_reason": disabled_reason,
        "message": message,
        "job_id": job_id,
    }
