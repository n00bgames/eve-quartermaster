from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any
import zipfile

import yaml
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import EveCategory, EveGroup, EveType, IndustryActivity, IndustryActivityInput
from app.models.enums import ActivityKind


SDE_FILES = {
    "categories": ("categories.yaml", "categoryIDs.yaml"),
    "groups": ("groups.yaml", "groupIDs.yaml"),
    "types": ("types.yaml", "typeIDs.yaml"),
    "blueprints": ("blueprints.yaml",),
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
        for member in self.archive.namelist() if self.archive is not None else []:
            normalized = PurePosixPath(member).as_posix().lstrip("/")
            if normalized in expected or normalized.endswith(fsd_suffixes):
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
    wanted = sections or {"categories", "groups", "types", "blueprints"}

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
