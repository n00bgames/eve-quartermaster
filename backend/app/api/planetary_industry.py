from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import get_current_user
from app.api.characters import can_sync_character_data, visible_characters
from app.api.esi import (
    apply_type_metadata,
    apply_type_names,
    get_linked_token,
    refresh_access_token,
    require_scope,
    token_scopes,
)
from app.db.session import SessionLocal, get_db
from app.models import (
    EsiSyncJob,
    EsiToken,
    EveCharacter,
    EvePlanetSchematic,
    EvePlanetSchematicInput,
    EveSystem,
    EveType,
    PlanetaryColony,
    PlanetaryLink,
    PlanetaryPin,
    PlanetaryRoute,
    User,
)
from app.models.enums import SyncStatus
from app.services.esi_client import EsiClient
from app.services.permissions import can_view_section
from app.services.planetary_analytics import record_planetary_production_snapshot
from app.services.planetary_industry import (
    DEFAULT_DECAY_FACTOR,
    DEFAULT_NOISE_FACTOR,
    extractor_dogma_factors,
    extractor_program_projection,
)
from app.services.planetary_simulation import (
    SimulationPin,
    SimulationRoute,
    SimulationSchematic,
    known_pin_capacity_m3,
    simulate_colony,
)

router = APIRouter(prefix="/planetary-industry", tags=["planetary-industry"])

PLANET_SCOPE = "esi-planets.manage_planets.v1"
PLANETARY_SYNC_JOBS: dict[str, dict[str, Any]] = {}


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def iso(value: Any) -> str | None:
    return value.isoformat() if value else None


def require_planetary_view(user: User, db: Session) -> None:
    if not can_view_section(user, "planetary_industry", db):
        raise HTTPException(status_code=403, detail="Planetary Industry permission is required")


def type_map(db: Session, type_ids: set[int]) -> dict[int, EveType]:
    if not type_ids:
        return {}
    return {
        row.type_id: row
        for row in db.scalars(select(EveType).where(EveType.type_id.in_(type_ids))).all()
    }


def serialize_schematic(schematic: EvePlanetSchematic) -> dict[str, Any]:
    return {
        "id": schematic.schematic_id,
        "name": schematic.name,
        "cycle_time": schematic.cycle_time,
        "output": {
            "type_id": schematic.output_type_id,
            "name": schematic.output_type.name,
            "quantity": schematic.output_quantity,
            "volume": float(schematic.output_type.volume or 0),
        },
        "inputs": [
            {
                "type_id": item.type_id,
                "name": item.item_type.name,
                "quantity": item.quantity,
                "volume": float(item.item_type.volume or 0),
            }
            for item in sorted(schematic.inputs, key=lambda row: row.item_type.name)
        ],
    }


def pin_status(pin: PlanetaryPin, now: datetime) -> str:
    if pin.expiry_time is None:
        return "online"
    expiry = pin.expiry_time
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if expiry <= now:
        return "expired"
    if (expiry - now).total_seconds() <= 24 * 60 * 60:
        return "expiring"
    return "active"


