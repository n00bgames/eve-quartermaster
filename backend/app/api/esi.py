from __future__ import annotations

import base64
import asyncio
import secrets
import urllib.parse
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import httpx


from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.security import create_sso_state, decode_sso_state_payload, decrypt_secret, encrypt_secret
from app.db.session import SessionLocal, get_db
from app.models import Asset, Blueprint, CharacterFitting, CharacterFittingItem, CharacterSkill, CharacterSkillQueueEntry, CorporationWalletDivision, EsiSyncJob, EsiToken, EveAlliance, EveCategory, EveCharacter, EveCorporation, EveGroup, EveSystem, EveType, Location, OwnershipEntity, RecruitmentLinkedCharacter, User
from app.models.enums import AssetSource, LocationKind, OwnerKind, SyncStatus
from app.services.esi_client import EsiClient, esi_status, resolve_names
from app.services.eve_sso import validate_eve_access_token
from app.services.contracts import ACTIVE_CONTRACT_STATUSES, fetch_contract_pages, upsert_contract_rows
from app.services.corporation_metadata import sync_corporation_divisions, sync_corporation_structure_names
from app.services.mining_ledger import upsert_esi_ledger
from app.services.research_projects import (
    fetch_character_industry_jobs,
    fetch_corporation_industry_jobs,
    resolve_installer_names,
    scoped_corporation_research_rows,
    upsert_research_projects,
)
from app.services.audit import notify_if_other_user_synced_character
from app.services.analytics import create_snapshot
from app.api.auth import can_view_all_characters, get_current_user
from app.services.permissions import ROLE_RANK, can_view_section, role_rank
from app.services.recruiting import applicant_application, audit as recruitment_audit, sync_recruitment_character

router = APIRouter(prefix="/esi", tags=["esi"])

SKILL_SYNC_JOBS: dict[str, dict[str, Any]] = {}
CHARACTER_SYNC_ALL_JOBS: dict[str, dict[str, Any]] = {}


PUBLIC_SCOPES = [
    "publicData",
    "esi-location.read_location.v1",
    "esi-location.read_ship_type.v1",
    "esi-mail.organize_mail.v1",
    "esi-mail.read_mail.v1",
    "esi-mail.send_mail.v1",
    "esi-skills.read_skills.v1",
    "esi-skills.read_skillqueue.v1",
    "esi-wallet.read_character_wallet.v1",
    "esi-wallet.read_corporation_wallet.v1",
    "esi-search.search_structures.v1",
    "esi-clones.read_clones.v1",
    "esi-characters.read_contacts.v1",
    "esi-universe.read_structures.v1",
    "esi-killmails.read_killmails.v1",
    "esi-corporations.read_corporation_membership.v1",
    "esi-assets.read_assets.v1",
    "esi-planets.manage_planets.v1",
    "esi-ui.open_window.v1",
    "esi-ui.write_waypoint.v1",
    "esi-characters.write_contacts.v1",
    "esi-fittings.read_fittings.v1",
    "esi-fittings.write_fittings.v1",
    "esi-clones.read_clones.v1",
    "esi-clones.read_implants.v1",
    "esi-markets.structure_markets.v1",
    "esi-corporations.read_structures.v1",
    "esi-characters.read_loyalty.v1",
    "esi-characters.read_chat_channels.v1",
    "esi-characters.read_medals.v1",
    "esi-characters.read_standings.v1",
    "esi-characters.read_agents_research.v1",
    "esi-industry.read_character_jobs.v1",
    "esi-markets.read_character_orders.v1",
    "esi-characters.read_blueprints.v1",
    "esi-characters.read_corporation_roles.v1",
    "esi-location.read_online.v1",
    "esi-contracts.read_character_contracts.v1",
    "esi-clones.read_implants.v1",
    "esi-characters.read_fatigue.v1",
    "esi-killmails.read_corporation_killmails.v1",
    "esi-corporations.track_members.v1",
    "esi-wallet.read_corporation_wallets.v1",
    "esi-characters.read_notifications.v1",
    "esi-corporations.read_divisions.v1",
    "esi-corporations.read_contacts.v1",
    "esi-assets.read_corporation_assets.v1",
    "esi-corporations.read_titles.v1",
    "esi-corporations.read_blueprints.v1",
    "esi-contracts.read_corporation_contracts.v1",
    "esi-corporations.read_standings.v1",
    "esi-corporations.read_starbases.v1",
    "esi-industry.read_corporation_jobs.v1",
    "esi-markets.read_corporation_orders.v1",
    "esi-corporations.read_container_logs.v1",
    "esi-industry.read_character_mining.v1",
    "esi-industry.read_corporation_mining.v1",
    "esi-planets.read_customs_offices.v1",
    "esi-corporations.read_facilities.v1",
    "esi-corporations.read_medals.v1",
    "esi-characters.read_titles.v1",
    "esi-alliances.read_contacts.v1",
    "esi-characters.read_fw_stats.v1",
    "esi-corporations.read_fw_stats.v1",
    "esi-corporations.read_projects.v1",
    "esi-corporations.read_freelance_jobs.v1",
    "esi-characters.read_freelance_jobs.v1",
    "esi-structures.read_corporation.v1",
    "esi-structures.read_character.v1",
]

SKILL_SYNC_SCOPES = [
    "esi-skills.read_skills.v1",
    "esi-skills.read_skillqueue.v1",
]
CHARACTER_STANDINGS_SCOPES = ["esi-characters.read_standings.v1"]
CORPORATION_RESEARCH_SCOPES = [
    "esi-industry.read_corporation_jobs.v1",
    "esi-characters.read_corporation_roles.v1",
]
CORPORATION_RESEARCH_ROLES = {"director", "factory_manager"}

CONTACT_SYNC_SCOPES = [
    "esi-characters.read_contacts.v1",
    "esi-characters.write_contacts.v1",
]

MAIL_SYNC_SCOPES = [
    "esi-mail.read_mail.v1",
    "esi-mail.send_mail.v1",
    "esi-mail.organize_mail.v1",
]

RECRUITMENT_AUTH_SCOPES = [
    "publicData",
    "esi-skills.read_skills.v1",
]

PLANETARY_AUTH_SCOPES = [
    "esi-planets.manage_planets.v1",
]

CORE_AUTH_SCOPES = [
    "publicData",
    "esi-location.read_location.v1",
    "esi-location.read_ship_type.v1",
    "esi-universe.read_structures.v1",
    "esi-search.search_structures.v1",
    "esi-assets.read_assets.v1",
    "esi-assets.read_corporation_assets.v1",
    "esi-characters.read_blueprints.v1",
    "esi-corporations.read_blueprints.v1",
    "esi-characters.read_corporation_roles.v1",
    "esi-corporations.read_structures.v1",
    "esi-corporations.read_corporation_membership.v1",
    "esi-corporations.track_members.v1",
    "esi-corporations.read_divisions.v1",
    "esi-wallet.read_character_wallet.v1",
    "esi-wallet.read_corporation_wallets.v1",
    "esi-industry.read_character_jobs.v1",
    "esi-industry.read_corporation_jobs.v1",
    "esi-industry.read_character_mining.v1",
    "esi-contracts.read_character_contracts.v1",
    "esi-contracts.read_corporation_contracts.v1",
    "esi-skills.read_skills.v1",
    "esi-skills.read_skillqueue.v1",
    "esi-characters.read_standings.v1",
    "esi-fittings.read_fittings.v1",
    "esi-fittings.write_fittings.v1",
    "esi-clones.read_clones.v1",
    "esi-clones.read_implants.v1",
    "esi-planets.manage_planets.v1",
]


def _unique_scopes(scopes: list[str]) -> list[str]:
    return list(dict.fromkeys(scopes))


def auth_scopes_for_group(scope_group: str | None) -> list[str]:
    group = (scope_group or "core").strip().lower().replace("-", "_")
    if group in {"recruitment", "recruiting", "applicant"}:
        return _unique_scopes(RECRUITMENT_AUTH_SCOPES)
    if group in {"contact", "contacts", "standing", "standing_sync", "contact_sync"}:
        return _unique_scopes(CORE_AUTH_SCOPES + CONTACT_SYNC_SCOPES)
    if group == "mail":
        return _unique_scopes(CORE_AUTH_SCOPES + MAIL_SYNC_SCOPES)
    if group in {"planet", "planets", "planetary", "planetary_industry", "pi"}:
        return _unique_scopes(CORE_AUTH_SCOPES + PLANETARY_AUTH_SCOPES)
    if group == "full":
        return _unique_scopes(PUBLIC_SCOPES)
    return _unique_scopes(CORE_AUTH_SCOPES)


def standing_sync_scopes() -> list[str]:
    return auth_scopes_for_group("contacts")

async def refresh_access_token(token: EsiToken) -> str:
    settings = get_settings()
    try:
        refresh_token = decrypt_secret(token.encrypted_refresh_token, settings.token_encryption_key)
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "This character's stored ESI authorization can no longer be decrypted. Re-link the character through EVE SSO, then try syncing again.",
                "code": "esi_token_reauthorization_required",
            },
        ) from exc
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
        response = await client.post(
            "https://login.eveonline.com/v2/oauth/token",
            auth=httpx.BasicAuth(settings.eve_sso_client_id, settings.eve_sso_client_secret),
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "eve-quartermaster/0.1 local development",
            },
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail={"message": "EVE SSO refresh failed", "eve_response": response.text[:1000]})
    payload = response.json()
    if payload.get("refresh_token"):
        token.encrypted_refresh_token = encrypt_secret(payload["refresh_token"], settings.token_encryption_key)
    token.access_token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(payload.get("expires_in", 1200)))
    return payload["access_token"]


def chunked(values: list[int], size: int = 1000) -> list[list[int]]:
    return [values[index:index + size] for index in range(0, len(values), size)]


def parse_esi_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def location_kind_from_esi(location_type: str | None, location_id: int | None = None) -> LocationKind:
    if location_type == "other" and location_id is not None and location_id >= 1_000_000_000_000:
        return LocationKind.STRUCTURE
    return {
        "station": LocationKind.STATION,
        "solar_system": LocationKind.SYSTEM,
        "structure": LocationKind.STRUCTURE,
        "other": LocationKind.UNKNOWN,
    }.get(location_type or "", LocationKind.UNKNOWN)


def ensure_type(db: Session, type_id: int) -> EveType:
    item_type = db.get(EveType, type_id)
    if item_type is None:
        item_type = EveType(type_id=type_id, name=f"Type {type_id}", published=True)
        db.add(item_type)
        db.flush()
    return item_type


def ensure_location(db: Session, location_id: int | None, location_type: str | None = None) -> Location | None:
    if location_id is None:
        return None
    location = db.scalar(select(Location).where(Location.eve_location_id == location_id))
    if location is None:
        location = Location(
            location_kind=location_kind_from_esi(location_type, location_id),
            eve_location_id=location_id,
            name=f"Location {location_id}",
            source=AssetSource.ESI,
        )
        db.add(location)
        db.flush()
    elif location_type:
        location.location_kind = location_kind_from_esi(location_type, location_id)
    return location


async def apply_type_names(client: EsiClient, db: Session, type_ids: set[int]) -> int:
    updated = 0
    ids = sorted(type_ids)
    for type_id in ids:
        ensure_type(db, type_id)
    for chunk in chunked(ids):
        names = await client.post("/universe/names/", chunk)
        for item in names:
            if item.get("category") != "inventory_type":
                continue
            item_type = ensure_type(db, int(item["id"]))
            item_type.name = item["name"]
            updated += 1
    db.flush()
    return updated



async def apply_type_metadata(client: EsiClient, db: Session, type_ids: set[int], max_fetch: int | None = None) -> int:
    updated = 0
    fetched = 0
    for type_id in sorted(type_ids):
        if max_fetch is not None and fetched >= max_fetch:
            break
        item_type = ensure_type(db, type_id)
        if item_type.group_id is not None and item_type.group is not None and item_type.capacity is not None:
            continue
        try:
            payload = await client.get(f"/universe/types/{type_id}/", params={"language": "en"})
        except HTTPException:
            continue
        item_type.name = payload.get("name", item_type.name)
        item_type.description = payload.get("description")
        item_type.group_id = payload.get("group_id")
        item_type.volume = payload.get("volume")
        item_type.packaged_volume = payload.get("packaged_volume")
        item_type.capacity = payload.get("capacity")
        item_type.market_group_id = payload.get("market_group_id")
        item_type.published = bool(payload.get("published", True))
        if item_type.group_id is not None:
            group = db.get(EveGroup, item_type.group_id)
            if group is None or group.category_id is None:
                try:
                    group_payload = await client.get(f"/universe/groups/{item_type.group_id}/", params={"language": "en"})
                except HTTPException:
                    group_payload = None
                if group_payload:
                    group = group or EveGroup(group_id=item_type.group_id, name=group_payload.get("name", f"Group {item_type.group_id}"))
                    db.add(group)
                    group.name = group_payload.get("name", group.name)
                    group.category_id = group_payload.get("category_id")
                    group.published = bool(group_payload.get("published", True))
                    if group.category_id is not None:
                        category = db.get(EveCategory, group.category_id)
                        if category is None:
                            try:
                                category_payload = await client.get(f"/universe/categories/{group.category_id}/", params={"language": "en"})
                            except HTTPException:
                                category_payload = None
                            category = EveCategory(category_id=group.category_id, name=(category_payload or {}).get("name", f"Category {group.category_id}"), published=bool((category_payload or {}).get("published", True)))
                            db.add(category)
                        elif category.name.startswith("Category "):
                            try:
                                category_payload = await client.get(f"/universe/categories/{group.category_id}/", params={"language": "en"})
                                category.name = category_payload.get("name", category.name)
                                category.published = bool(category_payload.get("published", category.published))
                            except HTTPException:
                                pass
        updated += 1
    db.flush()
    return updated

