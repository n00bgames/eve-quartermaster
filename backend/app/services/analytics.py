from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Asset,
    Blueprint,
    BlueprintSnapshot,
    CharacterSkill,
    CharacterSkillQueueEntry,
    CharacterSkillSnapshot,
    CharacterWalletSnapshot,
    CorporationSnapshot,
    CorporationWalletDivision,
    CorporationWalletSnapshot,
    EveCategory,
    EveCharacter,
    EveCorporation,
    EsiSyncJob,
    EsiToken,
    EveGroup,
    EveType,
    OwnershipEntity,
    ResearchProject,
    SnapshotMetric,
    SnapshotRun,
)
from app.models.enums import OwnerKind, SyncStatus
from app.services.metric_registry import metric_definition


CORPORATION_ANALYTICS_SYNC_TYPES = frozenset(
    {
        "corporation_assets",
        "corporation_blueprints",
        "corporation_wallets",
    }
)


def decimal_value(value: int | float | Decimal | None) -> Decimal:
    return Decimal(str(value or 0))


def privileged_analytics_corporation_ids(db: Session) -> set[int]:
    """Corporations with current linked-token evidence of successful corporate access."""
    return set(
        db.scalars(
            select(EveCorporation.id)
            .join(
                OwnershipEntity,
                (OwnershipEntity.corporation_id == EveCorporation.id)
                & (OwnershipEntity.owner_kind == OwnerKind.CORPORATION),
            )
            .join(EsiSyncJob, EsiSyncJob.ownership_entity_id == OwnershipEntity.id)
            .join(EsiToken, EsiToken.id == EsiSyncJob.token_id)
            .join(
                EveCharacter,
                (EveCharacter.id == EsiToken.character_id)
                & (EveCharacter.corporation_id == EveCorporation.id),
            )
            .where(
                EsiToken.revoked_at.is_(None),
                EsiSyncJob.status == SyncStatus.SUCCESS,
                EsiSyncJob.sync_type.in_(CORPORATION_ANALYTICS_SYNC_TYPES),
            )
            .distinct()
        ).all()
    )


def analytics_corporation_ids(db: Session) -> set[int]:
    privileged_ids = privileged_analytics_corporation_ids(db)
    if not privileged_ids:
        return set()
    return set(
        db.scalars(
            select(EveCorporation.id).where(
                EveCorporation.id.in_(privileged_ids),
                EveCorporation.hide_from_corporation_list.is_(False),
                EveCorporation.exclude_from_analytics.is_(False),
            )
        ).all()
    )


AUTO_SNAPSHOT_COALESCE_MINUTES = 60
SNAPSHOT_SCHEMA_VERSION = 3


def recent_automatic_snapshot(
    db: Session,
    *,
    scope_type: str,
    scope_id: int | None,
    source: str,
    now: datetime,
) -> SnapshotRun | None:
    if source == "manual" or scope_id is None:
        return None
    cutoff = now - timedelta(minutes=AUTO_SNAPSHOT_COALESCE_MINUTES)
    return db.scalar(
        select(SnapshotRun)
        .where(
            SnapshotRun.scope_type == scope_type,
            SnapshotRun.scope_id == scope_id,
            SnapshotRun.source == source,
            SnapshotRun.status == "success",
            SnapshotRun.started_at >= cutoff,
            SnapshotRun.schema_version >= SNAPSHOT_SCHEMA_VERSION,
        )
        .order_by(SnapshotRun.started_at.desc(), SnapshotRun.id.desc())
        .limit(1)
    )


