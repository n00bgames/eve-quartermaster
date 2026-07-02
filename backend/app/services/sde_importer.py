from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any
import zipfile

import yaml
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import (
    EveCategory,
    EveConstellation,
    EveGroup,
    EveRegion,
    EveStargate,
    EveStation,
    EveSystem,
    EveType,
    IndustryActivity,
    IndustryActivityInput,
)
from app.models.enums import ActivityKind


SDE_FILES = {
    "categories": ("categories.yaml", "categoryIDs.yaml"),
    "groups": ("groups.yaml", "groupIDs.yaml"),
    "types": ("types.yaml", "typeIDs.yaml"),
    "blueprints": ("blueprints.yaml",),
    "regions": ("mapRegions.yaml",),
    "constellations": ("mapConstellations.yaml",),
    "systems": ("mapSolarSystems.yaml",),
    "stargates": ("mapStargates.yaml",),
    "stations": ("npcStations.yaml",),
    "station_operations": ("stationOperations.yaml",),
    "station_names": ("invNames.yaml", "itemNames.yaml", "bsd/invNames.yaml", "bsd/itemNames.yaml"),
    "station_table": ("staStations.yaml", "bsd/staStations.yaml"),
}

ACTIVITY_MAP = {
    "manufacturing": ActivityKind.MANUFACTURING,
    "copying": ActivityKind.COPYING,
    "invention": ActivityKind.INVENTION,
    "reaction": ActivityKind.REACTION,
    "research_material": ActivityKind.RESEARCH_MATERIAL,
    "research_time": ActivityKind.RESEARCH_TIME,
    "researching_material_efficiency": ActivityKind.RESEARCH_MATERIAL,
    "researching_time_efficiency": ActivityKind.RESEARCH_TIME,
}


@dataclass
class SdeImportStats:
    source_path: str
    categories: int = 0
    groups: int = 0
    types: int = 0
    regions: int = 0
    constellations: int = 0
    systems: int = 0
    stargates: int = 0
    stations: int = 0
    blueprint_activities: int = 0
    activity_inputs: int = 0
    skipped_activities: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SdeSource:
    def __init__(self, source_path: str) -> None:
        self.source_path = source_path
        self.path = Path(source_path)
        self.archive: zipfile.ZipFile | None = None
        if self.path.is_file() and self.path.suffix.lower() == ".zip":
            self.archive = zipfile.ZipFile(self.path)
        elif not self.path.exists():
            raise FileNotFoundError(f"SDE source path was not found: {source_path}")

    def close(self) -> None:
        if self.archive is not None:
            self.archive.close()

    def load_yaml(self, logical_name: str) -> dict[Any, Any]:
        filenames = SDE_FILES[logical_name]
        if self.archive is not None:
            member = self._find_archive_member(filenames)
            if member is None:
                raise FileNotFoundError(f"None of {', '.join(filenames)} were found in {self.source_path}")
            with self.archive.open(member) as handle:
                return yaml.safe_load(handle) or {}

        candidates: list[Path] = []
        for filename in filenames:
            candidates.extend([self.path / "fsd" / filename, self.path / filename])
        for candidate in candidates:
            if candidate.exists():
                with candidate.open("r", encoding="utf-8") as handle:
                    return yaml.safe_load(handle) or {}
        raise FileNotFoundError(f"None of {', '.join(filenames)} were found under {self.source_path}")

    def _find_archive_member(self, filenames: tuple[str, ...]) -> str | None:
        expected = {filename for filename in filenames} | {f"fsd/{filename}" for filename in filenames}
        fsd_suffixes = tuple(f"/fsd/{filename}" for filename in filenames)
        root_suffixes = tuple(f"/{filename}" for filename in filenames)
        for member in self.archive.namelist() if self.archive is not None else []:
            normalized = PurePosixPath(member).as_posix().lstrip("/")
            if normalized in expected or normalized.endswith(fsd_suffixes) or normalized.endswith(root_suffixes):
                return member
        return None