async def apply_skill_metadata(client: EsiClient, db: Session, type_ids: set[int]) -> int:
    if not type_ids:
        return 0
    try:
        category_payload = await client.get("/universe/categories/16/", params={"language": "en"})
    except HTTPException:
        return 0

    category = db.get(EveCategory, 16)
    if category is None:
        category = EveCategory(category_id=16, name=category_payload.get("name", "Skill"), published=bool(category_payload.get("published", True)))
        db.add(category)
    else:
        category.name = category_payload.get("name", category.name)
        category.published = bool(category_payload.get("published", category.published))

    pending_type_ids = set(type_ids)
    updated = 0
    for group_id in category_payload.get("groups", []) or []:
        if not pending_type_ids:
            break
        try:
            group_payload = await client.get(f"/universe/groups/{group_id}/", params={"language": "en"})
        except HTTPException:
            continue
        group_type_ids = {int(type_id) for type_id in group_payload.get("types", []) or []}
        matched_type_ids = pending_type_ids.intersection(group_type_ids)
        if not matched_type_ids:
            continue

        group = db.get(EveGroup, int(group_id))
        if group is None:
            group = EveGroup(group_id=int(group_id), name=group_payload.get("name", f"Group {group_id}"))
            db.add(group)
        group.name = group_payload.get("name", group.name)
        group.category_id = 16
        group.published = bool(group_payload.get("published", True))

        for type_id in matched_type_ids:
            item_type = ensure_type(db, type_id)
            if item_type.group_id != int(group_id):
                item_type.group_id = int(group_id)
                updated += 1
        pending_type_ids.difference_update(matched_type_ids)

    db.flush()
    return updated
async def apply_location_names(client: EsiClient, db: Session, location_ids: set[int], location_types: dict[int, str]) -> int:
    updated = 0
    ids = sorted(location_ids)
    for location_id in ids:
        ensure_location(db, location_id, location_types.get(location_id))
    for chunk in chunked(ids):
        try:
            names = await client.post("/universe/names/", chunk)
        except HTTPException:
            names = []
        for item in names:
            location_id = int(item["id"])
            location = ensure_location(db, location_id, location_types.get(location_id))
            if location is None:
                continue
            location.name = item["name"]
            if item.get("category") == "station":
                location.location_kind = LocationKind.STATION
            elif item.get("category") == "solar_system":
                location.location_kind = LocationKind.SYSTEM
            elif item.get("category") == "structure":
                location.location_kind = LocationKind.STRUCTURE
            updated += 1

    for location_id in ids:
        location = ensure_location(db, location_id, location_types.get(location_id))
        if location is None or location.location_kind != LocationKind.STRUCTURE or not location.name.startswith("Location "):
            continue
        try:
            structure = await client.get(f"/universe/structures/{location_id}/")
        except HTTPException:
            continue
        location.name = structure.get("name", location.name)
        location.system_id = structure.get("solar_system_id")
        updated += 1
    db.flush()
    return updated

async def fetch_all_asset_pages(client: EsiClient, path: str) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    page = 1
    while True:
        payload, headers = await client.get_with_headers(path, params={"page": page})
        rows = payload or []
        assets.extend(rows)
        try:
            pages = int(headers.get("x-pages", "1"))
        except ValueError:
            pages = 1
        if page >= pages or not rows:
            break
        page += 1
    return assets



async def fetch_all_blueprint_pages(client: EsiClient, path: str) -> list[dict[str, Any]]:
    blueprints: list[dict[str, Any]] = []
    page = 1
    while True:
        payload, headers = await client.get_with_headers(path, params={"page": page})
        rows = payload or []
        blueprints.extend(rows)
        try:
            pages = int(headers.get("x-pages", "1"))
        except ValueError:
            pages = 1
        if page >= pages or not rows:
            break
        page += 1
    return blueprints


def asset_location_types(assets_payload: list[dict[str, Any]]) -> dict[int, str]:
    """Return final ESI locations, including structures reported as item locations."""
    asset_item_ids = {
        int(row["item_id"])
        for row in assets_payload
        if row.get("item_id") is not None
    }
    locations: dict[int, str] = {}
    for row in assets_payload:
        raw_location_id = row.get("location_id")
        if raw_location_id is None:
            continue
        location_id = int(raw_location_id)
        location_type = row.get("location_type")
        if location_type != "item":
            locations[location_id] = location_type or "unknown"
        elif location_id not in asset_item_ids:
            # Corporation offices in an Upwell structure are commonly reported
            # with location_type=item even though the structure is not an asset
            # row in the corporation payload.
            locations[location_id] = "structure"
    return locations


def upsert_blueprint_rows(db: Session, owner: OwnershipEntity, blueprints_payload: list[dict[str, Any]]) -> int:
    synced = 0
    for row in blueprints_payload:
        blueprint_type_id = int(row["type_id"])
        ensure_type(db, blueprint_type_id)
        location = None
        parent_asset = None
        location_id = row.get("location_id")
        if location_id is not None:
            location_id = int(location_id)
            parent_asset = db.scalar(select(Asset).where(Asset.eve_item_id == location_id))
            if parent_asset is None:
                location = ensure_location(db, location_id, "unknown")
        item_id = int(row["item_id"])
        asset = db.scalar(select(Asset).where(Asset.eve_item_id == item_id))
        if asset is None:
            asset = Asset(ownership_entity_id=owner.id, eve_item_id=item_id, type_id=blueprint_type_id)
            db.add(asset)
            db.flush()
        asset.ownership_entity_id = owner.id
        asset.type_id = blueprint_type_id
        asset.quantity = 1
        asset.location_id = location.id if location else None
        asset.parent_asset_id = parent_asset.id if parent_asset else None
        asset.location_flag = row.get("location_flag")
        asset.is_singleton = True
        asset.is_blueprint_copy = int(row.get("runs", -1)) != -1
        asset.source = AssetSource.ESI
        asset.last_synced_at = datetime.now(timezone.utc)

        blueprint = db.scalar(select(Blueprint).where(Blueprint.asset_id == asset.id))
        if blueprint is None:
            blueprint = Blueprint(ownership_entity_id=owner.id, blueprint_type_id=blueprint_type_id, asset_id=asset.id)
            db.add(blueprint)
        blueprint.asset_id = asset.id
        blueprint.ownership_entity_id = owner.id
        blueprint.blueprint_type_id = blueprint_type_id
        blueprint.material_efficiency = int(row.get("material_efficiency", 0))
        blueprint.time_efficiency = int(row.get("time_efficiency", 0))
        runs = int(row.get("runs", -1))
        blueprint.runs_remaining = None if runs == -1 else runs
        blueprint.is_copy = runs != -1
        blueprint.location_id = (
            parent_asset.location_id
            if parent_asset and parent_asset.location_id
            else (location.id if location else None)
        )
        blueprint.source = AssetSource.ESI
        blueprint.last_synced_at = datetime.now(timezone.utc)
        synced += 1
    db.flush()
    return synced


async def apply_corporation_metadata(client: EsiClient, db: Session, corp: EveCorporation, corp_payload: dict[str, Any] | None = None, *, ensure_owner_row: bool = True) -> EveCorporation:
    if corp_payload is None:
        corp_payload = await client.get(f"/corporations/{corp.corporation_id}/")
    alliance_row = None
    if corp_payload.get("alliance_id"):
        alliance_payload = await client.get(f"/alliances/{corp_payload['alliance_id']}/")
        alliance_row = db.scalar(select(EveAlliance).where(EveAlliance.alliance_id == corp_payload["alliance_id"]))
        if alliance_row is None:
            alliance_row = EveAlliance(alliance_id=corp_payload["alliance_id"], name=alliance_payload["name"])
            db.add(alliance_row)
        alliance_row.name = alliance_payload["name"]
        alliance_row.ticker = alliance_payload.get("ticker")
        db.flush()
    corp.name = corp_payload["name"]
    corp.ticker = corp_payload.get("ticker")
    corp.alliance_id = alliance_row.id if alliance_row else None
    corp.ceo_character_eve_id = corp_payload.get("ceo_id")
    corp.member_count = corp_payload.get("member_count")
    if corp.ceo_character_eve_id:
        try:
            ceo_payload = await client.get(f"/characters/{corp.ceo_character_eve_id}/")
            ceo = db.scalar(select(EveCharacter).where(EveCharacter.character_id == corp.ceo_character_eve_id))
            if ceo is None:
                ceo = EveCharacter(character_id=corp.ceo_character_eve_id, name=ceo_payload["name"])
                db.add(ceo)
            ceo.name = ceo_payload["name"]
            ceo.security_status = ceo_payload.get("security_status")
            ceo.corporation_id = corp.id
            ceo.alliance_id = alliance_row.id if alliance_row else None
        except Exception:
            pass
    if ensure_owner_row:
        ensure_owner(db, OwnerKind.CORPORATION, corp.name, corporation_id=corp.id)
    db.flush()
    return corp


async def apply_character_affiliation(client: EsiClient, db: Session, character: EveCharacter, character_payload: dict[str, Any]) -> None:
    corp_payload = await client.get(f"/corporations/{character_payload['corporation_id']}/")
    corp_row = db.scalar(select(EveCorporation).where(EveCorporation.corporation_id == character_payload["corporation_id"]))
    if corp_row is None:
        corp_row = EveCorporation(corporation_id=character_payload["corporation_id"], name=corp_payload["name"])
        db.add(corp_row)
        db.flush()
    await apply_corporation_metadata(client, db, corp_row, corp_payload, ensure_owner_row=False)
    character.corporation_id = corp_row.id
    character.alliance_id = corp_row.alliance_id
    character.security_status = character_payload.get("security_status")
    db.flush()


def upsert_asset_rows(db: Session, owner: OwnershipEntity, assets_payload: list[dict[str, Any]]) -> tuple[int, int]:
    synced = 0
    final_location_types = asset_location_types(assets_payload)
    for row in assets_payload:
        type_id = int(row["type_id"])
        raw_location_id = row.get("location_id")
        location_id = int(raw_location_id) if raw_location_id is not None else None
        location = (
            ensure_location(db, location_id, final_location_types[location_id])
            if location_id in final_location_types
            else None
        )
        asset = db.scalar(select(Asset).where(Asset.eve_item_id == int(row["item_id"])))
        if asset is None:
            asset = Asset(ownership_entity_id=owner.id, eve_item_id=int(row["item_id"]), type_id=type_id)
            db.add(asset)
        asset.ownership_entity_id = owner.id
        asset.type_id = type_id
        asset.quantity = int(row.get("quantity", 1))
        asset.location_id = location.id if location else None
        asset.parent_asset_id = None
        asset.location_flag = row.get("location_flag")
        asset.is_singleton = bool(row.get("is_singleton", False))
        asset.is_blueprint_copy = row.get("is_blueprint_copy")
        asset.source = AssetSource.ESI
        asset.last_synced_at = datetime.now(timezone.utc)
        synced += 1
    db.flush()

    linked_parents = 0
    for row in assets_payload:
        if row.get("location_type") != "item" or row.get("location_id") is None:
            continue
        child = db.scalar(select(Asset).where(Asset.eve_item_id == int(row["item_id"])))
        parent = db.scalar(select(Asset).where(Asset.eve_item_id == int(row["location_id"])))
        if child is not None and parent is not None:
            child.parent_asset_id = parent.id
            linked_parents += 1
    return synced, linked_parents

def ensure_owner(db: Session, owner_kind: OwnerKind, display_name: str, character_id: int | None = None, corporation_id: int | None = None, alliance_id: int | None = None) -> OwnershipEntity:
    existing = db.scalar(
        select(OwnershipEntity).where(
            OwnershipEntity.owner_kind == owner_kind,
            OwnershipEntity.character_id == character_id,
            OwnershipEntity.corporation_id == corporation_id,
            OwnershipEntity.alliance_id == alliance_id,
        )
    )
    if existing:
        existing.display_name = display_name
        return existing
    owner = OwnershipEntity(owner_kind=owner_kind, display_name=display_name, character_id=character_id, corporation_id=corporation_id, alliance_id=alliance_id)
    db.add(owner)
    db.flush()
    return owner