def create_snapshot(
    db: Session,
    *,
    scope_type: str = "global",
    scope_id: int | None = None,
    source: str = "manual",
    message: str | None = None,
) -> SnapshotRun:
    now = datetime.now(timezone.utc)
    existing = recent_automatic_snapshot(
        db,
        scope_type=scope_type,
        scope_id=scope_id,
        source=source,
        now=now,
    )
    if existing is not None:
        return existing

    run = SnapshotRun(
        scope_type=scope_type,
        scope_id=scope_id,
        source=source,
        status="running",
        schema_version=SNAPSHOT_SCHEMA_VERSION,
        message=message,
    )
    db.add(run)
    db.flush()
    try:
        if scope_type == "global":
            snapshot_character_wallets(db, run)
            snapshot_character_skills(db, run)
            snapshot_corporations(db, run)
            snapshot_blueprints(db, run)
        elif scope_type == "character" and scope_id is not None:
            snapshot_character_wallets(db, run, {scope_id})
            if source == "character_assets":
                snapshot_character_assets(db, run, scope_id)
            elif source != "character_wallet":
                snapshot_character_skills(db, run, {scope_id})
        elif scope_type == "corporation" and scope_id is not None:
            snapshot_corporations(db, run, {scope_id})
            if source == "corporation_blueprints":
                # Detailed blueprint rows are captured only by blueprint syncs or manual global snapshots.
                snapshot_blueprints(db, run)
        else:
            snapshot_character_wallets(db, run)
            snapshot_character_skills(db, run)
            snapshot_corporations(db, run)
            snapshot_blueprints(db, run)
        run.status = "success"
        run.completed_at = datetime.now(timezone.utc)
        db.flush()
        return run
    except Exception as exc:
        run.status = "failed"
        run.message = f"{message or ''} {exc}".strip()
        run.completed_at = datetime.now(timezone.utc)
        db.flush()
        raise


def add_metric(
    db: Session,
    run: SnapshotRun,
    *,
    owner_type: str,
    owner_id: int | None,
    owner_name: str | None,
    metric_key: str,
    metric_value: int | float | Decimal | None,
    metric_version: int | None = None,
    dimensions: dict[str, object] | None = None,
) -> None:
    definition = metric_definition(metric_key)
    if owner_type == "character" and not definition["supportsCharacter"]:
        raise ValueError(f"Metric {metric_key!r} does not support character snapshots")
    if owner_type == "corporation" and not definition["supportsCorporation"]:
        raise ValueError(f"Metric {metric_key!r} does not support corporation snapshots")
    registered_version = int(definition["version"])
    if metric_version is not None and metric_version != registered_version:
        raise ValueError(f"Metric {metric_key!r} requires version {registered_version}, not {metric_version}")
    metric_version = registered_version
    db.add(
        SnapshotMetric(
            snapshot_run_id=run.id,
            owner_type=owner_type,
            owner_id=owner_id,
            owner_name=owner_name,
            metric_key=metric_key,
            metric_version=metric_version,
            metric_value=decimal_value(metric_value),
            dimensions_json=dimensions,
        )
    )


def snapshot_character_assets(db: Session, run: SnapshotRun, character_id: int) -> None:
    character = db.get(EveCharacter, character_id)
    if character is None:
        return
    owner = db.scalar(
        select(OwnershipEntity).where(
            OwnershipEntity.owner_kind == OwnerKind.CHARACTER,
            OwnershipEntity.character_id == character_id,
        )
    )
    asset_rows = asset_units = blueprint_count = 0
    if owner is not None:
        asset_rows = int(db.scalar(select(func.count()).select_from(Asset).where(Asset.ownership_entity_id == owner.id)) or 0)
        asset_units = int(db.scalar(select(func.coalesce(func.sum(Asset.quantity), 0)).where(Asset.ownership_entity_id == owner.id)) or 0)
        blueprint_count = int(db.scalar(select(func.count()).select_from(Blueprint).where(Blueprint.ownership_entity_id == owner.id)) or 0)
    add_metric(db, run, owner_type="character", owner_id=character.id, owner_name=character.name, metric_key="assets.rows", metric_value=asset_rows)
    add_metric(db, run, owner_type="character", owner_id=character.id, owner_name=character.name, metric_key="assets.units", metric_value=asset_units)
    add_metric(db, run, owner_type="character", owner_id=character.id, owner_name=character.name, metric_key="blueprints.count", metric_value=blueprint_count)


def snapshot_character_wallets(db: Session, run: SnapshotRun, character_ids: set[int] | None = None) -> None:
    query = (
        select(EveCharacter)
        .where(
            EveCharacter.current_wallet_balance.is_not(None),
            EveCharacter.wallet_history_opt_out.is_(False),
            EveCharacter.sync_opt_out.is_(False),
        )
        .options(selectinload(EveCharacter.corporation))
    )
    if character_ids is not None:
        if not character_ids:
            return
        query = query.where(EveCharacter.id.in_(character_ids))
    for character in db.scalars(query.order_by(EveCharacter.name)).all():
        db.add(
            CharacterWalletSnapshot(
                snapshot_run_id=run.id,
                character_id=character.id,
                character_eve_id=character.character_id,
                character_name=character.name,
                corporation_id=character.corporation_id,
                corporation_name=character.corporation.name if character.corporation else None,
                balance=decimal_value(character.current_wallet_balance),
            )
        )
        add_metric(
            db,
            run,
            owner_type="character",
            owner_id=character.id,
            owner_name=character.name,
            metric_key="character_wallet.balance",
            metric_value=character.current_wallet_balance,
        )


