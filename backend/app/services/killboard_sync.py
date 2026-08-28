from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import time
from typing import Any, Protocol
import uuid

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import (
    EveCharacter,
    EveCorporation,
    KillboardSyncRun,
    Killmail,
    KillmailAttacker,
    KillmailDiscovery,
    KillmailItem,
    User,
    ZkillEnrichment,
)
from app.services.esi_client import EsiClient
from app.services.killboard_settings import killboard_settings
from app.services.permissions import role_rank


ZKILLBOARD_BASE_URL = "https://zkillboard.com/api"
KILLBOARD_USER_AGENT = "EVE-Quartermaster/0.1.23-beta killboard (+https://github.com/n00bgames/eve-quartermaster)"
ZKILLBOARD_HEADERS = {
    "User-Agent": KILLBOARD_USER_AGENT,
    "Accept-Encoding": "gzip",
    "Accept": "application/json",
}
SYNC_FEEDS = ("kills", "losses")
ACTIVE_SYNC_TASKS: dict[str, asyncio.Task[None]] = {}


class DiscoveryClient(Protocol):
    async def fetch_page(self, owner_type: str, owner_id: int, feed: str, page: int) -> list[dict[str, Any]]: ...
    async def close(self) -> None: ...


class CanonicalClient(Protocol):
    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any: ...
    async def close(self) -> None: ...


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def optional_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def parse_killmail_time(value: Any) -> datetime:
    if not value:
        raise ValueError("Canonical ESI killmail is missing killmail_time")
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Canonical ESI killmail contains an invalid killmail_time") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def discovery_identity(entry: dict[str, Any]) -> tuple[int, str]:
    zkb = entry.get("zkb") if isinstance(entry.get("zkb"), dict) else {}
    killmail_id = optional_int(entry.get("killmail_id") or entry.get("killID"))
    killmail_hash = str(entry.get("killmail_hash") or zkb.get("hash") or "").strip()
    if killmail_id is None or not killmail_hash:
        raise ValueError("zKill discovery row is missing killmail ID or hash")
    return killmail_id, killmail_hash


def decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def bool_or_none(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return bool(value)


def flatten_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []

    def visit(rows: list[dict[str, Any]], parent_index: int | None = None) -> None:
        for raw in rows:
            if not isinstance(raw, dict) or optional_int(raw.get("item_type_id")) is None:
                continue
            item_index = len(flattened)
            flattened.append({"item_index": item_index, "parent_item_index": parent_index, "raw": raw})
            children = raw.get("items")
            if isinstance(children, list):
                visit(children, item_index)

    visit(items)
    return flattened


def validate_canonical_payload(payload: Any) -> tuple[dict[str, Any], datetime, int]:
    if not isinstance(payload, dict):
        raise ValueError("Canonical ESI killmail payload is not an object")
    victim = payload.get("victim")
    attackers = payload.get("attackers")
    system_id = optional_int(payload.get("solar_system_id"))
    if not isinstance(victim, dict):
        raise ValueError("Canonical ESI killmail is missing victim data")
    if not isinstance(attackers, list):
        raise ValueError("Canonical ESI killmail is missing attacker data")
    if system_id is None:
        raise ValueError("Canonical ESI killmail is missing solar_system_id")
    return payload, parse_killmail_time(payload.get("killmail_time")), system_id


def upsert_killmail(
    db: Session,
    *,
    killmail_id: int,
    killmail_hash: str,
    esi_payload: dict[str, Any],
    zkill_payload: dict[str, Any],
    owner_type: str,
    owner_id: int,
    feed: str,
) -> tuple[Killmail, bool]:
    """Replace normalized children only after a complete canonical payload validates."""
    canonical, killmail_time, system_id = validate_canonical_payload(esi_payload)
    victim = canonical["victim"]
    now = utc_now()
    row = db.get(Killmail, killmail_id)
    created = row is None
    if row is None:
        row = Killmail(killmail_id=killmail_id, killmail_hash=killmail_hash, killmail_time=killmail_time, solar_system_id=system_id, canonical_esi_payload=canonical)
        db.add(row)
        db.flush()
    else:
        db.execute(delete(KillmailAttacker).where(KillmailAttacker.killmail_id == killmail_id))
        db.execute(delete(KillmailItem).where(KillmailItem.killmail_id == killmail_id))

    row.killmail_hash = killmail_hash
    row.killmail_time = killmail_time
    row.solar_system_id = system_id
    row.victim_character_id = optional_int(victim.get("character_id"))
    row.victim_corporation_id = optional_int(victim.get("corporation_id"))
    row.victim_alliance_id = optional_int(victim.get("alliance_id"))
    row.victim_faction_id = optional_int(victim.get("faction_id"))
    row.victim_ship_type_id = optional_int(victim.get("ship_type_id"))
    row.damage_taken = optional_int(victim.get("damage_taken")) or 0
    row.war_id = optional_int(canonical.get("war_id"))
    row.canonical_esi_payload = canonical
    row.last_updated_at = now

    for index, attacker in enumerate(canonical["attackers"]):
        if not isinstance(attacker, dict):
            continue
        db.add(KillmailAttacker(
            killmail_id=killmail_id, attacker_index=index,
            character_id=optional_int(attacker.get("character_id")), corporation_id=optional_int(attacker.get("corporation_id")),
            alliance_id=optional_int(attacker.get("alliance_id")), faction_id=optional_int(attacker.get("faction_id")),
            ship_type_id=optional_int(attacker.get("ship_type_id")), weapon_type_id=optional_int(attacker.get("weapon_type_id")),
            damage_done=optional_int(attacker.get("damage_done")) or 0, final_blow=bool(attacker.get("final_blow")),
            security_status=optional_float(attacker.get("security_status")),
        ))

    source_items = victim.get("items") if isinstance(victim.get("items"), list) else []
    for item in flatten_items(source_items):
        raw = item["raw"]
        db.add(KillmailItem(
            killmail_id=killmail_id, item_index=item["item_index"], parent_item_index=item["parent_item_index"],
            item_type_id=int(raw["item_type_id"]), flag=optional_int(raw.get("flag")) or 0,
            singleton=optional_int(raw.get("singleton")) or 0,
            quantity_destroyed=optional_int(raw.get("quantity_destroyed")) or 0,
            quantity_dropped=optional_int(raw.get("quantity_dropped")) or 0,
            raw_payload=raw,
        ))

    upsert_enrichment(db, killmail_id, zkill_payload, now)
    ensure_discovery(db, killmail_id, owner_type, owner_id, feed)
    return row, created


def upsert_enrichment(db: Session, killmail_id: int, payload: dict[str, Any], now: datetime | None = None) -> ZkillEnrichment:
    zkb = payload.get("zkb") if isinstance(payload.get("zkb"), dict) else payload
    row = db.get(ZkillEnrichment, killmail_id)
    if row is None:
        row = ZkillEnrichment(killmail_id=killmail_id, zkill_url=f"https://zkillboard.com/kill/{killmail_id}/", raw_enrichment_payload=zkb)
        db.add(row)
    row.estimated_total_value = decimal_or_none(zkb.get("totalValue"))
    row.points = optional_int(zkb.get("points"))
    row.solo = bool_or_none(zkb.get("solo"))
    row.npc = bool_or_none(zkb.get("npc"))
    row.awox = bool_or_none(zkb.get("awox"))
    row.zkill_url = str(zkb.get("url") or f"https://zkillboard.com/kill/{killmail_id}/")
    row.raw_enrichment_payload = zkb
    row.updated_at = now or utc_now()
    return row


def ensure_discovery(db: Session, killmail_id: int, owner_type: str, owner_id: int, feed: str) -> KillmailDiscovery:
    row = db.scalar(select(KillmailDiscovery).where(
        KillmailDiscovery.killmail_id == killmail_id,
        KillmailDiscovery.owner_type == owner_type,
        KillmailDiscovery.owner_id == owner_id,
        KillmailDiscovery.feed == feed,
    ))
    if row is None:
        row = KillmailDiscovery(killmail_id=killmail_id, owner_type=owner_type, owner_id=owner_id, feed=feed)
        db.add(row)
    return row


class ZkillDiscoveryClient:
    def __init__(self, request_delay_seconds: float = 1.0, client: httpx.AsyncClient | None = None) -> None:
        self.request_delay_seconds = max(0.2, float(request_delay_seconds))
        self._last_request_at = 0.0
        self._client = client or httpx.AsyncClient(
            headers=ZKILLBOARD_HEADERS,
            timeout=30.0,
            follow_redirects=True,
        )
        self._owns_client = client is None

    async def fetch_page(self, owner_type: str, owner_id: int, feed: str, page: int) -> list[dict[str, Any]]:
        if owner_type not in {"character", "corporation", "alliance"} or feed not in SYNC_FEEDS:
            raise ValueError("Unsupported zKill discovery target")
        wait_for = self.request_delay_seconds - (time.monotonic() - self._last_request_at)
        if wait_for > 0:
            await asyncio.sleep(wait_for)
        modifier = {"character": "characterID", "corporation": "corporationID", "alliance": "allianceID"}[owner_type]
        url = f"{ZKILLBOARD_BASE_URL}/{feed}/{modifier}/{owner_id}/page/{max(1, page)}/"
        for attempt in range(3):
            response = await self._client.get(url, headers=ZKILLBOARD_HEADERS)
            self._last_request_at = time.monotonic()
            if response.status_code == 429:
                await asyncio.sleep(min(60.0, max(self.request_delay_seconds, float(response.headers.get("Retry-After") or 1))))
                continue
            if response.status_code >= 500 and attempt < 2:
                await asyncio.sleep(self.request_delay_seconds * (attempt + 1))
                continue
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, list) else []
        raise RuntimeError("zKillboard request retries exhausted")

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()