def localized_text(value: Any, fallback: str) -> str:
    if isinstance(value, dict):
        for key in ("en", "en-us", "EN"):
            if value.get(key):
                return str(value[key])
        for item in value.values():
            if item:
                return str(item)
    if value not in (None, ""):
        return str(value)
    return fallback


def optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def position_value(payload: dict[str, Any], axis: str) -> float | None:
    position = payload.get("position") or {}
    if not isinstance(position, dict):
        return None
    return optional_float(position.get(axis))


def ensure_region(db: Session, region_id: int, name: str | None = None) -> EveRegion:
    region = db.get(EveRegion, region_id)
    if region is None:
        region = EveRegion(region_id=region_id, name=name or f"Region {region_id}")
        db.add(region)
    elif name:
        region.name = name
    return region


def ensure_constellation(db: Session, constellation_id: int, region_id: int | None = None, name: str | None = None) -> EveConstellation:
    if region_id is not None:
        ensure_region(db, region_id)
    constellation = db.get(EveConstellation, constellation_id)
    if constellation is None:
        constellation = EveConstellation(constellation_id=constellation_id, name=name or f"Constellation {constellation_id}")
        db.add(constellation)
    if region_id is not None:
        constellation.region_id = region_id
    if name:
        constellation.name = name
    return constellation


def ensure_system(db: Session, system_id: int, name: str | None = None) -> EveSystem:
    system = db.get(EveSystem, system_id)
    if system is None:
        system = EveSystem(system_id=system_id, name=name or f"System {system_id}")
        db.add(system)
    elif name:
        system.name = name
    return system


def upsert_category(db: Session, category_id: int, payload: dict[str, Any]) -> EveCategory:
    category = db.get(EveCategory, category_id)
    if category is None:
        category = EveCategory(category_id=category_id, name=f"Category {category_id}")
        db.add(category)
    category.name = localized_text(payload.get("name"), f"Category {category_id}")
    category.published = bool(payload.get("published", True))
    return category


def upsert_group(db: Session, group_id: int, payload: dict[str, Any]) -> EveGroup:
    category_id = payload.get("categoryID")
    if category_id is not None and db.get(EveCategory, int(category_id)) is None:
        db.add(EveCategory(category_id=int(category_id), name=f"Category {category_id}", published=True))
    group = db.get(EveGroup, group_id)
    if group is None:
        group = EveGroup(group_id=group_id, name=f"Group {group_id}")
        db.add(group)
    group.category_id = int(category_id) if category_id is not None else None
    group.name = localized_text(payload.get("name"), f"Group {group_id}")
    group.published = bool(payload.get("published", True))
    return group


def upsert_type(db: Session, type_id: int, payload: dict[str, Any]) -> EveType:
    group_id = payload.get("groupID")
    if group_id is not None and db.get(EveGroup, int(group_id)) is None:
        db.add(EveGroup(group_id=int(group_id), name=f"Group {group_id}", published=True))
    item_type = db.get(EveType, type_id)
    if item_type is None:
        item_type = EveType(type_id=type_id, name=f"Type {type_id}")
        db.add(item_type)
    item_type.group_id = int(group_id) if group_id is not None else None
    item_type.name = localized_text(payload.get("name"), f"Type {type_id}")
    item_type.description = localized_text(payload.get("description"), "") or None
    item_type.volume = optional_float(payload.get("volume"))
    item_type.packaged_volume = optional_float(payload.get("packagedVolume"))
    item_type.market_group_id = int(payload["marketGroupID"]) if payload.get("marketGroupID") is not None else None
    item_type.published = bool(payload.get("published", True))
    return item_type


def upsert_region(db: Session, region_id: int, payload: dict[str, Any]) -> EveRegion:
    return ensure_region(db, region_id, localized_text(payload.get("name"), f"Region {region_id}"))