def skill_category_name(skill: CharacterSkill) -> str:
    group = skill.skill_type.group if skill.skill_type else None
    category = group.category if group else None
    if group and group.name:
        return group.name
    if category and category.name and category.name != "Skill":
        return category.name
    return "Uncategorized"


def snapshot_character_skills(db: Session, run: SnapshotRun, character_ids: set[int] | None = None) -> None:
    query = select(EveCharacter).where(EveCharacter.total_skill_points.is_not(None))
    if character_ids is not None:
        if not character_ids:
            return
        query = query.where(EveCharacter.id.in_(character_ids))
    characters = db.scalars(query.order_by(EveCharacter.name)).all()
    for character in characters:
        skills = db.scalars(
            select(CharacterSkill)
            .options(selectinload(CharacterSkill.skill_type).selectinload(EveType.group).selectinload(EveGroup.category))
            .where(CharacterSkill.character_id == character.id)
        ).all()
        queue_count = db.scalar(select(func.count()).select_from(CharacterSkillQueueEntry).where(CharacterSkillQueueEntry.character_id == character.id)) or 0
        category_points: dict[str, int] = defaultdict(int)
        for skill in skills:
            category_points[skill_category_name(skill)] += int(skill.skillpoints_in_skill or 0)

        db.add(
            CharacterSkillSnapshot(
                snapshot_run_id=run.id,
                character_id=character.id,
                character_eve_id=character.character_id,
                character_name=character.name,
                total_skill_points=int(character.total_skill_points or 0),
                unallocated_skill_points=int(character.unallocated_skill_points or 0),
                skill_count=len(skills),
                queue_count=int(queue_count),
            )
        )
        add_metric(db, run, owner_type="character", owner_id=character.id, owner_name=character.name, metric_key="skill_points.total", metric_value=character.total_skill_points)
        add_metric(db, run, owner_type="character", owner_id=character.id, owner_name=character.name, metric_key="skills.count", metric_value=len(skills))
        add_metric(db, run, owner_type="character", owner_id=character.id, owner_name=character.name, metric_key="skill_queue.count", metric_value=queue_count)
        for category, points in sorted(category_points.items()):
            db.add(
                CharacterSkillSnapshot(
                    snapshot_run_id=run.id,
                    character_id=character.id,
                    character_eve_id=character.character_id,
                    character_name=character.name,
                    total_skill_points=int(character.total_skill_points or 0),
                    unallocated_skill_points=int(character.unallocated_skill_points or 0),
                    skill_count=len(skills),
                    queue_count=int(queue_count),
                    category_name=category,
                    category_skill_points=points,
                )
            )
            add_metric(
                db,
                run,
                owner_type="character",
                owner_id=character.id,
                owner_name=character.name,
                metric_key="skill_points.category",
                metric_value=points,
                dimensions={"category": category},
            )


RESEARCH_BLUEPRINT_ACTIVITIES = frozenset({3, 4, 5})
RESEARCH_BLUEPRINT_STATUSES = frozenset({"active", "paused", "ready"})