def sync_targets_for_user(db: Session, user: User, scope: str = "account") -> list[dict[str, Any]]:
    character_query = select(EveCharacter).where(EveCharacter.sync_opt_out.is_(False))
    if role_rank(user, db) < role_rank("admin") or scope == "account":
        character_query = character_query.where(EveCharacter.owner_user_id == user.id)
    characters = db.scalars(character_query.order_by(EveCharacter.name)).all()
    targets = [{"owner_type": "character", "owner_id": row.character_id, "owner_name": row.name} for row in characters]
    if scope in {"corporations", "all"} or role_rank(user, db) >= role_rank("officer"):
        corporation_ids = {row.corporation_id for row in characters if row.corporation_id is not None}
        if scope == "all" and role_rank(user, db) >= role_rank("admin"):
            corporation_ids.update(db.scalars(select(EveCorporation.id)).all())
        corporations = db.scalars(select(EveCorporation).where(EveCorporation.id.in_(corporation_ids)).order_by(EveCorporation.name)).all() if corporation_ids else []
        targets.extend({"owner_type": "corporation", "owner_id": row.corporation_id, "owner_name": row.name} for row in corporations)
    seen: set[tuple[str, int]] = set()
    unique: list[dict[str, Any]] = []
    for target in targets:
        key = (str(target["owner_type"]), int(target["owner_id"]))
        if key not in seen:
            seen.add(key)
            unique.append(target)
    return unique


def create_sync_run(db: Session, user: User, *, scope: str = "account", lookback_days: int | None = None) -> KillboardSyncRun:
    settings = killboard_settings(db)
    if not settings["enabled"]:
        raise ValueError("The Killboard module is disabled")
    targets = sync_targets_for_user(db, user, scope)
    if not targets:
        raise ValueError("No eligible linked characters or corporations are available for killboard sync")
    run = KillboardSyncRun(
        id=uuid.uuid4().hex,
        initiated_by_user_id=user.id,
        status="queued",
        targets_json=targets,
        lookback_days=max(1, min(3650, int(lookback_days or settings["lookback_days"]))),
        errors_json=[],
    )
    db.add(run)
    db.flush()
    return run


