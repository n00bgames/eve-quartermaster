from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import (
    Asset,
    CorporationDivision,
    EveCorporation,
    Location,
    OwnershipEntity,
)
from app.models.enums import AssetSource, LocationKind, OwnerKind
from app.services.esi_client import EsiClient


CORPORATION_HANGAR_FLAG = re.compile(r"^CorpSAG([1-7])$")


async def sync_corporation_divisions(
    client: EsiClient,
    db: Session,
    corporation: EveCorporation,
) -> tuple[int, str | None]:
    try:
        payload = await client.get(
            f"/corporations/{corporation.corporation_id}/divisions/"
        )
    except HTTPException as exc:
        return 0, _esi_detail(exc)

    now = datetime.now(timezone.utc)
    synced = 0
    for division_type in ("hangar", "wallet"):
        rows = payload.get(division_type) or []
        db.execute(
            delete(CorporationDivision).where(
                CorporationDivision.corporation_id == corporation.id,
                CorporationDivision.division_type == division_type,
            )
        )
        for row in rows:
            division = int(row["division"])
            name = str(row.get("name") or f"{division_type.title()} {division}")
            db.add(
                CorporationDivision(
                    corporation_id=corporation.id,
                    division_type=division_type,
                    division=division,
                    name=name,
                    last_synced_at=now,
                )
            )
            synced += 1
    db.flush()
    return synced, None


async def sync_corporation_structure_names(
    client: EsiClient,
    db: Session,
    corporation: EveCorporation,
) -> tuple[int, str | None]:
    try:
        rows: list[dict[str, Any]] = []
        page = 1
        while True:
            payload, headers = await client.get_with_headers(
                f"/corporations/{corporation.corporation_id}/structures/",
                params={"page": page},
            )
            rows.extend(payload or [])
            if page >= int(headers.get("X-Pages") or 1):
                break
            page += 1
    except HTTPException as exc:
        return 0, _esi_detail(exc)

    updated = 0
    for row in rows or []:
        structure_id = row.get("structure_id")
        name = row.get("name")
        if structure_id is None or not name:
            continue
        location = db.scalar(
            select(Location).where(Location.eve_location_id == int(structure_id))
        )
        if location is None:
            location = Location(
                location_kind=LocationKind.STRUCTURE,
                eve_location_id=int(structure_id),
                name=str(name),
                source=AssetSource.ESI,
            )
            db.add(location)
        else:
            location.location_kind = LocationKind.STRUCTURE
            location.name = str(name)
        location.system_id = row.get("system_id")
        location.type_id = row.get("type_id")
        updated += 1
    db.flush()
    return updated, None


def corporation_hangar_names(
    db: Session,
    assets: list[Asset],
) -> dict[tuple[int, str], str]:
    corporation_ids = {
        asset.ownership_entity.corporation_id
        for asset in assets
        if asset.ownership_entity
        and asset.ownership_entity.owner_kind == OwnerKind.CORPORATION
        and asset.ownership_entity.corporation_id is not None
    }
    if not corporation_ids:
        return {}
    divisions = db.scalars(
        select(CorporationDivision).where(
            CorporationDivision.corporation_id.in_(corporation_ids),
            CorporationDivision.division_type == "hangar",
        )
    ).all()
    return {
        (row.corporation_id, f"CorpSAG{row.division}"): row.name
        for row in divisions
    }


def asset_flag_name(
    asset: Asset,
    hangar_names: dict[tuple[int, str], str],
) -> str | None:
    raw_flag = asset.location_flag
    if not raw_flag or not CORPORATION_HANGAR_FLAG.match(raw_flag):
        return raw_flag
    owner: OwnershipEntity | None = asset.ownership_entity
    if (
        owner is None
        or owner.owner_kind != OwnerKind.CORPORATION
        or owner.corporation_id is None
    ):
        return raw_flag
    return hangar_names.get((owner.corporation_id, raw_flag), raw_flag)


def asset_location_name(asset: Asset) -> str | None:
    direct_location = asset.location
    if direct_location and not direct_location.name.startswith("Location "):
        return direct_location.name

    labels: list[str] = []
    ancestor = asset.parent_asset
    visited: set[int] = set()
    while ancestor is not None and ancestor.id not in visited:
        visited.add(ancestor.id)
        labels.append(
            ancestor.item_type.name
            if ancestor.item_type
            else "Container"
        )
        if ancestor.location:
            return " - ".join([ancestor.location.name, *reversed(labels)])
        ancestor = ancestor.parent_asset

    if labels:
        parent_id = asset.parent_asset.eve_item_id if asset.parent_asset else None
        unresolved = f"Unresolved item {parent_id}" if parent_id else "Unresolved container"
        return " - ".join([unresolved, *reversed(labels)])
    if direct_location:
        return f"Unresolved location {direct_location.eve_location_id}"
    return None


def _esi_detail(exc: HTTPException) -> str:
    detail: Any = exc.detail
    if isinstance(detail, dict):
        return str(detail.get("message") or detail)
    return str(detail)