def scoped_blueprint_records(db: Session) -> list[dict[str, object]]:
    """Merge visible inventory and in-flight research by immutable ESI blueprint item ID."""
    corporation_ids = analytics_corporation_ids(db)
    corporation_filter = OwnershipEntity.owner_kind != OwnerKind.CORPORATION
    if corporation_ids:
        corporation_filter = or_(
            corporation_filter,
            OwnershipEntity.corporation_id.in_(corporation_ids),
        )
    blueprints = db.scalars(
        select(Blueprint)
        .join(OwnershipEntity, OwnershipEntity.id == Blueprint.ownership_entity_id)
        .options(
            selectinload(Blueprint.asset),
            selectinload(Blueprint.ownership_entity),
            selectinload(Blueprint.blueprint_type),
        )
        .where(corporation_filter)
        .order_by(Blueprint.blueprint_type_id, Blueprint.id)
    ).all()
    records: dict[tuple[str, int], dict[str, object]] = {}
    for blueprint in blueprints:
        owner = blueprint.ownership_entity
        item_id = blueprint.asset.eve_item_id if blueprint.asset else None
        key = ("item", int(item_id)) if item_id is not None else ("blueprint", int(blueprint.id))
        records[key] = {
            "owner_id": int(blueprint.ownership_entity_id),
            "owner_name": owner.display_name if owner else "Unknown owner",
            "type_id": int(blueprint.blueprint_type_id),
            "type_name": blueprint.blueprint_type.name if blueprint.blueprint_type else f"Type {blueprint.blueprint_type_id}",
            "material_efficiency": int(blueprint.material_efficiency or 0),
            "time_efficiency": int(blueprint.time_efficiency or 0),
            "runs_remaining": blueprint.runs_remaining,
            "is_copy": bool(blueprint.is_copy),
            "item_id": int(item_id) if item_id is not None else None,
            "inventory_state": "inventory",
            "research_job_id": None,
        }

    owners = db.scalars(select(OwnershipEntity)).all()
    character_owners = {
        int(owner.character_id): owner
        for owner in owners
        if owner.owner_kind == OwnerKind.CHARACTER and owner.character_id is not None
    }
    corporation_owners = {
        int(owner.corporation_id): owner
        for owner in owners
        if owner.owner_kind == OwnerKind.CORPORATION
        and owner.corporation_id is not None
        and owner.corporation_id in corporation_ids
    }
    projects = db.scalars(
        select(ResearchProject)
        .options(
            selectinload(ResearchProject.blueprint_type),
            selectinload(ResearchProject.character),
            selectinload(ResearchProject.corporation),
        )
        .where(
            ResearchProject.activity_id.in_(RESEARCH_BLUEPRINT_ACTIVITIES),
            ResearchProject.status.in_(RESEARCH_BLUEPRINT_STATUSES),
            ResearchProject.blueprint_id.is_not(None),
            ResearchProject.blueprint_type_id.is_not(None),
        )
        .order_by(ResearchProject.job_id)
    ).all()
    for project in projects:
        if project.source_type == "corporation":
            owner = corporation_owners.get(int(project.corporation_id)) if project.corporation_id is not None else None
        else:
            owner = character_owners.get(int(project.character_id)) if project.character_id is not None else None
        if owner is None or project.blueprint_id is None or project.blueprint_type_id is None:
            continue
        item_id = int(project.blueprint_id)
        key = ("item", item_id)
        existing = records.get(key)
        if existing is not None:
            existing["inventory_state"] = "in_production"
            existing["research_job_id"] = int(project.job_id)
            continue

        prior = db.scalar(
            select(BlueprintSnapshot)
            .where(BlueprintSnapshot.blueprint_item_id == item_id)
            .order_by(BlueprintSnapshot.snapshot_run_id.desc(), BlueprintSnapshot.id.desc())
            .limit(1)
        )
        if prior is None:
            prior = db.scalar(
                select(BlueprintSnapshot)
                .where(
                    BlueprintSnapshot.ownership_entity_id == owner.id,
                    BlueprintSnapshot.blueprint_type_id == project.blueprint_type_id,
                    BlueprintSnapshot.is_copy.is_(False),
                )
                .order_by(BlueprintSnapshot.snapshot_run_id.desc(), BlueprintSnapshot.id.desc())
                .limit(1)
            )
        records[key] = {
            "owner_id": int(owner.id),
            "owner_name": owner.display_name,
            "type_id": int(project.blueprint_type_id),
            "type_name": project.blueprint_type.name if project.blueprint_type else f"Type {project.blueprint_type_id}",
            "material_efficiency": int(prior.material_efficiency or 0) if prior else 0,
            "time_efficiency": int(prior.time_efficiency or 0) if prior else 0,
            "runs_remaining": prior.runs_remaining if prior else None,
            "is_copy": bool(prior.is_copy) if prior else False,
            "item_id": item_id,
            "inventory_state": "in_production",
            "research_job_id": int(project.job_id),
        }
    return list(records.values())