def upsert_constellation(db: Session, constellation_id: int, payload: dict[str, Any]) -> EveConstellation:
    region_id = int(payload["regionID"]) if payload.get("regionID") is not None else None
    return ensure_constellation(
        db,
        constellation_id,
        region_id,
        localized_text(payload.get("name"), f"Constellation {constellation_id}"),
    )


def upsert_system(db: Session, system_id: int, payload: dict[str, Any]) -> EveSystem:
    region_id = int(payload["regionID"]) if payload.get("regionID") is not None else None
    constellation_id = int(payload["constellationID"]) if payload.get("constellationID") is not None else None
    if constellation_id is not None:
        ensure_constellation(db, constellation_id, region_id)
    system = ensure_system(db, system_id, localized_text(payload.get("name"), f"System {system_id}"))
    system.constellation_id = constellation_id
    system.security_status = optional_float(payload.get("securityStatus"))
    system.security_class = str(payload.get("securityClass")) if payload.get("securityClass") is not None else None
    system.x = position_value(payload, "x")
    system.y = position_value(payload, "y")
    system.z = position_value(payload, "z")
    return system


def upsert_stargate(db: Session, stargate_id: int, payload: dict[str, Any]) -> EveStargate:
    system_id = int(payload["solarSystemID"])
    destination = payload.get("destination") or {}
    destination_system_id = int(destination["solarSystemID"]) if destination.get("solarSystemID") is not None else None
    ensure_system(db, system_id)
    if destination_system_id is not None:
        ensure_system(db, destination_system_id)
    stargate = db.get(EveStargate, stargate_id)
    if stargate is None:
        stargate = EveStargate(stargate_id=stargate_id, system_id=system_id)
        db.add(stargate)
    stargate.system_id = system_id
    stargate.destination_system_id = destination_system_id
    stargate.destination_stargate_id = int(destination["stargateID"]) if destination.get("stargateID") is not None else None
    stargate.type_id = int(payload["typeID"]) if payload.get("typeID") is not None else None
    stargate.x = position_value(payload, "x")
    stargate.y = position_value(payload, "y")
    stargate.z = position_value(payload, "z")
    return stargate


def station_operation_names(operations: dict[Any, Any]) -> dict[int, str]:
    names: dict[int, str] = {}
    for raw_id, payload in operations.items():
        if not isinstance(payload, dict):
            continue
        names[int(raw_id)] = localized_text(payload.get("operationName"), f"Operation {raw_id}")
    return names


def load_optional_yaml(source: SdeSource, logical_name: str) -> dict[Any, Any]:
    try:
        return source.load_yaml(logical_name)
    except FileNotFoundError:
        return {}


def station_name_from_payload(payload: dict[str, Any]) -> str:
    for key in ("stationName", "itemName", "name", "station_name", "item_name"):
        value = localized_text(payload.get(key), "")
        if value and optional_int(value) is None:
            return value
    return ""


def station_id_from_payload(raw_id: Any, payload: dict[str, Any]) -> int | None:
    for key in ("stationID", "stationId", "station_id", "itemID", "itemId", "item_id", "id"):
        value = optional_int(payload.get(key))
        if value is not None:
            return value
    return optional_int(raw_id)


def station_names_from_table(data: Any) -> dict[int, str]:
    names: dict[int, str] = {}
    if isinstance(data, dict):
        entries = data.items()
    elif isinstance(data, list):
        entries = enumerate(data)
    else:
        return names

    for raw_id, payload in entries:
        if isinstance(payload, dict):
            station_id = station_id_from_payload(raw_id, payload)
            name = station_name_from_payload(payload)
        else:
            station_id = optional_int(raw_id)
            name = localized_text(payload, "")
        if station_id is not None and name:
            names[station_id] = name
    return names