def sync_run_payload(run: KillboardSyncRun) -> dict[str, Any]:
    targets = run.targets_json or []
    current = targets[run.target_index] if run.target_index < len(targets) else None
    return {
        "job_id": run.id, "status": run.status, "targets": targets, "target_count": len(targets),
        "target_index": run.target_index, "current_target": current, "feed": run.feed, "page": run.page,
        "lookback_days": run.lookback_days, "discovered_count": run.discovered_count,
        "imported_count": run.imported_count, "updated_count": run.updated_count,
        "skipped_count": run.skipped_count, "failed_count": run.failed_count,
        "errors": run.errors_json or [], "message": run.message,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }


async def execute_sync_run(
    run_id: str,
    *,
    discovery_client: DiscoveryClient | None = None,
    canonical_client: CanonicalClient | None = None,
) -> None:
    owned_discovery = discovery_client is None
    owned_canonical = canonical_client is None
    with SessionLocal() as db:
        settings = killboard_settings(db)
    discovery = discovery_client or ZkillDiscoveryClient(settings["request_delay_seconds"])
    canonical = canonical_client or EsiClient()
    try:
        await _execute_sync_loop(run_id, discovery, canonical, int(settings["max_pages"]))
    finally:
        if owned_discovery:
            await discovery.close()
        if owned_canonical:
            await canonical.close()


async def _execute_sync_loop(run_id: str, discovery: DiscoveryClient, canonical: CanonicalClient, max_pages: int) -> None:
    with SessionLocal() as db:
        run = db.get(KillboardSyncRun, run_id)
        if run is None:
            return
        if run.status == "complete":
            return
        run.status = "running"
        run.started_at = run.started_at or utc_now()
        run.updated_at = utc_now()
        run.message = "Discovering killmails through zKillboard. Canonical records are fetched from ESI."
        db.commit()

    try:
        while True:
            with SessionLocal() as db:
                run = db.get(KillboardSyncRun, run_id)
                if run is None or run.status == "cancelled":
                    return
                targets = run.targets_json or []
                if run.target_index >= len(targets):
                    run.status = "complete" if run.failed_count == 0 else "complete_with_errors"
                    run.finished_at = utc_now()
                    run.updated_at = run.finished_at
                    run.message = "Killboard synchronization complete."
                    if run.initiated_by_user_id is not None:
                        from app.services.killboard_snapshots import snapshot_killboard_targets

                        user = db.get(User, run.initiated_by_user_id)
                        if user is not None:
                            try:
                                snapshot_killboard_targets(db, user, targets)
                            except Exception as exc:
                                errors = list(run.errors_json or [])
                                errors.append({"message": f"Analytics snapshot failed: {exc}"[:1000], "at": utc_now().isoformat()})
                                run.errors_json = errors[-100:]
                                run.status = "complete_with_errors"
                    db.commit()
                    return
                target = targets[run.target_index]
                target_index, feed, page = run.target_index, run.feed, run.page

            try:
                entries = await discovery.fetch_page(str(target["owner_type"]), int(target["owner_id"]), feed, page)
            except Exception as exc:
                _fail_run(run_id, f"zKillboard discovery failed for {target.get('owner_name')}: {exc}")
                return

            if not entries:
                _advance_cursor(run_id, target_index, feed, page, page_complete=True)
                continue

            known_count = 0
            cutoff_reached = False
            for entry in entries:
                try:
                    killmail_id, killmail_hash = discovery_identity(entry)
                except ValueError as exc:
                    _record_item_failure(run_id, None, str(exc))
                    continue
                with SessionLocal() as db:
                    run = db.get(KillboardSyncRun, run_id)
                    existing = db.get(Killmail, killmail_id)
                    run.discovered_count += 1
                    run.updated_at = utc_now()
                    if existing is not None and existing.killmail_hash == killmail_hash:
                        ensure_discovery(db, killmail_id, str(target["owner_type"]), int(target["owner_id"]), feed)
                        upsert_enrichment(db, killmail_id, entry)
                        run.skipped_count += 1
                        known_count += 1
                        cutoff_reached = existing.killmail_time < utc_now() - timedelta(days=run.lookback_days)
                        db.commit()
                        if cutoff_reached:
                            break
                        continue
                    db.commit()
                try:
                    payload = await canonical.get(f"/killmails/{killmail_id}/{killmail_hash}/")
                    canonical_payload, kill_time, _system_id = validate_canonical_payload(payload)
                    with SessionLocal() as db:
                        run = db.get(KillboardSyncRun, run_id)
                        if kill_time < utc_now() - timedelta(days=run.lookback_days):
                            run.skipped_count += 1
                            run.updated_at = utc_now()
                            db.commit()
                            cutoff_reached = True
                            break
                        with db.begin_nested():
                            _row, created = upsert_killmail(
                                db, killmail_id=killmail_id, killmail_hash=killmail_hash,
                                esi_payload=canonical_payload, zkill_payload=entry,
                                owner_type=str(target["owner_type"]), owner_id=int(target["owner_id"]), feed=feed,
                            )
                            if created:
                                run.imported_count += 1
                            else:
                                run.updated_count += 1
                            run.updated_at = utc_now()
                        db.commit()
                except Exception as exc:
                    _record_item_failure(run_id, killmail_id, f"ESI canonical fetch/import failed: {exc}")

            full_known_page = known_count == len(entries)
            page_complete = cutoff_reached or full_known_page or page >= max_pages
            _advance_cursor(run_id, target_index, feed, page, page_complete=page_complete)
    except Exception as exc:
        _fail_run(run_id, f"Killboard synchronization stopped unexpectedly: {exc}")