@router.get("/status")
async def get_status() -> dict[str, Any]:
    return await esi_status()


@router.post("/resolve")
async def resolve(payload: dict[str, Any]) -> dict[str, Any]:
    names = payload.get("names")
    if isinstance(names, str):
        names = [line.strip() for line in names.splitlines()]
    if not isinstance(names, list):
        raise HTTPException(status_code=400, detail="names must be a list or newline-separated string")
    return await resolve_names(names)


@router.post("/import/type/{type_id}")
async def import_type(type_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = EsiClient()
    payload = await client.get(f"/universe/types/{type_id}/", params={"language": "en"})
    item_type = db.get(EveType, type_id)
    if item_type is None:
        item_type = EveType(type_id=type_id, name=payload["name"])
        db.add(item_type)
    item_type.name = payload["name"]
    item_type.description = payload.get("description")
    item_type.group_id = payload.get("group_id")
    item_type.volume = payload.get("volume")
    item_type.packaged_volume = payload.get("packaged_volume")
    item_type.capacity = payload.get("capacity")
    item_type.market_group_id = payload.get("market_group_id")
    item_type.published = bool(payload.get("published", True))
    db.commit()
    return {"status": "imported", "type_id": type_id, "name": item_type.name}


@router.post("/import/character/{character_id}")
async def import_character(character_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = EsiClient()
    payload = await client.get(f"/characters/{character_id}/")
    corp_row = db.scalar(select(EveCorporation).where(EveCorporation.corporation_id == payload["corporation_id"]))
    alliance_row = None
    if payload.get("alliance_id"):
        alliance_row = db.scalar(select(EveAlliance).where(EveAlliance.alliance_id == payload["alliance_id"]))
    character = db.scalar(select(EveCharacter).where(EveCharacter.character_id == character_id))
    if character is None:
        character = EveCharacter(character_id=character_id, name=payload["name"])
        db.add(character)
    character.name = payload["name"]
    character.security_status = payload.get("security_status")
    character.corporation_id = corp_row.id if corp_row else None
    character.alliance_id = alliance_row.id if alliance_row else None
    db.flush()
    owner = ensure_owner(db, OwnerKind.CHARACTER, character.name, character_id=character.id)
    db.commit()
    return {"status": "imported", "character_id": character_id, "name": character.name, "owner_id": owner.id}


@router.post("/import/corporation/{corporation_id}")
async def import_corporation(corporation_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = EsiClient()
    payload = await client.get(f"/corporations/{corporation_id}/")
    corp = db.scalar(select(EveCorporation).where(EveCorporation.corporation_id == corporation_id))
    if corp is None:
        corp = EveCorporation(corporation_id=corporation_id, name=payload["name"])
        db.add(corp)
        db.flush()
    await apply_corporation_metadata(client, db, corp, payload)
    owner = ensure_owner(db, OwnerKind.CORPORATION, corp.name, corporation_id=corp.id)
    db.commit()
    return {"status": "imported", "corporation_id": corporation_id, "name": corp.name, "owner_id": owner.id}


@router.post("/import/alliance/{alliance_id}")
async def import_alliance(alliance_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = EsiClient()
    payload = await client.get(f"/alliances/{alliance_id}/")
    alliance = db.scalar(select(EveAlliance).where(EveAlliance.alliance_id == alliance_id))
    if alliance is None:
        alliance = EveAlliance(alliance_id=alliance_id, name=payload["name"])
        db.add(alliance)
    alliance.name = payload["name"]
    alliance.ticker = payload.get("ticker")
    db.flush()
    owner = ensure_owner(db, OwnerKind.ALLIANCE, alliance.name, alliance_id=alliance.id)
    db.commit()
    return {"status": "imported", "alliance_id": alliance_id, "name": alliance.name, "owner_id": owner.id}


@router.post("/import/system/{system_id}")
async def import_system(system_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = EsiClient()
    payload = await client.get(f"/universe/systems/{system_id}/", params={"language": "en"})
    system = db.get(EveSystem, system_id)
    if system is None:
        system = EveSystem(system_id=system_id, name=payload["name"])
        db.add(system)
    system.name = payload["name"]
    system.constellation_id = payload.get("constellation_id")
    system.security_status = payload.get("security_status")
    location = db.scalar(select(Location).where(Location.location_kind == LocationKind.SYSTEM, Location.eve_location_id == system_id))
    if location is None:
        location = Location(location_kind=LocationKind.SYSTEM, eve_location_id=system_id, name=system.name, source=AssetSource.ESI)
        db.add(location)
    location.name = system.name
    location.system_id = system_id
    db.commit()
    return {"status": "imported", "system_id": system_id, "name": system.name, "location_id": location.id}


@router.post("/import/station/{station_id}")
async def import_station(station_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = EsiClient()
    payload = await client.get(f"/universe/stations/{station_id}/")
    location = db.scalar(select(Location).where(Location.location_kind == LocationKind.STATION, Location.eve_location_id == station_id))
    if location is None:
        location = Location(location_kind=LocationKind.STATION, eve_location_id=station_id, name=payload["name"], source=AssetSource.ESI)
        db.add(location)
    location.name = payload["name"]
    location.system_id = payload.get("system_id")
    db.commit()
    return {"status": "imported", "station_id": station_id, "name": location.name, "location_id": location.id}





WAYPOINT_SCOPE = "esi-ui.write_waypoint.v1"


def find_waypoint_token(db: Session, current_user: User, token_id: int | None = None) -> EsiToken:
    if token_id is not None:
        token, _character = get_linked_token(db, token_id)
        require_token_access(token, current_user, db)
        require_scope(token, WAYPOINT_SCOPE, "Setting an EVE destination")
        return token
    tokens = db.scalars(
        select(EsiToken)
        .where(EsiToken.user_id == current_user.id)
        .where(EsiToken.revoked_at.is_(None))
        .order_by(EsiToken.id.desc())
    ).all()
    for token in tokens:
        if WAYPOINT_SCOPE in token_scopes(token):
            return token
    raise HTTPException(status_code=400, detail="Setting an EVE destination requires esi-ui.write_waypoint.v1. Re-link a character through EVE SSO after enabling that scope.")


@router.post("/ui/waypoint")
async def set_eve_waypoint(payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    destination_id = payload.get("destination_id")
    if destination_id is None:
        raise HTTPException(status_code=400, detail="destination_id is required")
    token = find_waypoint_token(db, current_user, payload.get("token_id"))
    access_token = await refresh_access_token(token)
    params = {
        "destination_id": int(destination_id),
        "clear_other_waypoints": str(bool(payload.get("clear_other_waypoints", True))).lower(),
        "add_to_beginning": str(bool(payload.get("add_to_beginning", False))).lower(),
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://esi.evetech.net/latest/ui/autopilot/waypoint/",
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=f"EVE waypoint failed: {response.text[:500]}")
    return {"status": "sent", "destination_id": int(destination_id)}

@router.get("/linked-characters")
def linked_characters(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    query = (
        select(EsiToken, EveCharacter, User)
        .join(EveCharacter, EveCharacter.id == EsiToken.character_id)
        .join(User, User.id == EsiToken.user_id)
        .where(EsiToken.revoked_at.is_(None))
        .order_by(EveCharacter.name, EsiToken.created_at.desc())
    )
    if current_user.role not in {"host", "admin"}:
        query = query.where(EsiToken.user_id == current_user.id)
    rows = db.execute(query).all()
    results = []
    for token, character, linked_user in rows:
        can_manage_link = token.user_id == current_user.id or current_user.role in {"host", "admin"}
        latest_job = db.scalar(
            select(EsiSyncJob)
            .where(EsiSyncJob.token_id == token.id)
            .order_by(EsiSyncJob.finished_at.desc().nullslast(), EsiSyncJob.created_at.desc())
            .limit(1)
        )
        last_sync_at = None
        if latest_job:
            last_sync_at = latest_job.finished_at or latest_job.started_at or latest_job.created_at
        results.append(
            {
                "token_id": token.id,
                "character_id": character.character_id,
                "character_name": character.name,
                "security_status": character.security_status,
                "linked_user_id": token.user_id,
                "linked_user_display_name": linked_user.display_name,
                "can_sync_assets": can_manage_link,
                "can_unlink": can_manage_link,
                "scopes": token.scopes,
                "access_token_expires_at": token.access_token_expires_at.isoformat() if token.access_token_expires_at else None,
                "linked_at": token.created_at.isoformat() if token.created_at else None,
                "last_sync_at": last_sync_at.isoformat() if last_sync_at else None,
                "last_sync_type": latest_job.sync_type if latest_job else None,
                "last_sync_status": latest_job.status.value if latest_job else None,
                "missing_public_scopes": missing_scopes(token, CORE_AUTH_SCOPES),
                "missing_standing_scopes": missing_scopes(token, CONTACT_SYNC_SCOPES),
            }
        )
    return results



def serialize_character_skill_record(skill: CharacterSkill) -> dict[str, Any]:
    skill_type = skill.skill_type
    group = skill_type.group if skill_type else None
    category = group.category if group else None
    return {
        "id": skill.id,
        "skill_type_id": skill.skill_type_id,
        "skill_name": skill_type.name if skill_type else f"Type {skill.skill_type_id}",
        "skill_group_name": group.name if group else "Uncategorized",
        "skill_category_name": group.name if group else (category.name if category and category.name != "Skill" else "Uncategorized"),
        "trained_skill_level": skill.trained_skill_level,
        "active_skill_level": skill.active_skill_level,
        "skillpoints_in_skill": skill.skillpoints_in_skill,
        "last_synced_at": skill.last_synced_at.isoformat() if skill.last_synced_at else None,
    }


def serialize_skill_queue_entry(entry: CharacterSkillQueueEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "queue_position": entry.queue_position,
        "skill_type_id": entry.skill_type_id,
        "skill_name": entry.skill_type.name if entry.skill_type else f"Type {entry.skill_type_id}",
        "finished_level": entry.finished_level,
        "training_start_sp": entry.training_start_sp,
        "level_start_sp": entry.level_start_sp,
        "level_end_sp": entry.level_end_sp,
        "start_date": entry.start_date.isoformat() if entry.start_date else None,
        "finish_date": entry.finish_date.isoformat() if entry.finish_date else None,
    }


@router.get("/character-skills")
def list_character_skills(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.execute(
        select(EsiToken, EveCharacter)
        .join(EveCharacter, EveCharacter.id == EsiToken.character_id)
        .where(EsiToken.revoked_at.is_(None))
        .order_by(EveCharacter.name, EsiToken.created_at.desc())
    ).all()
    can_view_all_skills = can_view_section(current_user, "skills", db)
    results = []
    for token, character in rows:
        if token.user_id != current_user.id and not can_view_all_skills:
            continue
        skills = db.scalars(select(CharacterSkill).options(selectinload(CharacterSkill.skill_type).selectinload(EveType.group).selectinload(EveGroup.category)).where(CharacterSkill.character_id == character.id).order_by(CharacterSkill.skillpoints_in_skill.desc(), CharacterSkill.skill_type_id)).all()
        queue = db.scalars(select(CharacterSkillQueueEntry).options(selectinload(CharacterSkillQueueEntry.skill_type)).where(CharacterSkillQueueEntry.character_id == character.id).order_by(CharacterSkillQueueEntry.queue_position)).all()
        results.append(
            {
                "token_id": token.id,
                "character_id": character.character_id,
                "character_name": character.name,
                "security_status": character.security_status,
                "owner_user_id": token.user_id,
                "sync_opt_out": character.sync_opt_out,
                "admin_override_visible": character.sync_opt_out and current_user.role in {"host", "admin"} and token.user_id != current_user.id,
                "can_sync": can_force_sync_character_token(token, character, current_user, db),
                "total_skill_points": character.total_skill_points,
                "unallocated_skill_points": character.unallocated_skill_points,
                "skills_synced_at": character.skills_synced_at.isoformat() if character.skills_synced_at else None,
                "skill_queue_synced_at": character.skill_queue_synced_at.isoformat() if character.skill_queue_synced_at else None,
                "missing_skill_scopes": missing_scopes(token, SKILL_SYNC_SCOPES),
                "skill_count": len(skills),
                "queue_count": len(queue),
                "skills": [serialize_character_skill_record(skill) for skill in skills],
                "queue": [serialize_skill_queue_entry(entry) for entry in queue],
            }
        )
    return results


async def sync_character_skills_for_token(token_id: int, current_user: User, db: Session, *, allow_opt_out_override: bool = True) -> dict[str, Any]:
    token, character = get_linked_token(db, token_id)
    if not can_force_sync_character_token(token, character, current_user, db):
        raise HTTPException(status_code=403, detail="You can only sync characters you own or are permitted to administer")
    if character.sync_opt_out and (not allow_opt_out_override or (token.user_id != current_user.id and current_user.role not in {"host", "admin"})):
        raise HTTPException(status_code=403, detail=f"{character.name} has opted out of Quartermaster sync")
    require_scope(token, "esi-skills.read_skills.v1", f"Reading skills for {character.name}")
    require_scope(token, "esi-skills.read_skillqueue.v1", f"Reading skill queue for {character.name}")

    job = EsiSyncJob(token_id=token.id, sync_type="character_skills", status=SyncStatus.RUNNING, started_at=datetime.now(timezone.utc))
    db.add(job)
    db.flush()

    try:
        access_token = await refresh_access_token(token)
        client = EsiClient(access_token=access_token)
        character_payload = await client.get(f"/characters/{character.character_id}/")
        character.name = character_payload.get("name", character.name)
        await apply_character_affiliation(client, db, character, character_payload)
        skills_payload = await client.get(f"/characters/{character.character_id}/skills/")
        queue_payload = await client.get(f"/characters/{character.character_id}/skillqueue/")
        skill_rows = skills_payload.get("skills", []) or []
        queue_rows = queue_payload or []
        type_ids = {int(row["skill_id"]) for row in skill_rows if row.get("skill_id") is not None}
        type_ids.update({int(row["skill_id"]) for row in queue_rows if row.get("skill_id") is not None})
        type_names = await apply_type_names(client, db, type_ids)
        type_metadata = await apply_skill_metadata(client, db, type_ids)
        metadata_note = " Skill group metadata refreshed from the EVE Skill category."
        now = datetime.now(timezone.utc)

        for row in skill_rows:
            skill_type_id = int(row["skill_id"])
            skill = db.scalar(select(CharacterSkill).where(CharacterSkill.character_id == character.id, CharacterSkill.skill_type_id == skill_type_id))
            if skill is None:
                skill = CharacterSkill(character_id=character.id, skill_type_id=skill_type_id)
                db.add(skill)
            skill.trained_skill_level = int(row.get("trained_skill_level", 0))
            skill.active_skill_level = int(row.get("active_skill_level", 0))
            skill.skillpoints_in_skill = int(row.get("skillpoints_in_skill", 0))
            skill.last_synced_at = now

        db.execute(delete(CharacterSkillQueueEntry).where(CharacterSkillQueueEntry.character_id == character.id))
        for row in queue_rows:
            db.add(
                CharacterSkillQueueEntry(
                    character_id=character.id,
                    queue_position=int(row.get("queue_position", 0)),
                    skill_type_id=int(row["skill_id"]),
                    finished_level=int(row.get("finished_level", 0)),
                    training_start_sp=row.get("training_start_sp"),
                    level_start_sp=row.get("level_start_sp"),
                    level_end_sp=row.get("level_end_sp"),
                    start_date=parse_esi_datetime(row.get("start_date")),
                    finish_date=parse_esi_datetime(row.get("finish_date")),
                    last_synced_at=now,
                )
            )

        character.total_skill_points = int(skills_payload.get("total_sp", 0))
        character.unallocated_skill_points = skills_payload.get("unallocated_sp")
        character.skills_synced_at = now
        character.skill_queue_synced_at = now
        character.last_synced_at = now
        job.status = SyncStatus.SUCCESS
        job.message = f"Synced {len(skill_rows)} trained skills and {len(queue_rows)} queued skills. Resolved {type_names} skill names and {type_metadata} skill metadata records during the skills sync.{metadata_note}"
        notify_if_other_user_synced_character(db, sync_label="skills", actor_user=current_user, character=character, detail=f"{len(skill_rows)} trained skills and {len(queue_rows)} queue entries were refreshed.")
        job.finished_at = now
        create_snapshot(db, scope_type="character", scope_id=character.id, source="character_skills", message=job.message)
        db.commit()
        return {"status": "synced", "character_name": character.name, "skill_count": len(skill_rows), "queue_count": len(queue_rows), "total_skill_points": character.total_skill_points, "job_id": job.id}
    except Exception as exc:
        job.status = SyncStatus.FAILED
        job.message = str(exc)
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        raise


@router.post("/sync/character-skills/{token_id:int}")
async def sync_character_skills(token_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    return await sync_character_skills_for_token(token_id, current_user, db)


def skill_sync_job_payload(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "created_at": job["created_at"],
        "updated_at": job.get("updated_at"),
        "completed_at": job.get("completed_at"),
        "total_count": job["total_count"],
        "processed_count": job["processed_count"],
        "success_count": job["success_count"],
        "failed_count": job["failed_count"],
        "skipped_count": job["skipped_count"],
        "current_character_name": job.get("current_character_name"),
        "results": job["results"][-12:],
        "errors": job["errors"][-12:],
    }


def utc_job_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def skill_sync_eligible_tokens(db: Session, current_user: User) -> tuple[list[int], int]:
    rows = db.execute(
        select(EsiToken, EveCharacter)
        .join(EveCharacter, EveCharacter.id == EsiToken.character_id)
        .where(EsiToken.revoked_at.is_(None))
        .order_by(EveCharacter.name, EsiToken.created_at.desc())
    ).all()
    token_ids: list[int] = []
    skipped = 0
    seen_characters: set[int] = set()
    for token, character in rows:
        if character.id in seen_characters:
            skipped += 1
            continue
        seen_characters.add(character.id)
        if character.sync_opt_out:
            skipped += 1
            continue
        if not can_force_sync_character_token(token, character, current_user, db):
            skipped += 1
            continue
        if missing_scopes(token, SKILL_SYNC_SCOPES):
            skipped += 1
            continue
        token_ids.append(token.id)
    return token_ids, skipped


async def run_skill_sync_all_job(job_id: str, token_ids: list[int], user_id: int) -> None:
    job = SKILL_SYNC_JOBS[job_id]
    job["status"] = "running"
    job["updated_at"] = utc_job_iso()
    try:
        for token_id in token_ids:
            if job.get("cancel_requested"):
                job["status"] = "cancelled"
                job["completed_at"] = utc_job_iso()
                job["updated_at"] = job["completed_at"]
                return
            with SessionLocal() as db:
                user = db.get(User, user_id)
                if user is None:
                    job["failed_count"] += 1
                    job["errors"].append("The user that started this skill sync no longer exists.")
                    break
                token = db.get(EsiToken, token_id)
                character = db.get(EveCharacter, token.character_id) if token else None
                character_name = character.name if character else f"Token {token_id}"
                job["current_character_name"] = character_name
                job["updated_at"] = utc_job_iso()
                try:
                    result = await sync_character_skills_for_token(token_id, user, db, allow_opt_out_override=False)
                    job["success_count"] += 1
                    job["results"].append({"character_name": result["character_name"], "skill_count": result["skill_count"], "queue_count": result["queue_count"]})
                except Exception as exc:
                    job["failed_count"] += 1
                    detail = getattr(exc, "detail", None) or str(exc)
                    job["errors"].append(f"{character_name}: {detail}")
                finally:
                    job["processed_count"] += 1
                    job["updated_at"] = utc_job_iso()
            await asyncio.sleep(0)
        job["current_character_name"] = None
        job["status"] = "complete" if job["failed_count"] == 0 else "failed"
        job["completed_at"] = utc_job_iso()
        job["updated_at"] = job["completed_at"]
    except Exception as exc:
        job["current_character_name"] = None
        job["status"] = "failed"
        job["failed_count"] += max(0, job["total_count"] - job["processed_count"])
        job["errors"].append(f"Skill sync worker stopped unexpectedly: {exc}")
        job["completed_at"] = utc_job_iso()
        job["updated_at"] = job["completed_at"]

@router.post("/sync/character-skills/all")
async def start_character_skills_sync_all(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    token_ids, skipped = skill_sync_eligible_tokens(db, current_user)
    if not token_ids:
        raise HTTPException(status_code=400, detail="No eligible characters with skill scopes are available to sync.")
    job_id = uuid.uuid4().hex
    now = utc_job_iso()
    SKILL_SYNC_JOBS[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
        "total_count": len(token_ids),
        "processed_count": 0,
        "success_count": 0,
        "failed_count": 0,
        "skipped_count": skipped,
        "current_character_name": None,
        "results": [],
        "errors": [],
    }
    asyncio.create_task(run_skill_sync_all_job(job_id, token_ids, current_user.id))
    return skill_sync_job_payload(SKILL_SYNC_JOBS[job_id])


@router.get("/sync/character-skills/all/{job_id}")
def get_character_skills_sync_all_job(job_id: str, current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    job = SKILL_SYNC_JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Skill sync job was not found. It may have been cleared by a backend restart.")
    return skill_sync_job_payload(job)

async def sync_character_fittings_for_token(token_id: int, current_user: User, db: Session, *, allow_opt_out_override: bool = True) -> dict[str, Any]:
    token, character = get_linked_token(db, token_id)
    if not can_force_sync_character_token(token, character, current_user, db):
        raise HTTPException(status_code=403, detail="You can only sync characters you own or are permitted to administer")
    if character.sync_opt_out and (not allow_opt_out_override or (token.user_id != current_user.id and current_user.role not in {"host", "admin"})):
        raise HTTPException(status_code=403, detail=f"{character.name} has opted out of Quartermaster sync")
    require_scope(token, "esi-fittings.read_fittings.v1", f"Reading fittings for {character.name}")

    job = EsiSyncJob(token_id=token.id, sync_type="character_fittings", status=SyncStatus.RUNNING, started_at=datetime.now(timezone.utc))
    db.add(job)
    db.flush()

    try:
        access_token = await refresh_access_token(token)
        client = EsiClient(access_token=access_token)
        fittings_payload = await client.get(f"/characters/{character.character_id}/fittings/")
        fitting_rows = fittings_payload or []
        type_ids = {int(row["ship_type_id"]) for row in fitting_rows if row.get("ship_type_id") is not None}
        for row in fitting_rows:
            type_ids.update({int(item["type_id"]) for item in row.get("items", []) if item.get("type_id") is not None})
        type_names = await apply_type_names(client, db, type_ids)
        type_metadata = await apply_type_metadata(client, db, type_ids, max_fetch=80)
        now = datetime.now(timezone.utc)
        seen_ids: set[int] = set()

        for row in fitting_rows:
            eve_fitting_id = int(row["fitting_id"])
            seen_ids.add(eve_fitting_id)
            fitting = db.scalar(select(CharacterFitting).where(CharacterFitting.character_id == character.id, CharacterFitting.eve_fitting_id == eve_fitting_id))
            if fitting is None:
                fitting = CharacterFitting(character_id=character.id, eve_fitting_id=eve_fitting_id, ship_type_id=int(row["ship_type_id"]), name=row.get("name") or f"Fitting {eve_fitting_id}")
                db.add(fitting)
                db.flush()
            fitting.name = row.get("name") or fitting.name
            fitting.description = row.get("description")
            fitting.ship_type_id = int(row["ship_type_id"])
            fitting.last_synced_at = now
            db.execute(delete(CharacterFittingItem).where(CharacterFittingItem.fitting_id == fitting.id))
            for item in row.get("items", []) or []:
                db.add(
                    CharacterFittingItem(
                        fitting_id=fitting.id,
                        type_id=int(item["type_id"]),
                        flag=str(item.get("flag") or "Other"),
                        quantity=int(item.get("quantity", 1)),
                    )
                )

        if seen_ids:
            stale = db.scalars(select(CharacterFitting).where(CharacterFitting.character_id == character.id, CharacterFitting.eve_fitting_id.is_not(None), CharacterFitting.eve_fitting_id.notin_(list(seen_ids)))).all()
        else:
            stale = db.scalars(select(CharacterFitting).where(CharacterFitting.character_id == character.id, CharacterFitting.eve_fitting_id.is_not(None))).all()
        for fitting in stale:
            db.delete(fitting)

        character.last_synced_at = now
        job.status = SyncStatus.SUCCESS
        opt_out_note = " Admin override used for opted-out character." if character.sync_opt_out and current_user.role in {"host", "admin"} and token.user_id != current_user.id else ""
        job.message = f"Synced {len(fitting_rows)} saved fittings. Resolved {type_names} fitting item names and {type_metadata} fitting type records.{opt_out_note}"
        notify_if_other_user_synced_character(db, sync_label="fittings", actor_user=current_user, character=character, detail=f"{len(fitting_rows)} saved fittings were refreshed.")
        job.finished_at = now
        db.commit()
        return {"status": "synced", "character_name": character.name, "fitting_count": len(fitting_rows), "job_id": job.id}
    except Exception as exc:
        job.status = SyncStatus.FAILED
        job.message = str(exc)
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        raise


@router.post("/sync/character-fittings/{token_id}")
async def sync_character_fittings(token_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    return await sync_character_fittings_for_token(token_id, current_user, db)


@router.delete("/linked-characters/{token_id}")
def unlink_character(token_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    token, character = get_linked_token(db, token_id)
    if token.user_id != current_user.id and current_user.role not in {"host", "admin"}:
        raise HTTPException(status_code=403, detail="Only admins or the account that authorized SSO can unlink this character")
    token.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "unlinked", "token_id": token.id, "character_name": character.name}

async def sync_character_assets_for_token(token_id: int, current_user: User, db: Session, *, allow_opt_out_override: bool = True) -> dict[str, Any]:
    token = db.get(EsiToken, token_id)
    if token is None or token.revoked_at is not None:
        raise HTTPException(status_code=404, detail="Linked character token was not found")
    character = db.get(EveCharacter, token.character_id)
    if character is None:
        raise HTTPException(status_code=404, detail="Linked character was not found")
    if not can_force_sync_character_token(token, character, current_user, db):
        raise HTTPException(status_code=403, detail="You can only sync characters you own or are permitted to administer")
    if character.sync_opt_out and (not allow_opt_out_override or (token.user_id != current_user.id and current_user.role not in {"host", "admin"})):
        raise HTTPException(status_code=403, detail=f"{character.name} has opted out of Quartermaster sync")
    require_scope(token, "esi-assets.read_assets.v1", f"Reading assets for {character.name}")

    owner = ensure_owner(db, OwnerKind.CHARACTER, character.name, character_id=character.id)
    job = EsiSyncJob(token_id=token.id, ownership_entity_id=owner.id, sync_type="character_assets", status=SyncStatus.RUNNING, started_at=datetime.now(timezone.utc))
    db.add(job)
    db.flush()

    try:
        access_token = await refresh_access_token(token)
        client = EsiClient(access_token=access_token)
        assets_payload = await fetch_all_asset_pages(client, f"/characters/{character.character_id}/assets/")
        type_ids = {int(row["type_id"]) for row in assets_payload}
        location_types = asset_location_types(assets_payload)
        type_names = await apply_type_names(client, db, type_ids)
        location_names = await apply_location_names(client, db, set(location_types.keys()), location_types)

        synced, linked_parents = await asyncio.to_thread(upsert_asset_rows, db, owner, assets_payload)

        job.status = SyncStatus.SUCCESS
        job.message = f"Synced {synced} character asset rows. Resolved {type_names} type names and {location_names} location names. Linked {linked_parents} contained assets."
        notify_if_other_user_synced_character(db, sync_label="inventory", actor_user=current_user, character=character, detail=f"{synced} asset rows were refreshed.")
        job.finished_at = datetime.now(timezone.utc)
        create_snapshot(db, scope_type="character", scope_id=character.id, source="character_assets", message=job.message)
        db.commit()
        return {"status": "synced", "character_name": character.name, "asset_rows": synced, "job_id": job.id}
    except Exception as exc:
        job.status = SyncStatus.FAILED
        job.message = str(exc)
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        raise


@router.post("/sync/character-assets/{token_id}")
async def sync_character_assets(token_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    return await sync_character_assets_for_token(token_id, current_user, db)


async def sync_character_contracts_for_token(token_id: int, current_user: User, db: Session, *, allow_opt_out_override: bool = True) -> dict[str, Any]:
    token = db.get(EsiToken, token_id)
    if token is None or token.revoked_at is not None:
        raise HTTPException(status_code=404, detail="Linked character token was not found")
    character = db.get(EveCharacter, token.character_id)
    if character is None:
        raise HTTPException(status_code=404, detail="Linked character was not found")
    if not can_force_sync_character_token(token, character, current_user, db):
        raise HTTPException(status_code=403, detail="You can only sync characters you own or are permitted to administer")
    if character.sync_opt_out and (not allow_opt_out_override or (token.user_id != current_user.id and current_user.role not in {"host", "admin"})):
        raise HTTPException(status_code=403, detail=f"{character.name} has opted out of Quartermaster sync")
    require_scope(token, "esi-contracts.read_character_contracts.v1", f"Syncing contracts for {character.name}")

    owner = db.get(User, token.user_id)
    job = EsiSyncJob(token_id=token.id, sync_type="character_contracts", status=SyncStatus.RUNNING, started_at=datetime.now(timezone.utc))
    db.add(job)
    db.flush()
    job_id = job.id
    db.commit()
    try:
        access_token = await refresh_access_token(token)
        db.commit()
        client = EsiClient(access_token=access_token)
        rows = await fetch_contract_pages(client, f"/characters/{character.character_id}/contracts/")
        synced = upsert_contract_rows(db, rows, scope_type="character", owner_user=owner, character=character)
        job.status = SyncStatus.SUCCESS
        job.message = f"Synced {synced} character contracts for {character.name}."
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": "synced", "character_name": character.name, "contracts": synced, "active_contracts": sum(1 for row in rows if row.get("status") in ACTIVE_CONTRACT_STATUSES), "job_id": job.id}
    except Exception as exc:
        db.rollback()
        failed_job = db.get(EsiSyncJob, job_id)
        if failed_job is not None:
            failed_job.status = SyncStatus.FAILED
            failed_job.message = str(exc)
            failed_job.finished_at = datetime.now(timezone.utc)
            db.commit()
        raise

async def sync_character_research_for_token(token_id: int, current_user: User, db: Session, *, allow_opt_out_override: bool = True) -> dict[str, Any]:
    token = db.get(EsiToken, token_id)
    if token is None or token.revoked_at is not None:
        raise HTTPException(status_code=404, detail="Linked character token was not found")
    character = db.get(EveCharacter, token.character_id)
    if character is None:
        raise HTTPException(status_code=404, detail="Linked character was not found")
    if not can_force_sync_character_token(token, character, current_user, db):
        raise HTTPException(status_code=403, detail="You can only sync characters you own or are permitted to administer")
    if character.sync_opt_out and (not allow_opt_out_override or (token.user_id != current_user.id and current_user.role not in {"host", "admin"})):
        raise HTTPException(status_code=403, detail=f"{character.name} has opted out of Quartermaster sync")
    require_scope(token, "esi-industry.read_character_jobs.v1", f"Syncing research projects for {character.name}")

    job = EsiSyncJob(token_id=token.id, sync_type="character_research_projects", status=SyncStatus.RUNNING, started_at=datetime.now(timezone.utc))
    db.add(job)
    db.flush()
    job_id = job.id
    db.commit()
    try:
        access_token = await refresh_access_token(token)
        db.commit()
        client = EsiClient(access_token=access_token)
        rows = await fetch_character_industry_jobs(client, character.character_id)
        synced, active = upsert_research_projects(db, character.id, rows)
        job.status = SyncStatus.SUCCESS
        job.message = f"Synced {synced} research projects for {character.name}."
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": "synced", "character_name": character.name, "projects": synced, "active_projects": active, "job_id": job.id}
    except Exception as exc:
        db.rollback()
        failed_job = db.get(EsiSyncJob, job_id)
        if failed_job is not None:
            failed_job.status = SyncStatus.FAILED
            failed_job.message = str(exc)
            failed_job.finished_at = datetime.now(timezone.utc)
            db.commit()
        raise


async def sync_character_mining_for_token(token_id: int, current_user: User, db: Session, *, allow_opt_out_override: bool = True) -> dict[str, Any]:
    token = db.get(EsiToken, token_id)
    if token is None or token.revoked_at is not None:
        raise HTTPException(status_code=404, detail="Linked character token was not found")
    character = db.get(EveCharacter, token.character_id)
    if character is None:
        raise HTTPException(status_code=404, detail="Linked character was not found")
    if not can_force_sync_character_token(token, character, current_user, db):
        raise HTTPException(status_code=403, detail="You can only sync characters you own or are permitted to administer")
    if character.sync_opt_out and (not allow_opt_out_override or (token.user_id != current_user.id and current_user.role not in {"host", "admin"})):
        raise HTTPException(status_code=403, detail=f"{character.name} has opted out of Quartermaster sync")
    require_scope(token, "esi-industry.read_character_mining.v1", f"Syncing mining history for {character.name}")

    job = EsiSyncJob(token_id=token.id, sync_type="character_mining_ledger", status=SyncStatus.RUNNING, started_at=datetime.now(timezone.utc))
    db.add(job)
    db.flush()
    job_id = job.id
    db.commit()
    try:
        access_token = await refresh_access_token(token)
        db.commit()
        client = EsiClient(access_token=access_token)
        rows: list[dict[str, Any]] = []
        page = 1
        while True:
            payload, headers = await client.get_with_headers(f"/characters/{character.character_id}/mining/", params={"page": page})
            rows.extend(payload or [])
            if page >= int(headers.get("X-Pages") or 1):
                break
            page += 1
        market_rows = await client.get("/markets/prices/") or []
        prices = {int(row["type_id"]): float(row.get("average_price") or row.get("adjusted_price") or 0) for row in market_rows if row.get("type_id") is not None}
        result = upsert_esi_ledger(db, character, rows, prices)
        job = db.get(EsiSyncJob, job_id)
        job.status = SyncStatus.SUCCESS
        job.message = f"Synced {len(rows)} persistent mining ledger rows for {character.name}; older EQM history was retained."
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": "synced", **result, "job_id": job.id}
    except Exception as exc:
        db.rollback()
        failed_job = db.get(EsiSyncJob, job_id)
        if failed_job is not None:
            failed_job.status = SyncStatus.FAILED
            failed_job.message = str(exc)
            failed_job.finished_at = datetime.now(timezone.utc)
            db.commit()
        raise

def corporation_role_names(payload: dict[str, Any] | None) -> set[str]:
    roles: set[str] = set()
    for key, values in (payload or {}).items():
        if key.startswith("roles") and isinstance(values, list):
            roles.update(str(value).strip().lower() for value in values)
    return roles


async def sync_corporation_research_for_tokens(
    token_ids: list[int],
    corporation_id: int,
    current_user: User,
    db: Session,
    *,
    allow_opt_out_override: bool = True,
) -> dict[str, Any]:
    corporation = db.get(EveCorporation, corporation_id)
    if corporation is None:
        raise HTTPException(status_code=404, detail="Corporation was not found")

    candidate_errors: list[str] = []
    for token_id in token_ids:
        token = db.get(EsiToken, token_id)
        character = db.get(EveCharacter, token.character_id) if token and token.revoked_at is None else None
        if token is None or character is None:
            continue
        if not can_force_sync_character_token(token, character, current_user, db):
            continue
        if character.sync_opt_out and not allow_opt_out_override:
            continue
        if missing_scopes(token, CORPORATION_RESEARCH_SCOPES):
            continue
        try:
            access_token = await refresh_access_token(token)
            db.commit()
            client = EsiClient(access_token=access_token)
            roles = corporation_role_names(await client.get(f"/characters/{character.character_id}/roles/"))
            if not roles.intersection(CORPORATION_RESEARCH_ROLES):
                continue
            character_payload = await client.get(f"/characters/{character.character_id}/")
            await apply_character_affiliation(client, db, character, character_payload)
            if character.corporation_id != corporation.id:
                db.rollback()
                continue

            job = EsiSyncJob(
                token_id=token.id,
                sync_type="corporation_research_projects",
                status=SyncStatus.RUNNING,
                started_at=datetime.now(timezone.utc),
            )
            db.add(job)
            db.flush()
            job_id = job.id
            db.commit()
            try:
                rows = await fetch_corporation_industry_jobs(client, corporation.corporation_id)
                rows, linked_installers_only = scoped_corporation_research_rows(
                    db,
                    corporation.id,
                    rows,
                )
                installer_names = await resolve_installer_names(client, rows)
                synced, active = upsert_research_projects(
                    db,
                    None,
                    rows,
                    corporation_id=corporation.id,
                    source_type="corporation",
                    installer_names=installer_names,
                )
                job.status = SyncStatus.SUCCESS
                scope_label = "linked-character corporation" if linked_installers_only else "corporation"
                job.message = f"Synced {synced} {scope_label} research projects for {corporation.name} using {character.name}."
                job.finished_at = datetime.now(timezone.utc)
                db.commit()
                return {
                    "status": "synced",
                    "character_name": corporation.name,
                    "corporation_name": corporation.name,
                    "projects": synced,
                    "active_projects": active,
                    "job_id": job.id,
                }
            except Exception as exc:
                db.rollback()
                failed_job = db.get(EsiSyncJob, job_id)
                if failed_job is not None:
                    failed_job.status = SyncStatus.FAILED
                    failed_job.message = str(exc)
                    failed_job.finished_at = datetime.now(timezone.utc)
                    db.commit()
                raise
        except Exception as exc:
            db.rollback()
            detail = getattr(exc, "detail", None) or str(exc)
            candidate_errors.append(f"{character.name}: {detail}")

    if candidate_errors:
        raise HTTPException(status_code=502, detail="; ".join(candidate_errors[:3]))
    return {
        "status": "skipped",
        "character_name": corporation.name,
        "corporation_name": corporation.name,
        "reason": "No linked character with Director or Factory Manager and the corporation research scopes was available.",
    }

@router.post("/sync/character-research/{token_id:int}")
async def sync_character_research(token_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    return await sync_character_research_for_token(token_id, current_user, db)

def character_sync_all_job_payload(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "created_at": job["created_at"],
        "updated_at": job.get("updated_at"),
        "completed_at": job.get("completed_at"),
        "total_count": job["total_count"],
        "processed_count": job["processed_count"],
        "success_count": job["success_count"],
        "failed_count": job["failed_count"],
        "skipped_count": job["skipped_count"],
        "current_character_name": job.get("current_character_name"),
        "current_sync_kind": job.get("current_sync_kind"),
        "results": job["results"][-16:],
        "errors": job["errors"][-16:],
    }


async def prechecked_corporation_research_tokens(
    db: Session,
    current_user: User,
    corporation_tokens: dict[int, list[int]],
) -> tuple[dict[int, list[int]], int]:
    eligible: dict[int, list[int]] = {}
    skipped = 0
    for corporation_id, token_ids in corporation_tokens.items():
        corporation = db.get(EveCorporation, corporation_id)
        if corporation is None or corporation.hide_from_corporation_list:
            skipped += 1
            continue

        role_token_ids: list[int] = []
        for token_id in token_ids:
            token = db.get(EsiToken, token_id)
            character = db.get(EveCharacter, token.character_id) if token and token.revoked_at is None else None
            if token is None or character is None:
                continue
            if not can_force_sync_character_token(token, character, current_user, db):
                continue
            try:
                access_token = await refresh_access_token(token)
                db.commit()
                client = EsiClient(access_token=access_token)
                character_payload = await client.get(f"/characters/{character.character_id}/")
                if int(character_payload.get("corporation_id") or 0) != corporation.corporation_id:
                    continue
                roles = corporation_role_names(await client.get(f"/characters/{character.character_id}/roles/"))
                if roles.intersection(CORPORATION_RESEARCH_ROLES):
                    role_token_ids.append(token.id)
            except Exception:
                db.rollback()

        if role_token_ids:
            eligible[corporation_id] = role_token_ids
        else:
            skipped += 1
    return eligible, skipped


async def character_sync_all_work_items(
    db: Session,
    current_user: User,
    requested_kinds: set[str] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    required_scopes = {
        "assets": ["esi-assets.read_assets.v1"],
        "skills": SKILL_SYNC_SCOPES,
        "standings": CHARACTER_STANDINGS_SCOPES,
        "fittings": ["esi-fittings.read_fittings.v1"],
        "contracts": ["esi-contracts.read_character_contracts.v1"],
        "research": ["esi-industry.read_character_jobs.v1"],
        "mining": ["esi-industry.read_character_mining.v1"],
        "planets": ["esi-planets.manage_planets.v1"],
    }
    if requested_kinds is not None:
        required_scopes = {kind: scopes for kind, scopes in required_scopes.items() if kind in requested_kinds}
    research_requested = requested_kinds is None or "research" in requested_kinds
    rows = db.execute(
        select(EsiToken, EveCharacter)
        .join(EveCharacter, EveCharacter.id == EsiToken.character_id)
        .where(EsiToken.revoked_at.is_(None))
        .order_by(EveCharacter.name, EsiToken.created_at.desc())
    ).all()
    work_items: list[dict[str, Any]] = []
    corporation_tokens: dict[int, list[int]] = {}
    skipped = 0
    seen_characters: set[int] = set()
    for token, character in rows:
        if character.id in seen_characters:
            skipped += len(required_scopes)
            continue
        seen_characters.add(character.id)
        if character.sync_opt_out or not can_force_sync_character_token(token, character, current_user, db):
            skipped += len(required_scopes)
            continue
        for kind, scopes in required_scopes.items():
            if missing_scopes(token, scopes):
                skipped += 1
                continue
            work_items.append({"token_id": token.id, "sync_kind": kind})
        if research_requested and character.corporation_id and not missing_scopes(token, CORPORATION_RESEARCH_SCOPES):
            corporation_tokens.setdefault(character.corporation_id, []).append(token.id)

    corporation_tokens, corporation_skipped = await prechecked_corporation_research_tokens(
        db,
        current_user,
        corporation_tokens,
    )
    skipped += corporation_skipped
    for corporation_id, token_ids in corporation_tokens.items():
        work_items.append(
            {
                "token_id": token_ids[0],
                "token_ids": token_ids,
                "corporation_id": corporation_id,
                "sync_kind": "corporation_research",
            }
        )
    return work_items, skipped

async def run_character_sync_all_job(job_id: str, work_items: list[dict[str, Any]], user_id: int) -> None:
    from app.api.character_standings import sync_character_standings_for_token
    from app.api.planetary_industry import sync_planetary_industry_for_token

    job = CHARACTER_SYNC_ALL_JOBS[job_id]
    job["status"] = "running"
    job["updated_at"] = utc_job_iso()
    sync_handlers = {
        "assets": sync_character_assets_for_token,
        "skills": sync_character_skills_for_token,
        "standings": sync_character_standings_for_token,
        "fittings": sync_character_fittings_for_token,
        "contracts": sync_character_contracts_for_token,
        "research": sync_character_research_for_token,
        "mining": sync_character_mining_for_token,
        "planets": sync_planetary_industry_for_token,
    }
    try:
        for item in work_items:
            token_id = int(item["token_id"])
            sync_kind = str(item["sync_kind"])
            with SessionLocal() as db:
                user = db.get(User, user_id)
                if user is None:
                    job["failed_count"] += 1
                    job["errors"].append("The user that started this character sync no longer exists.")
                    break
                token = db.get(EsiToken, token_id)
                character = db.get(EveCharacter, token.character_id) if token else None
                display_name = character.name if character else f"Token {token_id}"
                if sync_kind == "corporation_research":
                    corporation = db.get(EveCorporation, int(item["corporation_id"]))
                    display_name = corporation.name if corporation else f"Corporation {item['corporation_id']}"
                job["current_character_name"] = display_name
                job["current_sync_kind"] = sync_kind
                job["updated_at"] = utc_job_iso()
                try:
                    if sync_kind == "corporation_research":
                        result = await sync_corporation_research_for_tokens(
                            [int(value) for value in item["token_ids"]],
                            int(item["corporation_id"]),
                            user,
                            db,
                            allow_opt_out_override=False,
                        )
                    else:
                        result = await sync_handlers[sync_kind](token_id, user, db, allow_opt_out_override=False)
                    result_status = result.get("status", "synced")
                    if result_status == "skipped":
                        job["skipped_count"] += 1
                    else:
                        job["success_count"] += 1
                    job["results"].append(
                        {
                            "character_name": result.get("character_name", display_name),
                            "sync_kind": sync_kind,
                            "status": result_status,
                            "reason": result.get("reason"),
                        }
                    )
                except Exception as exc:
                    job["failed_count"] += 1
                    detail = getattr(exc, "detail", None) or str(exc)
                    job["errors"].append(f"{display_name} {sync_kind}: {detail}")
                finally:
                    job["processed_count"] += 1
                    job["updated_at"] = utc_job_iso()
            await asyncio.sleep(0)
        job["current_character_name"] = None
        job["current_sync_kind"] = None
        job["status"] = "complete" if job["failed_count"] == 0 else "failed"
        job["completed_at"] = utc_job_iso()
        job["updated_at"] = job["completed_at"]
    except Exception as exc:
        job["current_character_name"] = None
        job["current_sync_kind"] = None
        job["status"] = "failed"
        job["failed_count"] += max(0, job["total_count"] - job["processed_count"])
        job["errors"].append(f"Character sync worker stopped unexpectedly: {exc}")
        job["completed_at"] = utc_job_iso()
        job["updated_at"] = job["completed_at"]

@router.post("/sync/characters/all")
async def start_characters_sync_all(sync_kind: str | None = Query(None), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    requested_kinds = {sync_kind} if sync_kind else None
    if requested_kinds and not requested_kinds.issubset({"assets", "skills", "standings", "fittings", "contracts", "research", "mining", "planets"}):
        raise HTTPException(status_code=400, detail="Unsupported character sync kind")
    work_items, skipped = await character_sync_all_work_items(db, current_user, requested_kinds)
    if not work_items:
        raise HTTPException(status_code=400, detail="No eligible character sync tasks are available. Check character privacy settings, role access, and ESI scopes.")
    job_id = uuid.uuid4().hex
    now = utc_job_iso()
    CHARACTER_SYNC_ALL_JOBS[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
        "total_count": len(work_items),
        "processed_count": 0,
        "success_count": 0,
        "failed_count": 0,
        "skipped_count": skipped,
        "current_character_name": None,
        "current_sync_kind": None,
        "results": [],
        "errors": [],
    }
    asyncio.create_task(run_character_sync_all_job(job_id, work_items, current_user.id))
    return character_sync_all_job_payload(CHARACTER_SYNC_ALL_JOBS[job_id])


@router.get("/sync/characters/all/{job_id}")
def get_characters_sync_all_job(job_id: str, current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    job = CHARACTER_SYNC_ALL_JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Character sync job was not found. It may have been cleared by a backend restart.")
    return character_sync_all_job_payload(job)


@router.post("/sync/linked-corporations")
async def sync_linked_corporations(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.execute(
        select(EsiToken, EveCharacter)
        .join(EveCharacter, EveCharacter.id == EsiToken.character_id)
        .where(EsiToken.revoked_at.is_(None))
        .order_by(EveCharacter.name, EsiToken.created_at.desc())
    ).all()
    refreshed = 0
    metadata_refreshed = 0
    skipped = 0
    failed = 0
    errors: list[str] = []
    for token, character in rows:
        if token.user_id != current_user.id and not can_view_all_characters(current_user, db):
            skipped += 1
            continue
        try:
            access_token = await refresh_access_token(token)
            client = EsiClient(access_token=access_token)
            character_payload = await client.get(f"/characters/{character.character_id}/")
            character.name = character_payload["name"]
            await apply_character_affiliation(client, db, character, character_payload)
            await asyncio.to_thread(db.commit)
            refreshed += 1
        except Exception as exc:
            await asyncio.to_thread(db.rollback)
            failed += 1
            errors.append(f"{character.name}: {exc}")
    public_client = EsiClient()
    for corp in db.scalars(select(EveCorporation).order_by(EveCorporation.name)).all():
        try:
            await apply_corporation_metadata(public_client, db, corp, ensure_owner_row=False)
            await asyncio.to_thread(db.commit)
            metadata_refreshed += 1
        except Exception as exc:
            await asyncio.to_thread(db.rollback)
            failed += 1
            errors.append(f"{corp.name}: {exc}")
    return {"status": "refreshed", "characters_refreshed": refreshed, "corporations_refreshed": metadata_refreshed, "skipped": skipped, "failed": failed, "errors": errors[:5]}

@router.post("/sync/corporation-assets/{token_id}")
async def sync_corporation_assets(token_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    token, character = get_linked_token(db, token_id)
    require_token_access(token, current_user, db)
    require_scope(token, "esi-assets.read_corporation_assets.v1", f"Syncing corporation assets for {character.name}")

    access_token = await refresh_access_token(token)
    client = EsiClient(access_token=access_token)
    character_payload = await client.get(f"/characters/{character.character_id}/")
    await apply_character_affiliation(client, db, character, character_payload)
    corporation = db.get(EveCorporation, character.corporation_id) if character.corporation_id else None
    if corporation is None:
        raise HTTPException(status_code=400, detail="Linked character does not have a known corporation")

    owner = ensure_owner(db, OwnerKind.CORPORATION, corporation.name, corporation_id=corporation.id)
    job = EsiSyncJob(token_id=token.id, ownership_entity_id=owner.id, sync_type="corporation_assets", status=SyncStatus.RUNNING, started_at=datetime.now(timezone.utc))
    db.add(job)
    db.flush()

    try:
        assets_payload = await fetch_all_asset_pages(client, f"/corporations/{corporation.corporation_id}/assets/")
        type_ids = {int(row["type_id"]) for row in assets_payload}
        location_types = asset_location_types(assets_payload)
        type_names = await apply_type_names(client, db, type_ids)
        division_names, division_warning = await sync_corporation_divisions(client, db, corporation)
        structure_names, structure_warning = await sync_corporation_structure_names(client, db, corporation)
        location_names = await apply_location_names(client, db, set(location_types.keys()), location_types)
        synced, linked_parents = await asyncio.to_thread(upsert_asset_rows, db, owner, assets_payload)
        corporation.last_synced_at = datetime.now(timezone.utc)
        job.status = SyncStatus.SUCCESS
        warnings = [warning for warning in (division_warning, structure_warning) if warning]
        job.message = (
            f"Synced {synced} corporation asset rows. Resolved {type_names} type names, "
            f"{location_names + structure_names} location names, and {division_names} division names. "
            f"Linked {linked_parents} contained assets."
            + (f" Metadata warnings: {'; '.join(warnings)}" if warnings else "")
        )
        notify_if_other_user_synced_character(db, sync_label="corporation assets", actor_user=current_user, character=character, detail=f"{synced} corporation asset rows for {corporation.name} were refreshed using this character token.")
        job.finished_at = datetime.now(timezone.utc)
        create_snapshot(db, scope_type="corporation", scope_id=corporation.id, source="corporation_assets", message=job.message)
        await asyncio.to_thread(db.commit)
        return {"status": "synced", "corporation_name": corporation.name, "asset_rows": synced, "division_names": division_names, "structure_names": structure_names, "warnings": warnings, "job_id": job.id}
    except Exception as exc:
        job.status = SyncStatus.FAILED
        job.message = str(exc)
        job.finished_at = datetime.now(timezone.utc)
        await asyncio.to_thread(db.commit)
        raise


@router.post("/sync/corporation-blueprints/{token_id}")
async def sync_corporation_blueprints(token_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    token, character = get_linked_token(db, token_id)
    require_token_access(token, current_user, db)
    require_scope(token, "esi-corporations.read_blueprints.v1", f"Syncing corporation blueprints for {character.name}")

    access_token = await refresh_access_token(token)
    client = EsiClient(access_token=access_token)
    character_payload = await client.get(f"/characters/{character.character_id}/")
    await apply_character_affiliation(client, db, character, character_payload)
    corporation = db.get(EveCorporation, character.corporation_id) if character.corporation_id else None
    if corporation is None:
        raise HTTPException(status_code=400, detail="Linked character does not have a known corporation")

    owner = ensure_owner(db, OwnerKind.CORPORATION, corporation.name, corporation_id=corporation.id)
    job = EsiSyncJob(token_id=token.id, ownership_entity_id=owner.id, sync_type="corporation_blueprints", status=SyncStatus.RUNNING, started_at=datetime.now(timezone.utc))
    db.add(job)
    db.flush()

    try:
        blueprints_payload = await fetch_all_blueprint_pages(client, f"/corporations/{corporation.corporation_id}/blueprints/")
        blueprint_type_ids = {int(row["type_id"]) for row in blueprints_payload}
        type_names = await apply_type_names(client, db, blueprint_type_ids)
        location_ids = {int(row["location_id"]) for row in blueprints_payload if row.get("location_id") is not None}
        location_names = await apply_location_names(client, db, location_ids, {location_id: "unknown" for location_id in location_ids})
        synced = await asyncio.to_thread(upsert_blueprint_rows, db, owner, blueprints_payload)
        job.status = SyncStatus.SUCCESS
        job.message = f"Synced {synced} corporation blueprint rows. Resolved {type_names} blueprint names and {location_names} locations."
        notify_if_other_user_synced_character(db, sync_label="corporation blueprints", actor_user=current_user, character=character, detail=f"{synced} corporation blueprint rows for {corporation.name} were refreshed using this character token.")
        job.finished_at = datetime.now(timezone.utc)
        create_snapshot(db, scope_type="corporation", scope_id=corporation.id, source="corporation_blueprints", message=job.message)
        await asyncio.to_thread(db.commit)
        return {"status": "synced", "corporation_name": corporation.name, "blueprint_rows": synced, "job_id": job.id}
    except Exception as exc:
        job.status = SyncStatus.FAILED
        job.message = str(exc)
        job.finished_at = datetime.now(timezone.utc)
        await asyncio.to_thread(db.commit)
        raise


def upsert_corporation_wallet_rows(db: Session, corporation: EveCorporation, rows: list[dict[str, Any]]) -> int:
    synced_at = datetime.now(timezone.utc)
    synced = 0
    for row in rows:
        division = int(row["division"])
        wallet = db.scalar(
            select(CorporationWalletDivision).where(
                CorporationWalletDivision.corporation_id == corporation.id,
                CorporationWalletDivision.division == division,
            )
        )
        if wallet is None:
            wallet = CorporationWalletDivision(corporation_id=corporation.id, division=division)
            db.add(wallet)
        wallet.balance = Decimal(str(row.get("balance", 0)))
        wallet.last_synced_at = synced_at
        synced += 1
    return synced

@router.post("/sync/corporation-wallets/{token_id}")
async def sync_corporation_wallets(token_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    token, character = get_linked_token(db, token_id)
    require_token_access(token, current_user, db)
    require_scope(token, "esi-wallet.read_corporation_wallets.v1", f"Syncing corporation wallet divisions for {character.name}")

    access_token = await refresh_access_token(token)
    client = EsiClient(access_token=access_token)
    character_payload = await client.get(f"/characters/{character.character_id}/")
    await apply_character_affiliation(client, db, character, character_payload)
    corporation = db.get(EveCorporation, character.corporation_id) if character.corporation_id else None
    if corporation is None:
        raise HTTPException(status_code=400, detail="Linked character does not have a known corporation")

    owner = ensure_owner(db, OwnerKind.CORPORATION, corporation.name, corporation_id=corporation.id)
    job = EsiSyncJob(token_id=token.id, ownership_entity_id=owner.id, sync_type="corporation_wallets", status=SyncStatus.RUNNING, started_at=datetime.now(timezone.utc))
    db.add(job)
    db.flush()

    try:
        wallet_payload = await client.get(f"/corporations/{corporation.corporation_id}/wallets/")
        division_names, division_warning = await sync_corporation_divisions(client, db, corporation)
        synced = await asyncio.to_thread(upsert_corporation_wallet_rows, db, corporation, wallet_payload or [])
        corporation.last_synced_at = datetime.now(timezone.utc)
        job.status = SyncStatus.SUCCESS
        job.message = f"Synced {synced} corporation wallet division balances and {division_names} division names." + (f" Metadata warning: {division_warning}" if division_warning else "")
        notify_if_other_user_synced_character(db, sync_label="corporation wallets", actor_user=current_user, character=character, detail=f"{synced} wallet division balances for {corporation.name} were refreshed using this character token.")
        job.finished_at = datetime.now(timezone.utc)
        create_snapshot(db, scope_type="corporation", scope_id=corporation.id, source="corporation_wallets", message=job.message)
        await asyncio.to_thread(db.commit)
        return {"status": "synced", "corporation_name": corporation.name, "wallet_divisions": synced, "job_id": job.id}
    except Exception as exc:
        job.status = SyncStatus.FAILED
        job.message = str(exc)
        job.finished_at = datetime.now(timezone.utc)
        await asyncio.to_thread(db.commit)
        raise
def token_scopes(token: EsiToken) -> set[str]:
    return {scope.strip() for scope in (token.scopes or "").split() if scope.strip()}


def require_scope(token: EsiToken, scope: str, action: str) -> None:
    if scope not in token_scopes(token):
        raise HTTPException(status_code=400, detail=f"{action} requires {scope}. Re-link this character through EVE SSO after enabling that scope on the EVE developer app.")



def missing_scopes(token: EsiToken, required_scopes: list[str]) -> list[str]:
    granted = token_scopes(token)
    return [scope for scope in required_scopes if scope not in granted]

def get_linked_token(db: Session, token_id: int) -> tuple[EsiToken, EveCharacter]:
    token = db.get(EsiToken, token_id)
    if token is None or token.revoked_at is not None:
        raise HTTPException(status_code=404, detail="Linked character token was not found")
    character = db.get(EveCharacter, token.character_id)
    if character is None:
        raise HTTPException(status_code=404, detail="Linked character was not found")
    return token, character



def require_token_access(token: EsiToken, current_user: User, db: Session) -> None:
    if token.user_id != current_user.id and not can_view_all_characters(current_user, db):
        raise HTTPException(status_code=403, detail="You can only use your own linked characters")

def can_force_sync_character_token(token: EsiToken, character: EveCharacter, current_user: User, db: Session) -> bool:
    if token.user_id == current_user.id:
        return True
    if can_view_all_characters(current_user, db):
        return True
    if role_rank(current_user, db) < ROLE_RANK["officer"]:
        return False
    if character.owner_user_id is None:
        return False
    owner = db.get(User, character.owner_user_id)
    return owner is not None and role_rank(owner, db) < ROLE_RANK["officer"]
async def fetch_character_contacts(db: Session, token: EsiToken, character: EveCharacter) -> list[dict[str, Any]]:
    require_scope(token, "esi-characters.read_contacts.v1", f"Reading contacts for {character.name}")
    access_token = await refresh_access_token(token)
    client = EsiClient(access_token=access_token)
    contacts: list[dict[str, Any]] = []
    page = 1
    while True:
        payload, headers = await client.get_with_headers(f"/characters/{character.character_id}/contacts/", params={"page": page})
        rows = payload or []
        contacts.extend(rows)
        try:
            pages = int(headers.get("x-pages", "1"))
        except ValueError:
            pages = 1
        if page >= pages or not rows:
            break
        page += 1
    db.flush()
    return contacts


async def resolve_contact_names(client: EsiClient, contact_ids: set[int]) -> dict[int, str]:
    names: dict[int, str] = {}
    for chunk in chunked(sorted(contact_ids), 1000):
        try:
            payload = await client.post("/universe/names/", chunk)
        except HTTPException:
            continue
        for item in payload or []:
            names[int(item["id"])] = item.get("name", str(item["id"]))
    return names


def contact_write_groups(rows: list[dict[str, Any]]) -> dict[tuple[float, bool], list[int]]:
    groups: dict[tuple[float, bool], list[int]] = {}
    for row in rows:
        key = (float(row.get("standing", 0)), bool(row.get("is_watched", False)))
        groups.setdefault(key, []).append(int(row["contact_id"]))
    return groups


def build_contact_plan(source_contacts: list[dict[str, Any]], target_contacts: list[dict[str, Any]], overwrite_existing: bool) -> dict[str, Any]:
    target_by_id = {int(contact["contact_id"]): contact for contact in target_contacts}
    create: list[dict[str, Any]] = []
    update: list[dict[str, Any]] = []
    skip: list[dict[str, Any]] = []
    for source in source_contacts:
        contact_id = int(source["contact_id"])
        target = target_by_id.get(contact_id)
        source_standing = float(source.get("standing", 0))
        source_watched = bool(source.get("is_watched", False))
        if target is None:
            create.append(source)
            continue
        target_standing = float(target.get("standing", 0))
        target_watched = bool(target.get("is_watched", False))
        if overwrite_existing and (target_standing != source_standing or target_watched != source_watched):
            update.append(source)
        else:
            skip.append(source)
    return {"create": create, "update": update, "skip": skip}


def contact_summary_rows(rows: list[dict[str, Any]], names: dict[int, str], limit: int = 20) -> list[dict[str, Any]]:
    return [
        {
            "contact_id": int(row["contact_id"]),
            "name": names.get(int(row["contact_id"]), f"Contact {row['contact_id']}"),
            "contact_type": row.get("contact_type"),
            "standing": row.get("standing", 0),
            "is_watched": bool(row.get("is_watched", False)),
        }
        for row in rows[:limit]
    ]


def parse_contact_sync_payload(payload: dict[str, Any]) -> tuple[int, list[int], bool]:
    source_token_id = payload.get("source_token_id")
    target_token_ids = payload.get("target_token_ids")
    if not isinstance(source_token_id, int):
        raise HTTPException(status_code=400, detail="source_token_id is required")
    if not isinstance(target_token_ids, list) or not target_token_ids:
        raise HTTPException(status_code=400, detail="Choose at least one target character")
    clean_targets = [int(token_id) for token_id in target_token_ids if int(token_id) != source_token_id]
    if not clean_targets:
        raise HTTPException(status_code=400, detail="Choose at least one target character different from the source")
    return source_token_id, clean_targets, bool(payload.get("overwrite_existing", False))


@router.get("/standings/{token_id}")
@router.get("/contacts/{token_id}")
async def character_contacts(token_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    token, character = get_linked_token(db, token_id)
    require_token_access(token, current_user, db)
    contacts = await fetch_character_contacts(db, token, character)
    access_token = await refresh_access_token(token)
    names = await resolve_contact_names(EsiClient(access_token=access_token), {int(contact["contact_id"]) for contact in contacts})
    db.commit()
    return {
        "character_name": character.name,
        "character_id": character.character_id,
        "contact_count": len(contacts),
        "contacts": contact_summary_rows(contacts, names, limit=200),
    }


@router.post("/standings/preview")
@router.post("/contacts/preview")
async def preview_contact_sync(payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    source_token_id, target_token_ids, overwrite_existing = parse_contact_sync_payload(payload)
    source_token, source_character = get_linked_token(db, source_token_id)
    require_token_access(source_token, current_user, db)
    source_contacts = await fetch_character_contacts(db, source_token, source_character)
    access_token = await refresh_access_token(source_token)
    names = await resolve_contact_names(EsiClient(access_token=access_token), {int(contact["contact_id"]) for contact in source_contacts})

    targets = []
    totals = {"create": 0, "update": 0, "skip": 0}
    for target_token_id in target_token_ids:
        target_token, target_character = get_linked_token(db, target_token_id)
        require_token_access(target_token, current_user, db)
        require_scope(target_token, "esi-characters.write_contacts.v1", f"Writing contacts for {target_character.name}")
        target_contacts = await fetch_character_contacts(db, target_token, target_character)
        plan = build_contact_plan(source_contacts, target_contacts, overwrite_existing)
        for key in totals:
            totals[key] += len(plan[key])
        targets.append(
            {
                "token_id": target_token.id,
                "character_id": target_character.character_id,
                "character_name": target_character.name,
                "create_count": len(plan["create"]),
                "update_count": len(plan["update"]),
                "skip_count": len(plan["skip"]),
                "create_sample": contact_summary_rows(plan["create"], names),
                "update_sample": contact_summary_rows(plan["update"], names),
            }
        )
    db.commit()
    return {
        "source_character_name": source_character.name,
        "source_contact_count": len(source_contacts),
        "overwrite_existing": overwrite_existing,
        "totals": totals,
        "targets": targets,
    }


@router.post("/standings/apply")
@router.post("/contacts/apply")
async def apply_contact_sync(payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    source_token_id, target_token_ids, overwrite_existing = parse_contact_sync_payload(payload)
    source_token, source_character = get_linked_token(db, source_token_id)
    require_token_access(source_token, current_user, db)
    source_contacts = await fetch_character_contacts(db, source_token, source_character)

    targets = []
    total_created = 0
    total_updated = 0
    for target_token_id in target_token_ids:
        target_token, target_character = get_linked_token(db, target_token_id)
        require_token_access(target_token, current_user, db)
        require_scope(target_token, "esi-characters.write_contacts.v1", f"Writing contacts for {target_character.name}")
        target_contacts = await fetch_character_contacts(db, target_token, target_character)
        plan = build_contact_plan(source_contacts, target_contacts, overwrite_existing)
        access_token = await refresh_access_token(target_token)
        client = EsiClient(access_token=access_token)

        created = 0
        for (standing, watched), contact_ids in contact_write_groups(plan["create"]).items():
            for batch in chunked(contact_ids, 100):
                await client.post(f"/characters/{target_character.character_id}/contacts/", batch, params={"standing": standing, "watched": watched})
                created += len(batch)

        updated = 0
        for (standing, watched), contact_ids in contact_write_groups(plan["update"]).items():
            for batch in chunked(contact_ids, 100):
                await client.put(f"/characters/{target_character.character_id}/contacts/", batch, params={"standing": standing, "watched": watched})
                updated += len(batch)

        total_created += created
        total_updated += updated
        targets.append(
            {
                "token_id": target_token.id,
                "character_id": target_character.character_id,
                "character_name": target_character.name,
                "created": created,
                "updated": updated,
                "skipped": len(plan["skip"]),
            }
        )

    owner = ensure_owner(db, OwnerKind.CHARACTER, source_character.name, character_id=source_character.id)
    job = EsiSyncJob(token_id=source_token.id, ownership_entity_id=owner.id, sync_type="character_contact_sync", status=SyncStatus.SUCCESS, started_at=datetime.now(timezone.utc), finished_at=datetime.now(timezone.utc))
    job.message = f"Copied contacts from {source_character.name}: created {total_created}, updated {total_updated}."
    db.add(job)
    db.commit()
    return {
        "status": "synced",
        "source_character_name": source_character.name,
        "created": total_created,
        "updated": total_updated,
        "targets": targets,
        "job_id": job.id,
    }
@router.get("/config")
def esi_config() -> dict[str, Any]:
    settings = get_settings()
    return {
        "client_id_configured": bool(settings.eve_sso_client_id),
        "client_secret_configured": bool(settings.eve_sso_client_secret),
        "token_encryption_key_configured": bool(settings.token_encryption_key),
        "callback_url": settings.eve_sso_callback_url,
        "required_scopes": CORE_AUTH_SCOPES,
        "available_scopes": PUBLIC_SCOPES,
    }

def build_auth_url(scopes: list[str], current_user: User, mode: str = "core") -> dict[str, Any]:
    settings = get_settings()
    missing = []
    if not settings.eve_sso_client_id:
        missing.append("EVE_SSO_CLIENT_ID")
    if not settings.eve_sso_client_secret:
        missing.append("EVE_SSO_CLIENT_SECRET")
    if not settings.token_encryption_key:
        missing.append("TOKEN_ENCRYPTION_KEY")
    if missing:
        return {
            "ready": False,
            "message": f"Set {', '.join(missing)} before starting EVE SSO.",
            "missing": missing,
            "required_scopes": scopes,
        }
    state = create_sso_state(current_user.id, mode)
    query = urllib.parse.urlencode(
        {
            "response_type": "code",
            "redirect_uri": settings.eve_sso_callback_url,
            "client_id": settings.eve_sso_client_id,
            "scope": " ".join(scopes),
            "state": state,
        }
    )
    return {"ready": True, "state": state, "url": f"https://login.eveonline.com/v2/oauth/authorize/?{query}", "required_scopes": scopes}


@router.get("/auth-url")
def auth_url(scope_group: str = Query("core", max_length=32), current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    group = scope_group.strip().lower().replace("-", "_")
    return build_auth_url(auth_scopes_for_group(group), current_user, group)


@router.get("/auth-url/standing-sync")
@router.get("/auth-url/contact-sync")
def contact_sync_auth_url(current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    return build_auth_url(standing_sync_scopes(), current_user, "standing_sync")


@router.get("/auth/diagnostics")
def auth_diagnostics() -> dict[str, Any]:
    settings = get_settings()
    return {
        "client_id_configured": bool(settings.eve_sso_client_id),
        "client_id_length": len(settings.eve_sso_client_id),
        "client_secret_configured": bool(settings.eve_sso_client_secret),
        "client_secret_length": len(settings.eve_sso_client_secret),
        "callback_url": settings.eve_sso_callback_url,
        "token_encryption_key_configured": bool(settings.token_encryption_key),
        "token_endpoint": "https://login.eveonline.com/v2/oauth/token",
    }

@router.get("/auth/callback")
async def auth_callback(code: str | None = None, state: str | None = None, db: Session = Depends(get_db)) -> dict[str, Any]:
    if not code:
        raise HTTPException(status_code=400, detail="Missing SSO authorization code")
    settings = get_settings()
    if not settings.eve_sso_client_id or not settings.eve_sso_client_secret or not settings.token_encryption_key:
        raise HTTPException(status_code=400, detail="EVE SSO client ID, secret, and token encryption key must be configured")
    state_payload = decode_sso_state_payload(state)
    if state_payload is None:
        raise HTTPException(status_code=400, detail="EVE SSO state did not match an active Quartermaster session. Start SSO from inside the app after signing in.")
    try:
        state_user_id = int(state_payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="EVE SSO state did not contain a valid Quartermaster account") from exc
    state_mode = str(state_payload.get("mode") or "core").strip().lower()

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
        response = await client.post(
            "https://login.eveonline.com/v2/oauth/token",
            auth=httpx.BasicAuth(settings.eve_sso_client_id, settings.eve_sso_client_secret),
            data={"grant_type": "authorization_code", "code": code},
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "eve-quartermaster/0.1 local development",
            },
        )
    if response.status_code >= 400:
        content_type = response.headers.get("content-type", "")
        location = response.headers.get("location")
        if "application/json" in content_type:
            detail = response.json()
        else:
            detail = response.text[:1000]
        raise HTTPException(
            status_code=response.status_code,
            detail={
                "message": "EVE SSO token exchange failed",
                "status_code": response.status_code,
                "content_type": content_type,
                "location": location,
                "callback_url_used": settings.eve_sso_callback_url,
                "client_id_length": len(settings.eve_sso_client_id),
                "client_secret_length": len(settings.eve_sso_client_secret),
                "eve_response": detail,
            },
        )

    token_payload = response.json()
    access_token = token_payload["access_token"]
    refresh_token = token_payload.get("refresh_token")
    try:
        claims = await validate_eve_access_token(access_token)
    except HTTPException as exc:
        if state_mode in {"recruitment", "recruiting", "applicant"}:
            error_query = urllib.parse.urlencode({"esi_error": str(exc.detail), "esi_mode": state_mode})
            return RedirectResponse(url=f"{settings.frontend_url}/?{error_query}#recruiting", status_code=303)
        raise
    subject = claims.get("sub", "")
    try:
        character_eve_id = int(subject.split(":")[-1])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse character ID from SSO subject {subject}") from exc

    character_payload = await EsiClient(access_token=access_token).get(f"/characters/{character_eve_id}/")
    character = db.scalar(select(EveCharacter).where(EveCharacter.character_id == character_eve_id))
    if character is None:
        character = EveCharacter(character_id=character_eve_id, name=character_payload["name"])
        db.add(character)
    character.name = character_payload["name"]
    # Corp asset sync depends on knowing which linked character belongs to which corporation.
    await apply_character_affiliation(EsiClient(access_token=access_token), db, character, character_payload)  # auth_callback_affiliation_marker

    user = db.get(User, state_user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="The Quartermaster account that started EVE SSO no longer exists")
    character.owner_user_id = user.id
    db.flush()
    owner = ensure_owner(db, OwnerKind.CHARACTER, character.name, character_id=character.id)

    link_status = "linked"
    added_scopes: list[str] = []
    removed_scopes: list[str] = []

    if refresh_token:
        encrypted_refresh = encrypt_secret(refresh_token, settings.token_encryption_key)
        scope_value = token_payload.get("scope") or claims.get("scp", [])
        scopes = " ".join(scope_value) if isinstance(scope_value, list) else str(scope_value)
        expires_in = int(token_payload.get("expires_in", 1200))
        token = db.scalar(select(EsiToken).where(EsiToken.character_id == character.id, EsiToken.revoked_at.is_(None)))
        previous_scopes = token_scopes(token) if token else set()
        link_status = "updated" if token else "linked"
        if token is None:
            token = EsiToken(user_id=user.id, character_id=character.id, scopes=scopes, encrypted_refresh_token=encrypted_refresh)
            db.add(token)
        token.user_id = user.id
        token.scopes = scopes
        token.encrypted_refresh_token = encrypted_refresh
        token.access_token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        new_scopes = {scope.strip() for scope in scopes.split() if scope.strip()}
        added_scopes = sorted(new_scopes - previous_scopes)
        removed_scopes = sorted(previous_scopes - new_scopes)

        if state_mode in {"recruitment", "recruiting", "applicant"}:
            if user.role != "applicant":
                raise HTTPException(status_code=403, detail="Recruitment SSO is only available to applicant accounts")
            application = applicant_application(db, user, create=True)
            assert application is not None
            linked = db.scalar(
                select(RecruitmentLinkedCharacter).where(
                    RecruitmentLinkedCharacter.application_id == application.id,
                    RecruitmentLinkedCharacter.character_id == character.id,
                )
            )
            if linked is None:
                has_main = db.scalar(
                    select(RecruitmentLinkedCharacter.id).where(
                        RecruitmentLinkedCharacter.application_id == application.id,
                        RecruitmentLinkedCharacter.is_main.is_(True),
                    )
                ) is not None
                linked = RecruitmentLinkedCharacter(
                    application_id=application.id,
                    character_id=character.id,
                    is_main=not has_main,
                )
                db.add(linked)
                db.flush()
            await sync_recruitment_character(db, linked, token)
            recruitment_audit(
                db,
                user,
                "character_linked",
                f"Applicant linked {character.name} through EVE SSO",
                application.id,
                {"character_id": character_eve_id, "scopes": sorted(new_scopes)},
            )

    db.commit()
    query = urllib.parse.urlencode(
        {
            "esi_status": link_status,
            "character_name": character.name,
            "character_id": character_eve_id,
            "owner_id": owner.id,
            "refresh_token_stored": str(bool(refresh_token)).lower(),
            "added_scopes": ",".join(added_scopes),
            "removed_scopes": ",".join(removed_scopes),
            "esi_mode": state_mode,
        }
    )
    if state_mode in {"recruitment", "recruiting", "applicant"}:
        destination = "recruiting"
    elif state_mode in {"planet", "planets", "planetary", "planetary_industry", "pi"}:
        destination = "planetary_industry"
    else:
        destination = "esi"
    return RedirectResponse(url=f"{settings.frontend_url}/?{query}#{destination}", status_code=303)