def load_station_names(source: SdeSource) -> dict[int, str]:
    names: dict[int, str] = {}
    for logical_name in ("station_names", "station_table"):
        names.update(station_names_from_table(load_optional_yaml(source, logical_name)))
    return names


def station_name_for(station_id: int, payload: dict[str, Any], station_names: dict[int, str]) -> str | None:
    direct_name = station_name_from_payload(payload)
    if direct_name:
        return direct_name

    for key in ("stationNameID", "nameID", "stationName", "itemID", "itemId"):
        lookup_id = optional_int(payload.get(key))
        if lookup_id is not None and station_names.get(lookup_id):
            return station_names[lookup_id]
    return station_names.get(station_id)


def upsert_station(
    db: Session,
    station_id: int,
    payload: dict[str, Any],
    operation_names: dict[int, str],
    station_names: dict[int, str],
) -> EveStation:
    system_id = int(payload["solarSystemID"])
    type_id = int(payload["typeID"]) if payload.get("typeID") is not None else None
    operation_id = int(payload["operationID"]) if payload.get("operationID") is not None else None
    ensure_system(db, system_id)
    if type_id is not None:
        ensure_placeholder_type(db, type_id)
    station = db.get(EveStation, station_id)
    if station is None:
        station = EveStation(station_id=station_id, system_id=system_id)
        db.add(station)
    station.system_id = system_id
    station.type_id = type_id
    station.operation_id = operation_id
    station.operation_name = operation_names.get(operation_id, f"Operation {operation_id}" if operation_id is not None else None)
    station.name = station_name_for(station_id, payload, station_names)
    station.owner_id = int(payload["ownerID"]) if payload.get("ownerID") is not None else None
    station.orbit_id = int(payload["orbitID"]) if payload.get("orbitID") is not None else None
    station.x = position_value(payload, "x")
    station.y = position_value(payload, "y")
    station.z = position_value(payload, "z")
    return station


def ensure_placeholder_type(db: Session, type_id: int) -> None:
    if db.get(EveType, type_id) is None:
        db.add(EveType(type_id=type_id, name=f"Type {type_id}", published=True))


