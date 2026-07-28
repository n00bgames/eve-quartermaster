from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
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
    SnapshotMetric,
    SnapshotRun,
)
from app.models.enums import OwnerKind, SyncStatus


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


def create_snapshot(
    db: Session,
    *,
    scope_type: str = "global",
    scope_id: int | None = None,
    source: str = "manual",
    message: str | None = None,
) -> SnapshotRun:
    run = SnapshotRun(scope_type=scope_type, scope_id=scope_id, source=source, status="running", message=message)
    db.add(run)
    db.flush()
    try:
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
    metric_version: int = 1,
    dimensions: dict[str, object] | None = None,
) -> None:
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


def skill_category_name(skill: CharacterSkill) -> str:
    group = skill.skill_type.group if skill.skill_type else None
    category = group.category if group else None
    if group and group.name:
        return group.name
    if category and category.name and category.name != "Skill":
        return category.name
    return "Uncategorized"


def snapshot_character_skills(db: Session, run: SnapshotRun) -> None:
    characters = db.scalars(
        select(EveCharacter)
        .where(EveCharacter.total_skill_points.is_not(None))
        .order_by(EveCharacter.name)
    ).all()
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


def snapshot_corporations(db: Session, run: SnapshotRun) -> None:
    corporation_ids = analytics_corporation_ids(db)
    if not corporation_ids:
        return
    corporations = db.scalars(
        select(EveCorporation)
        .where(EveCorporation.id.in_(corporation_ids))
        .order_by(EveCorporation.name)
    ).all()
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
            blueprint_count = db.scalar(select(func.count()).select_from(Blueprint).where(Blueprint.ownership_entity_id == owner.id)) or 0
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
        .options(selectinload(Blueprint.ownership_entity), selectinload(Blueprint.blueprint_type))
        .where(corporation_filter)
        .order_by(Blueprint.blueprint_type_id)
    ).all()
    grouped: dict[tuple[int, int, int, int, bool, str, str], int] = defaultdict(int)
    for blueprint in blueprints:
        owner_name = blueprint.ownership_entity.display_name if blueprint.ownership_entity else "Unknown owner"
        blueprint_name = blueprint.blueprint_type.name if blueprint.blueprint_type else f"Type {blueprint.blueprint_type_id}"
        key = (
            blueprint.ownership_entity_id,
            blueprint.blueprint_type_id,
            int(blueprint.material_efficiency or 0),
            int(blueprint.time_efficiency or 0),
            bool(blueprint.is_copy),
            owner_name,
            blueprint_name,
        )
        grouped[key] += 1
    for (owner_id, type_id, me, te, is_copy, owner_name, blueprint_name), quantity in grouped.items():
        db.add(
            BlueprintSnapshot(
                snapshot_run_id=run.id,
                ownership_entity_id=owner_id,
                owner_name=owner_name,
                blueprint_type_id=type_id,
                blueprint_type_name=blueprint_name,
                material_efficiency=me,
                time_efficiency=te,
                is_copy=is_copy,
                quantity=quantity,
            )
        )
        add_metric(
            db,
            run,
            owner_type="owner",
            owner_id=owner_id,
            owner_name=owner_name,
            metric_key="blueprint.quantity",
            metric_value=quantity,
            dimensions={"blueprint_type_id": type_id, "blueprint": blueprint_name, "me": me, "te": te, "is_copy": is_copy},
        )