def _advance_cursor(run_id: str, target_index: int, feed: str, page: int, *, page_complete: bool) -> None:
    with SessionLocal() as db:
        run = db.get(KillboardSyncRun, run_id)
        if run is None or run.target_index != target_index:
            return
        if not page_complete:
            run.page = page + 1
        elif feed == "kills":
            run.feed = "losses"
            run.page = 1
        else:
            run.target_index += 1
            run.feed = "kills"
            run.page = 1
        run.updated_at = utc_now()
        db.commit()


def _record_item_failure(run_id: str, killmail_id: int | None, message: str) -> None:
    with SessionLocal() as db:
        run = db.get(KillboardSyncRun, run_id)
        if run is None:
            return
        errors = list(run.errors_json or [])
        errors.append({"killmail_id": killmail_id, "message": message[:1000], "at": utc_now().isoformat()})
        run.errors_json = errors[-100:]
        run.failed_count += 1
        run.updated_at = utc_now()
        db.commit()


def _fail_run(run_id: str, message: str) -> None:
    with SessionLocal() as db:
        run = db.get(KillboardSyncRun, run_id)
        if run is None:
            return
        errors = list(run.errors_json or [])
        errors.append({"message": message[:1000], "at": utc_now().isoformat()})
        run.errors_json = errors[-100:]
        run.failed_count += 1
        run.status = "failed"
        run.message = message[:2000]
        run.updated_at = utc_now()
        run.finished_at = run.updated_at
        db.commit()


def start_sync_task(run_id: str) -> bool:
    active = ACTIVE_SYNC_TASKS.get(run_id)
    if active is not None and not active.done():
        return False
    task = asyncio.create_task(execute_sync_run(run_id))
    ACTIVE_SYNC_TASKS[run_id] = task
    task.add_done_callback(lambda _task: ACTIVE_SYNC_TASKS.pop(run_id, None))
    return True