def import_sde(
    source_path: str,
    db: Session,
    sections: set[str] | None = None,
    progress: Callable[[SdeImportStats, str], None] | None = None,
) -> dict[str, Any]:
    source = SdeSource(source_path)
    stats = SdeImportStats(source_path=source_path)
    wanted = sections or {"categories", "groups", "types", "blueprints", "regions", "constellations", "systems", "stargates", "stations"}

    def mark(stage: str) -> None:
        if progress is not None:
            progress(stats, stage)

    try:
        if "categories" in wanted:
            mark("loading categories")
            categories = source.load_yaml("categories")
            for raw_id, payload in categories.items():
                upsert_category(db, int(raw_id), payload or {})
                stats.categories += 1
            db.commit()
            mark("categories complete")

        if "groups" in wanted:
            mark("loading groups")
            groups = source.load_yaml("groups")
            for raw_id, payload in groups.items():
                upsert_group(db, int(raw_id), payload or {})
                stats.groups += 1
            db.commit()
            mark("groups complete")

        if "types" in wanted:
            mark("loading types")
            types = source.load_yaml("types")
            for raw_id, payload in types.items():
                upsert_type(db, int(raw_id), payload or {})
                stats.types += 1
                if stats.types % 5000 == 0:
                    db.commit()
                    mark(f"types imported: {stats.types}")
            db.commit()
            mark("types complete")

        if "regions" in wanted:
            mark("loading regions")
            regions = source.load_yaml("regions")
            for raw_id, payload in regions.items():
                upsert_region(db, int(raw_id), payload or {})
                stats.regions += 1
            db.commit()
            mark("regions complete")

        if "constellations" in wanted:
            mark("loading constellations")
            constellations = source.load_yaml("constellations")
            for raw_id, payload in constellations.items():
                upsert_constellation(db, int(raw_id), payload or {})
                stats.constellations += 1
                if stats.constellations % 1000 == 0:
                    db.commit()
                    mark(f"constellations imported: {stats.constellations}")
            db.commit()
            mark("constellations complete")

        if "systems" in wanted:
            mark("loading solar systems")
            systems = source.load_yaml("systems")
            for raw_id, payload in systems.items():
                upsert_system(db, int(raw_id), payload or {})
                stats.systems += 1
                if stats.systems % 2500 == 0:
                    db.commit()
                    mark(f"systems imported: {stats.systems}")
            db.commit()
            mark("systems complete")

        if "stargates" in wanted:
            mark("loading stargates")
            stargates = source.load_yaml("stargates")
            for raw_id, payload in stargates.items():
                upsert_stargate(db, int(raw_id), payload or {})
                stats.stargates += 1
                if stats.stargates % 2500 == 0:
                    db.commit()
                    mark(f"stargates imported: {stats.stargates}")
            db.commit()
            mark("stargates complete")

        if "stations" in wanted:
            mark("loading npc stations")
            operation_names = station_operation_names(source.load_yaml("station_operations"))
            station_names = load_station_names(source)
            stations = source.load_yaml("stations")
            for raw_id, payload in stations.items():
                upsert_station(db, int(raw_id), payload or {}, operation_names, station_names)
                stats.stations += 1
                if stats.stations % 2500 == 0:
                    db.commit()
                    mark(f"stations imported: {stats.stations}")
            db.commit()
            mark("stations complete")

        if "blueprints" in wanted:
            mark("loading blueprints")
            blueprints = source.load_yaml("blueprints")
            for raw_blueprint_type_id, payload in blueprints.items():
                blueprint_type_id = int(raw_blueprint_type_id)
                ensure_placeholder_type(db, blueprint_type_id)
                for raw_activity_kind, activity_payload in (payload or {}).get("activities", {}).items():
                    activity_kind = ACTIVITY_MAP.get(str(raw_activity_kind))
                    if activity_kind is None:
                        stats.skipped_activities += 1
                        continue
                    products = (activity_payload or {}).get("products") or []
                    product = products[0] if products else None
                    product_type_id = int(product["typeID"]) if product and product.get("typeID") is not None else None
                    if product_type_id is not None:
                        ensure_placeholder_type(db, product_type_id)

                    activity = db.scalar(
                        select(IndustryActivity).where(
                            IndustryActivity.blueprint_type_id == blueprint_type_id,
                            IndustryActivity.activity_kind == activity_kind,
                        )
                    )
                    if activity is None:
                        activity = IndustryActivity(blueprint_type_id=blueprint_type_id, activity_kind=activity_kind)
                        db.add(activity)
                    activity.product_type_id = product_type_id
                    activity.product_quantity = int(product.get("quantity", 1)) if product else 1
                    activity.time_seconds = int((activity_payload or {}).get("time")) if (activity_payload or {}).get("time") is not None else None
                    db.flush()

                    db.execute(delete(IndustryActivityInput).where(IndustryActivityInput.activity_id == activity.id))
                    for material in (activity_payload or {}).get("materials") or []:
                        input_type_id = int(material["typeID"])
                        ensure_placeholder_type(db, input_type_id)
                        db.add(
                            IndustryActivityInput(
                                activity_id=activity.id,
                                input_type_id=input_type_id,
                                quantity=int(material.get("quantity", 0)),
                                consume_type="consumed",
                            )
                        )
                        stats.activity_inputs += 1
                    stats.blueprint_activities += 1
                if stats.blueprint_activities % 1000 == 0:
                    db.commit()
                    mark(f"blueprint activities imported: {stats.blueprint_activities}")
            db.commit()
            mark("blueprints complete")

        mark("complete")
        return stats.to_dict()
    except Exception:
        db.rollback()
        raise
    finally:
        source.close()


