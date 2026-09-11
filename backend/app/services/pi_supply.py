"""Permission-filtered hangar snapshots and bounded native PI calculations."""
import json
import subprocess
from datetime import datetime, timezone

from fastapi import HTTPException

from app.core.config import get_settings
from app.models.enums import LocationKind, OwnerKind
from app.services.asset_visibility import visible_asset_rows
from app.services.corporation_metadata import CORPORATION_HANGAR_FLAG, corporation_hangar_names
from app.services.permissions import can_view_section


def hangar_snapshot(user, db):
    if not can_view_section(user, "assets", db):
        return {"as_of": datetime.now(timezone.utc).isoformat(), "hangars": []}
    assets = visible_asset_rows(user, db)
    names = corporation_hangar_names(db, assets)
    return group_hangars(assets, names)


def group_hangars(assets, names):
    # Resolve only through visible records, never through arbitrary ORM parents.
    by_id = {row.id: row for row in assets}
    groups = {}
    for asset in assets:
        owner = asset.ownership_entity
        if not owner or owner.owner_kind != OwnerKind.CORPORATION:
            continue
        current, seen, division, location = asset, set(), None, None
        while current is not None and current.id not in seen:
            seen.add(current.id)
            if current.ownership_entity_id != owner.id:
                break
            if CORPORATION_HANGAR_FLAG.fullmatch(current.location_flag or ""):
                division = current.location_flag
            candidate = current.location
            if candidate and candidate.location_kind in (LocationKind.STATION, LocationKind.STRUCTURE):
                location = candidate
                break
            current = by_id.get(current.parent_asset_id)
        if not division or not location:
            continue
        # All seven divisions are selectable at known corporate hangar locations,
        # including currently empty divisions.
        for index in range(1, 8):
            flag = f"CorpSAG{index}"
            key = f"{owner.id}:{location.id}:{flag}"
            groups.setdefault(key, {
                "id": key,
                "name": f"{owner.display_name} · {location.name} · {names.get((owner.corporation_id, flag), flag)}",
                "items": {}, "oldest_synced_at": None, "has_unsynced_items": False,
            })
        group = groups[f"{owner.id}:{location.id}:{division}"]
        if asset.quantity > 0:
            key = str(asset.type_id)
            group["items"][key] = group["items"].get(key, 0) + asset.quantity
        if asset.last_synced_at:
            stamp = asset.last_synced_at.replace(tzinfo=timezone.utc) if asset.last_synced_at.tzinfo is None else asset.last_synced_at
            text = stamp.isoformat()
            if group["oldest_synced_at"] is None or text < group["oldest_synced_at"]:
                group["oldest_synced_at"] = text
        else:
            group["has_unsynced_items"] = True
    return {"as_of": datetime.now(timezone.utc).isoformat(), "hangars": sorted(groups.values(), key=lambda row: row["name"])}


def native_calculation(command, payload, extra=()):
    settings = get_settings()
    try:
        completed = subprocess.run(
            [settings.eqm_core_binary, command, "--input", "-", *extra],
            input=json.dumps(payload, allow_nan=False), text=True, encoding="utf-8",
            capture_output=True, timeout=settings.eqm_core_timeout_seconds,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=True,
        )
        result = json.loads(completed.stdout)
        expected = "eqm.pi-production.v1" if command == "pi-production" else "eqm.planetary-shortage-report.v2"
        if result.get("schema_version") != expected:
            raise ValueError("Unsupported native result")
        return {**result, "engine_used": "rust"}
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        raise HTTPException(503, "PI calculation engine unavailable. Rebuild/deploy eqm-core with this update.") from error