def snapshot_corporations(db: Session, run: SnapshotRun, requested_corporation_ids: set[int] | None = None) -> None:
    corporation_ids = analytics_corporation_ids(db)
    if requested_corporation_ids is not None:
        corporation_ids &= requested_corporation_ids
    if not corporation_ids:
        return
    corporations = db.scalars(
        select(EveCorporation)
        .where(EveCorporation.id.in_(corporation_ids))
        .order_by(EveCorporation.name)
    ).all()
    blueprint_counts: dict[int, int] = defaultdict(int)
    for record in scoped_blueprint_records(db):
        blueprint_counts[int(record["owner_id"])] += 1
    for corporation in corporations:
        owner = db.scalar(
            select(OwnershipEntity).where(
                OwnershipEntity.owner_kind == OwnerKind.CORPORATION,
                OwnershipEntity.corporation_id == corporation.id,
            )
        )
        asset_rows = 0
        asset_units = 0
        blueprint_count = 0
        if owner is not None:
            asset_rows = db.scalar(select(func.count()).select_from(Asset).where(Asset.ownership_entity_id == owner.id)) or 0
            asset_units = db.scalar(select(func.coalesce(func.sum(Asset.quantity), 0)).where(Asset.ownership_entity_id == owner.id)) or 0
            blueprint_count = blueprint_counts.get(owner.id, 0)
        wallets = db.scalars(select(CorporationWalletDivision).where(CorporationWalletDivision.corporation_id == corporation.id)).all()
        wallet_total = sum(decimal_value(wallet.balance) for wallet in wallets)
        db.add(
            CorporationSnapshot(
                snapshot_run_id=run.id,
                corporation_id=corporation.id,
                corporation_eve_id=corporation.corporation_id,
                corporation_name=corporation.name,
                member_count=corporation.member_count,
                wallet_balance=wallet_total,
                asset_rows=int(asset_rows),
                asset_units=int(asset_units),
                blueprint_count=int(blueprint_count),
            )
        )
        add_metric(db, run, owner_type="corporation", owner_id=corporation.id, owner_name=corporation.name, metric_key="members.count", metric_value=corporation.member_count)
        add_metric(db, run, owner_type="corporation", owner_id=corporation.id, owner_name=corporation.name, metric_key="wallet.balance", metric_value=wallet_total)
        add_metric(db, run, owner_type="corporation", owner_id=corporation.id, owner_name=corporation.name, metric_key="assets.rows", metric_value=asset_rows)
        add_metric(db, run, owner_type="corporation", owner_id=corporation.id, owner_name=corporation.name, metric_key="assets.units", metric_value=asset_units)
        add_metric(db, run, owner_type="corporation", owner_id=corporation.id, owner_name=corporation.name, metric_key="blueprints.count", metric_value=blueprint_count)
        for wallet in wallets:
            db.add(
                CorporationWalletSnapshot(
                    snapshot_run_id=run.id,
                    corporation_id=corporation.id,
                    corporation_eve_id=corporation.corporation_id,
                    corporation_name=corporation.name,
                    division=wallet.division,
                    balance=decimal_value(wallet.balance),
                )
            )
            add_metric(
                db,
                run,
                owner_type="corporation",
                owner_id=corporation.id,
                owner_name=corporation.name,
                metric_key="wallet.division_balance",
                metric_value=wallet.balance,
                dimensions={"division": wallet.division},
            )


def snapshot_blueprints(db: Session, run: SnapshotRun) -> None:
    records = scoped_blueprint_records(db)
    grouped: dict[tuple[int, int, int, int, bool, str, str, str], int] = defaultdict(int)
    for record in records:
        owner_id = int(record["owner_id"])
        owner_name = str(record["owner_name"])
        type_id = int(record["type_id"])
        type_name = str(record["type_name"])
        me = int(record["material_efficiency"])
        te = int(record["time_efficiency"])
        is_copy = bool(record["is_copy"])
        inventory_state = str(record["inventory_state"])
        db.add(
            BlueprintSnapshot(
                snapshot_run_id=run.id,
                ownership_entity_id=owner_id,
                owner_name=owner_name,
                blueprint_item_id=record["item_id"],
                blueprint_type_id=type_id,
                blueprint_type_name=type_name,
                material_efficiency=me,
                time_efficiency=te,
                runs_remaining=record["runs_remaining"],
                is_copy=is_copy,
                inventory_state=inventory_state,
                research_job_id=record["research_job_id"],
                quantity=1,
            )
        )
        grouped[(owner_id, type_id, me, te, is_copy, owner_name, type_name, inventory_state)] += 1

    for (owner_id, type_id, me, te, is_copy, owner_name, type_name, inventory_state), quantity in grouped.items():
        add_metric(
            db,
            run,
            owner_type="owner",
            owner_id=owner_id,
            owner_name=owner_name,
            metric_key="blueprint.quantity",
            metric_value=quantity,
            dimensions={
                "blueprint_type_id": type_id,
                "blueprint": type_name,
                "me": me,
                "te": te,
                "is_copy": is_copy,
                "inventory_state": inventory_state,
            },
        )