def serialize_colony(db: Session, colony: PlanetaryColony) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    type_ids = {
        pin.type_id for pin in colony.pins
    } | {
        pin.extractor_product_type_id
        for pin in colony.pins
        if pin.extractor_product_type_id
    } | {
        route.content_type_id for route in colony.routes
    }
    for pin in colony.pins:
        type_ids.update(int(item["type_id"]) for item in pin.contents_json if item.get("type_id"))

    extractor_type_ids = {
        pin.type_id for pin in colony.pins if pin.extractor_cycle_time is not None
    }
    dogma_factors = extractor_dogma_factors(db, extractor_type_ids)
    schematic_ids = {pin.schematic_id for pin in colony.pins if pin.schematic_id is not None}
    schematics = {
        row.schematic_id: row
        for row in db.scalars(
            select(EvePlanetSchematic)
            .where(EvePlanetSchematic.schematic_id.in_(schematic_ids))
            .options(
                selectinload(EvePlanetSchematic.output_type),
                selectinload(EvePlanetSchematic.inputs).selectinload(EvePlanetSchematicInput.item_type),
            )
        ).all()
    } if schematic_ids else {}
    for schematic in schematics.values():
        type_ids.add(schematic.output_type_id)
        type_ids.update(item.type_id for item in schematic.inputs)
    types = type_map(db, type_ids)

    simulation_pins: list[SimulationPin] = []
    for pin in colony.pins:
        schematic = schematics.get(pin.schematic_id)
        simulation_schematic = SimulationSchematic(
            cycle_time=int(schematic.cycle_time),
            inputs={item.type_id: int(item.quantity) for item in schematic.inputs},
            output_type_id=schematic.output_type_id,
            output_quantity=int(schematic.output_quantity),
        ) if schematic else None
        type_name = pin.pin_type.name if pin.pin_type else f"Type {pin.type_id}"
        capacity = known_pin_capacity_m3(type_name)
        kind = "extractor" if pin.extractor_cycle_time is not None else "factory" if schematic else "storage" if capacity is not None else "infrastructure"
        decay_factor, noise_factor, _ = dogma_factors.get(
            pin.type_id,
            (DEFAULT_DECAY_FACTOR, DEFAULT_NOISE_FACTOR, "documented_default"),
        )
        simulation_pins.append(
            SimulationPin(
                pin_id=pin.pin_id,
                kind=kind,
                contents={
                    int(item["type_id"]): int(item.get("amount") or 0)
                    for item in pin.contents_json
                    if item.get("type_id")
                },
                capacity_m3=capacity,
                schematic=simulation_schematic,
                last_cycle_start=pin.last_cycle_start,
                install_time=pin.install_time,
                expiry_time=pin.expiry_time,
                extractor_cycle_time=pin.extractor_cycle_time,
                extractor_product_type_id=pin.extractor_product_type_id,
                extractor_quantity_per_cycle=pin.extractor_qty_per_cycle,
                extractor_decay_factor=decay_factor,
                extractor_noise_factor=noise_factor,
            )
        )
    simulation = simulate_colony(
        checkpoint_at=colony.esi_last_update,
        projected_at=now,
        pins=simulation_pins,
        routes=[
            SimulationRoute(
                source_pin_id=route.source_pin_id,
                destination_pin_id=route.destination_pin_id,
                content_type_id=route.content_type_id,
                quantity=int(route.quantity or 0),
            )
            for route in colony.routes
        ],
        type_volumes={type_id: float(item.volume or 0) for type_id, item in types.items()},
    )

    def serialize_contents(contents: dict[int, int]) -> list[dict[str, Any]]:
        return [
            {
                "type_id": type_id,
                "name": types[type_id].name if type_id in types else f"Type {type_id}",
                "amount": amount,
                "volume": float(types[type_id].volume or 0) if type_id in types else 0,
            }
            for type_id, amount in sorted(
                contents.items(),
                key=lambda item: (types[item[0]].name if item[0] in types else f"Type {item[0]}").casefold(),
            )
            if amount > 0
        ]

    inbound_pins = {route.destination_pin_id for route in colony.routes}
    pins: list[dict[str, Any]] = []
    expired_extractors = 0
    expiring_extractors = 0
    total_daily_output = 0.0

    for pin in sorted(colony.pins, key=lambda row: (row.pin_type.name if row.pin_type else "", row.pin_id)):
        observed_status = pin_status(pin, now)
        is_extractor = pin.extractor_cycle_time is not None
        is_factory = pin.schematic_id is not None
        if is_extractor and observed_status == "expired":
            expired_extractors += 1
        elif is_extractor and observed_status == "expiring":
            expiring_extractors += 1
        decay_factor, noise_factor, projection_source = dogma_factors.get(
            pin.type_id,
            (DEFAULT_DECAY_FACTOR, DEFAULT_NOISE_FACTOR, "documented_default"),
        )
        extractor_projection = extractor_program_projection(
            install_time=pin.install_time,
            expiry_time=pin.expiry_time,
            cycle_time=pin.extractor_cycle_time,
            quantity_per_cycle=pin.extractor_qty_per_cycle,
            decay_factor=decay_factor,
            noise_factor=noise_factor,
            now=now,
        )
        if pin.extractor_cycle_time and pin.extractor_qty_per_cycle and observed_status != "expired":
            total_daily_output += float(extractor_projection["average_daily_output"])

        observed_map = {
            int(item["type_id"]): int(item.get("amount") or 0)
            for item in pin.contents_json
            if item.get("type_id")
        }
        pin_projection = simulation["pins"].get(pin.pin_id, {})
        projected_map = pin_projection.get("contents", observed_map)
        observed_contents = serialize_contents(observed_map)
        projected_contents = serialize_contents(projected_map)
        observed_volume = sum(item["amount"] * item["volume"] for item in observed_contents)
        projected_volume = sum(item["amount"] * item["volume"] for item in projected_contents)
        projected_status = pin_projection.get("status", observed_status)
        schematic = schematics.get(pin.schematic_id)
        pins.append(
            {
                "pin_id": pin.pin_id,
                "type_id": pin.type_id,
                "type_name": pin.pin_type.name if pin.pin_type else f"Type {pin.type_id}",
                "latitude": pin.latitude,
                "longitude": pin.longitude,
                "install_time": iso(pin.install_time),
                "expiry_time": iso(pin.expiry_time),
                "last_cycle_start": iso(pin.last_cycle_start),
                "status": observed_status,
                "projected_status": projected_status,
                "content_source": "projected" if simulation["is_projection"] else "observed",
                "schematic_id": pin.schematic_id,
                "schematic": serialize_schematic(schematic) if schematic else None,
                "is_factory": is_factory,
                "is_extractor": is_extractor,
                "has_inbound_route": pin.pin_id in inbound_pins,
                "contents": projected_contents,
                "observed_contents": observed_contents,
                "stored_volume": projected_volume,
                "observed_stored_volume": observed_volume,
                "projected_produced": serialize_contents(pin_projection.get("produced", {})),
                "projected_blocked": serialize_contents(pin_projection.get("blocked", {})),
                "extractor": {
                    "cycle_time": pin.extractor_cycle_time,
                    "head_radius": pin.extractor_head_radius,
                    "head_count": len(pin.extractor_heads_json),
                    "product_type_id": pin.extractor_product_type_id,
                    "product_name": types.get(pin.extractor_product_type_id).name if pin.extractor_product_type_id and types.get(pin.extractor_product_type_id) else None,
                    "qty_per_cycle": pin.extractor_qty_per_cycle,
                    "cycle_count": extractor_projection["cycle_count"],
                    "projected_program_output": extractor_projection["program_output"],
                    "projected_daily_output": extractor_projection["average_daily_output"],
                    "projected_remaining_output": extractor_projection["remaining_output"],
                    "projection_source": projection_source,
                } if is_extractor else None,
            }
        )

    starved_factories = sum(
        1 for pin in pins if pin["is_factory"] and pin["projected_status"] in {"starved", "blocked"}
    )
    checkpoint = simulation["checkpoint_at"]
    checkpoint_age_minutes = max(0, int((now - checkpoint).total_seconds() // 60)) if checkpoint else None
    projection_warning = None
    if checkpoint is None:
        projection_warning = "No ESI checkpoint is available; showing observed inventory only."
    elif simulation["truncated"]:
        projection_warning = "Projection stopped at its safety limit; sync the colony for a newer checkpoint."
    elif checkpoint_age_minutes is not None and checkpoint_age_minutes >= 24 * 60:
        projection_warning = "This projection begins from an ESI checkpoint more than 24 hours old; manual transfers may not be reflected."

    return {
        "id": colony.id,
        "character_id": colony.character_id,
        "character_eve_id": colony.character.character_id,
        "character_name": colony.character.name,
        "character_portrait_url": colony.character.portrait_url,
        "planet_id": colony.planet_id,
        "planet_name": colony.planet_name,
        "planet_type": colony.planet_type,
        "solar_system_id": colony.solar_system_id,
        "solar_system_name": colony.system.name if colony.system else None,
        "security_status": colony.system.security_status if colony.system else None,
        "upgrade_level": colony.upgrade_level,
        "num_pins": colony.num_pins,
        "esi_last_update": iso(colony.esi_last_update),
        "last_synced_at": iso(colony.last_synced_at),
        "link_count": len(colony.links),
        "route_count": len(colony.routes),
        "projection": {
            "checkpoint_at": iso(simulation["checkpoint_at"]),
            "projected_at": iso(simulation["projected_at"]),
            "is_projection": simulation["is_projection"],
            "events_processed": simulation["events_processed"],
            "truncated": simulation["truncated"],
            "checkpoint_age_minutes": checkpoint_age_minutes,
            "warning": projection_warning,
        },
        "summary": {
            "extractors": sum(1 for pin in colony.pins if pin.extractor_cycle_time is not None),
            "expired_extractors": expired_extractors,
            "expiring_extractors": expiring_extractors,
            "factories": sum(1 for pin in colony.pins if pin.schematic_id is not None),
            "starved_factories": starved_factories,
            "stored_volume": sum(pin["stored_volume"] for pin in pins),
            "observed_stored_volume": sum(pin["observed_stored_volume"] for pin in pins),
            "projected_daily_output": total_daily_output,
        },
        "pins": pins,
        "routes": [
            {
                "route_id": route.route_id,
                "source_pin_id": route.source_pin_id,
                "destination_pin_id": route.destination_pin_id,
                "content_type_id": route.content_type_id,
                "content_name": types.get(route.content_type_id).name if types.get(route.content_type_id) else f"Type {route.content_type_id}",
                "quantity": route.quantity,
                "waypoints": route.waypoints_json,
            }
            for route in colony.routes
        ],
    }

def sync_token_payload(db: Session, user: User, character_ids: set[int]) -> list[dict[str, Any]]:
    rows = db.execute(
        select(EsiToken, EveCharacter)
        .join(EveCharacter, EveCharacter.id == EsiToken.character_id)
        .where(EsiToken.revoked_at.is_(None), EsiToken.character_id.in_(character_ids) if character_ids else False)
        .order_by(EveCharacter.name, EsiToken.created_at.desc())
    ).all()
    result: list[dict[str, Any]] = []
    seen: set[int] = set()
    for token, character in rows:
        if character.id in seen:
            continue
        seen.add(character.id)
        result.append(
            {
                "token_id": token.id,
                "character_id": character.id,
                "character_eve_id": character.character_id,
                "character_name": character.name,
                "has_scope": PLANET_SCOPE in token_scopes(token),
                "can_sync": can_sync_character_data(user, character, token, db) and not character.sync_opt_out,
            }
        )
    return result


@router.get("")
def list_planetary_industry(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_planetary_view(current_user, db)
    characters = visible_characters(current_user, db)
    character_ids = {row.id for row in characters}
    colonies = db.scalars(
        select(PlanetaryColony)
        .where(PlanetaryColony.character_id.in_(character_ids) if character_ids else False)
        .options(
            selectinload(PlanetaryColony.character),
            selectinload(PlanetaryColony.system),
            selectinload(PlanetaryColony.pins).selectinload(PlanetaryPin.pin_type),
            selectinload(PlanetaryColony.links),
            selectinload(PlanetaryColony.routes),
        )
        .order_by(PlanetaryColony.planet_name)
    ).all()
    payload = [serialize_colony(db, colony) for colony in colonies]
    schematic_catalog = db.scalars(
        select(EvePlanetSchematic)
        .options(
            selectinload(EvePlanetSchematic.output_type),
            selectinload(EvePlanetSchematic.inputs).selectinload(EvePlanetSchematicInput.item_type),
        )
        .order_by(EvePlanetSchematic.name, EvePlanetSchematic.schematic_id)
    ).all()
    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "characters": [
            {"id": row.id, "name": row.name, "portrait_url": row.portrait_url}
            for row in characters
        ],
        "sync_tokens": sync_token_payload(db, current_user, character_ids),
        "schematics": [serialize_schematic(row) for row in schematic_catalog],
        "colonies": payload,
        "summary": {
            "colonies": len(payload),
            "characters": len({row["character_id"] for row in payload}),
            "expired_extractors": sum(row["summary"]["expired_extractors"] for row in payload),
            "expiring_extractors": sum(row["summary"]["expiring_extractors"] for row in payload),
            "starved_factories": sum(row["summary"]["starved_factories"] for row in payload),
            "stored_volume": sum(row["summary"]["stored_volume"] for row in payload),
        },
    }


async def sync_planetary_industry_for_token(
    token_id: int,
    current_user: User,
    db: Session,
    *,
    allow_opt_out_override: bool = True,
) -> dict[str, Any]:
    token, character = get_linked_token(db, token_id)
    if not can_sync_character_data(current_user, character, token, db):
        raise HTTPException(status_code=403, detail="You cannot sync PI for this character")
    if character.sync_opt_out and not allow_opt_out_override:
        return {"status": "skipped", "character_name": character.name, "reason": "Character opted out"}
    require_scope(token, PLANET_SCOPE, f"Reading planetary colonies for {character.name}")

    job = EsiSyncJob(
        token_id=token.id,
        sync_type="character_planetary_industry",
        status=SyncStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.flush()
    access_token = await refresh_access_token(token)
    client = EsiClient(access_token=access_token)
    try:
        summaries = await client.get(f"/characters/{character.character_id}/planets/") or []
        layouts: list[tuple[dict[str, Any], dict[str, Any], str]] = []
        type_ids: set[int] = set()
        for summary in summaries:
            planet_id = int(summary["planet_id"])
            detail = await client.get(f"/characters/{character.character_id}/planets/{planet_id}/") or {}
            try:
                planet = await EsiClient().get(f"/universe/planets/{planet_id}/")
                planet_name = str(planet.get("name") or f"Planet {planet_id}")
            except Exception:
                planet_name = f"Planet {planet_id}"
            layouts.append((summary, detail, planet_name))
            for pin in detail.get("pins", []) or []:
                type_ids.add(int(pin["type_id"]))
                type_ids.update(int(item["type_id"]) for item in pin.get("contents", []) or [])
                extractor = pin.get("extractor_details") or {}
                if extractor.get("product_type_id"):
                    type_ids.add(int(extractor["product_type_id"]))
            type_ids.update(int(route["content_type_id"]) for route in detail.get("routes", []) or [])

        await apply_type_names(client, db, type_ids)
        await apply_type_metadata(client, db, type_ids, max_fetch=150)
        db.execute(delete(PlanetaryColony).where(PlanetaryColony.character_id == character.id))
        now = datetime.now(timezone.utc)
        pin_count = 0
        route_count = 0
        for summary, detail, planet_name in layouts:
            colony = PlanetaryColony(
                character_id=character.id,
                planet_id=int(summary["planet_id"]),
                planet_name=planet_name,
                planet_type=summary.get("planet_type"),
                solar_system_id=summary.get("solar_system_id"),
                upgrade_level=int(summary.get("upgrade_level") or 0),
                num_pins=int(summary.get("num_pins") or len(detail.get("pins", []) or [])),
                esi_last_update=parse_datetime(summary.get("last_update")),
                last_synced_at=now,
            )
            db.add(colony)
            db.flush()
            for pin in detail.get("pins", []) or []:
                extractor = pin.get("extractor_details") or {}
                factory = pin.get("factory_details") or {}
                db.add(
                    PlanetaryPin(
                        colony_id=colony.id,
                        pin_id=int(pin["pin_id"]),
                        type_id=int(pin["type_id"]),
                        latitude=pin.get("latitude"),
                        longitude=pin.get("longitude"),
                        install_time=parse_datetime(pin.get("install_time")),
                        expiry_time=parse_datetime(pin.get("expiry_time")),
                        last_cycle_start=parse_datetime(pin.get("last_cycle_start")),
                        schematic_id=factory.get("schematic_id") or pin.get("schematic_id"),
                        extractor_cycle_time=extractor.get("cycle_time"),
                        extractor_head_radius=extractor.get("head_radius"),
                        extractor_product_type_id=extractor.get("product_type_id"),
                        extractor_qty_per_cycle=extractor.get("qty_per_cycle"),
                        contents_json=pin.get("contents", []) or [],
                        extractor_heads_json=extractor.get("heads", []) or [],
                    )
                )
                pin_count += 1
            for link in detail.get("links", []) or []:
                db.add(
                    PlanetaryLink(
                        colony_id=colony.id,
                        source_pin_id=int(link["source_pin_id"]),
                        destination_pin_id=int(link["destination_pin_id"]),
                        link_level=int(link.get("link_level") or 0),
                    )
                )
            for route in detail.get("routes", []) or []:
                db.add(
                    PlanetaryRoute(
                        colony_id=colony.id,
                        route_id=int(route["route_id"]),
                        source_pin_id=int(route["source_pin_id"]),
                        destination_pin_id=int(route["destination_pin_id"]),
                        content_type_id=int(route["content_type_id"]),
                        quantity=float(route.get("quantity") or 0),
                        waypoints_json=route.get("waypoints", []) or [],
                    )
                )
                route_count += 1
        db.flush()
        snapshot_count = record_planetary_production_snapshot(db, character.id, now)
        character.last_synced_at = now
        job.status = SyncStatus.SUCCESS
        job.finished_at = now
        job.message = f"Synced {len(layouts)} colonies, {pin_count} pins, {route_count} routes, and {snapshot_count} production observations for {character.name}."
        db.commit()
        return {
            "status": "synced",
            "character_id": character.id,
            "character_name": character.name,
            "colony_count": len(layouts),
            "pin_count": pin_count,
            "production_observations": snapshot_count,
            "job_id": job.id,
        }
    except Exception as exc:
        db.rollback()
        db.add(
            EsiSyncJob(
                token_id=token.id,
                sync_type="character_planetary_industry",
                status=SyncStatus.FAILED,
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
                message=str(exc),
            )
        )
        db.commit()
        raise


def planetary_sync_job_payload(job: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in job.items() if key != "user_id"}


async def run_planetary_sync_job(job_id: str, token_id: int, user_id: int) -> None:
    job = PLANETARY_SYNC_JOBS[job_id]
    job["status"] = "running"
    job["current_sync_kind"] = "planets"
    try:
        with SessionLocal() as db:
            user = db.get(User, user_id)
            if user is None:
                raise RuntimeError("The user that started this PI sync no longer exists.")
            token, character = get_linked_token(db, token_id)
            job["current_character_name"] = character.name
            result = await sync_planetary_industry_for_token(token.id, user, db)
            job["success_count"] = 1
            job["results"] = [result]
    except Exception as exc:
        detail = getattr(exc, "detail", None) or str(exc)
        job["failed_count"] = 1
        job["errors"] = [str(detail)]
    finally:
        job["processed_count"] = 1
        job["current_character_name"] = None
        job["current_sync_kind"] = None
        job["status"] = "complete" if job["failed_count"] == 0 else "failed"
        job["completed_at"] = datetime.now(timezone.utc).isoformat()


@router.post("/sync/{token_id:int}")
async def sync_planetary_industry(
    token_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_planetary_view(current_user, db)
    token, character = get_linked_token(db, token_id)
    if not can_sync_character_data(current_user, character, token, db):
        raise HTTPException(status_code=403, detail="You cannot sync PI for this character")
    require_scope(token, PLANET_SCOPE, f"Reading planetary colonies for {character.name}")
    job_id = uuid.uuid4().hex
    PLANETARY_SYNC_JOBS[job_id] = {
        "job_id": job_id,
        "user_id": current_user.id,
        "status": "queued",
        "total_count": 1,
        "processed_count": 0,
        "success_count": 0,
        "failed_count": 0,
        "skipped_count": 0,
        "current_character_name": character.name,
        "current_sync_kind": "planets",
        "results": [],
        "errors": [],
        "completed_at": None,
    }
    asyncio.create_task(run_planetary_sync_job(job_id, token_id, current_user.id))
    return planetary_sync_job_payload(PLANETARY_SYNC_JOBS[job_id])


@router.get("/sync/jobs/{job_id}")
def get_planetary_sync_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    job = PLANETARY_SYNC_JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="PI sync job was not found. It may have been cleared by a backend restart.")
    if job["user_id"] != current_user.id and current_user.role not in {"host", "admin"}:
        raise HTTPException(status_code=403, detail="You cannot view this PI sync job")
    return planetary_sync_job_payload(job)
