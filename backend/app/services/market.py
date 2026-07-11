from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.models import CustomMarketHub, EveConstellation, EveRegion, EveSystem, EveType
from app.services.esi_client import EsiClient

QUANTITY_FIRST_RE = re.compile(r"^\s*(?P<qty>\d[\d,]*)\s*x?\s+(?P<name>.+?)\s*$", re.IGNORECASE)
QUANTITY_LAST_RE = re.compile(r"^\s*(?P<name>.+?)\s+(?:x\s*)?(?P<qty>\d[\d,]*)\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class MarketHub:
    key: str
    label: str
    region_id: int | None = None
    location_id: int | None = None
    system_name: str | None = None
    npc_group: bool = False
    custom: bool = False


TRADE_HUBS: dict[str, MarketHub] = {
    "jita": MarketHub("jita", "Jita 4-4", region_id=10000002, location_id=60003760),
    "amarr": MarketHub("amarr", "Amarr", region_id=10000043, location_id=60008494),
    "hek": MarketHub("hek", "Hek", region_id=10000042, location_id=60005686),
    "dodixie": MarketHub("dodixie", "Dodixie", region_id=10000032, location_id=60011866),
    "rens": MarketHub("rens", "Rens", region_id=10000030, location_id=60004588),
    "c-n4od": MarketHub("c-n4od", "C-N4OD", system_name="C-N4OD"),
    "npc": MarketHub("npc", "NPC", npc_group=True),
}
DEFAULT_HUB_KEYS = ["jita", "amarr", "hek", "dodixie", "rens"]
NPC_GROUP_KEYS = ("jita", "amarr", "hek", "dodixie", "rens")
STATIC_REGION_NAMES = {
    10000002: "The Forge",
    10000030: "Heimatar",
    10000032: "Sinq Laison",
    10000042: "Metropolis",
    10000043: "Domain",
}


def parse_appraisal_lines(text: str) -> list[dict[str, Any]]:
    parsed: dict[str, int] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        qty = 1
        name = line
        first = QUANTITY_FIRST_RE.match(line)
        last = QUANTITY_LAST_RE.match(line)
        if first:
            qty = int(first.group("qty").replace(",", ""))
            name = first.group("name").strip()
        elif last:
            qty = int(last.group("qty").replace(",", ""))
            name = last.group("name").strip()
        key = re.sub(r"\s+", " ", name).casefold()
        parsed[key] = parsed.get(key, 0) + qty
    return [{"name": name, "quantity": quantity} for name, quantity in parsed.items()]


def slugify_hub_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "hub"


def custom_hub_from_row(row: CustomMarketHub) -> MarketHub:
    return MarketHub(row.key, row.label, system_name=row.system_name, custom=True)


def custom_market_hubs(db: Session) -> list[CustomMarketHub]:
    try:
        return list(db.scalars(select(CustomMarketHub).order_by(CustomMarketHub.label)).all())
    except SQLAlchemyError:
        db.rollback()
        return []


def all_trade_hubs(db: Session) -> dict[str, MarketHub]:
    hubs = dict(TRADE_HUBS)
    for row in custom_market_hubs(db):
        hubs[row.key] = custom_hub_from_row(row)
    return hubs


def resolve_system_region(db: Session, system_name: str | None) -> tuple[int | None, str | None, int | None]:
    if not system_name:
        return None, None, None
    system = db.scalar(
        select(EveSystem)
        .options(selectinload(EveSystem.constellation).selectinload(EveConstellation.region))
        .where(EveSystem.name.ilike(system_name))
        .limit(1)
    )
    if system is None or system.constellation is None or system.constellation.region is None:
        return None, None, None
    return system.constellation.region.region_id, system.constellation.region.name, system.system_id


def hub_region_name(db: Session, region_id: int | None) -> str | None:
    if region_id is None:
        return None
    region = db.get(EveRegion, region_id)
    if region:
        return region.name
    return STATIC_REGION_NAMES.get(region_id)


def hub_payload(db: Session, hub: MarketHub) -> dict[str, Any]:
    region_id = hub.region_id
    region_name = hub_region_name(db, region_id)
    system_id = None
    if hub.system_name:
        region_id, region_name, system_id = resolve_system_region(db, hub.system_name)
    return {
        "key": hub.key,
        "label": hub.label,
        "region_id": region_id,
        "region_name": region_name,
        "location_id": hub.location_id,
        "system_id": system_id,
        "system_name": hub.system_name,
        "npc_group": hub.npc_group,
        "custom": hub.custom,
        "available": hub.npc_group or region_id is not None,
    }


def list_market_hubs(db: Session) -> list[dict[str, Any]]:
    return [hub_payload(db, hub) for hub in all_trade_hubs(db).values()]


def create_custom_market_hub(db: Session, label: str, system_name: str) -> dict[str, Any]:
    label = re.sub(r"\s+", " ", (label or "").strip())
    system_name = re.sub(r"\s+", " ", (system_name or "").strip())
    if not label or not system_name:
        raise HTTPException(status_code=400, detail="Custom hubs need both a label and a solar system.")
    if len(label) > 120 or len(system_name) > 120:
        raise HTTPException(status_code=400, detail="Custom hub label and system name must be 120 characters or fewer.")

    system = db.scalar(select(EveSystem).where(EveSystem.name.ilike(system_name)).limit(1))
    if system is None:
        raise HTTPException(status_code=400, detail="That solar system is not in the imported SDE yet.")

    try:
        existing = db.scalar(select(CustomMarketHub).where(CustomMarketHub.label == label, CustomMarketHub.system_name == system.name).limit(1))
        if existing is not None:
            return hub_payload(db, custom_hub_from_row(existing))

        base_key = f"custom-{slugify_hub_key(label)}"
        key = base_key
        suffix = 2
        while key in TRADE_HUBS or db.scalar(select(CustomMarketHub).where(CustomMarketHub.key == key)) is not None:
            key = f"{base_key}-{suffix}"
            suffix += 1

        row = CustomMarketHub(key=key, label=label, system_name=system.name)
        db.add(row)
        db.commit()
        db.refresh(row)
        return hub_payload(db, custom_hub_from_row(row))
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="Custom market hubs are unavailable until database migrations finish.") from None


def delete_custom_market_hub(db: Session, key: str) -> dict[str, Any]:
    try:
        row = db.scalar(select(CustomMarketHub).where(CustomMarketHub.key == key))
        if row is None:
            raise HTTPException(status_code=404, detail="Custom market hub not found.")
        db.delete(row)
        db.commit()
        return {"status": "deleted", "key": key}
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="Custom market hubs are unavailable until database migrations finish.") from None


def best_prices_from_orders(orders: list[dict[str, Any]]) -> dict[str, Any]:
    buy_orders = [order for order in orders if order.get("is_buy_order")]
    sell_orders = [order for order in orders if not order.get("is_buy_order")]
    best_buy = max((float(order.get("price") or 0) for order in buy_orders), default=0)
    best_sell = min((float(order.get("price") or 0) for order in sell_orders), default=0)
    split = (best_buy + best_sell) / 2 if best_buy and best_sell else best_buy or best_sell
    return {
        "buy": best_buy,
        "sell": best_sell,
        "split": split,
        "buy_orders": len(buy_orders),
        "sell_orders": len(sell_orders),
    }


EMPTY_MARKET_PRICES = {"buy": 0.0, "sell": 0.0, "split": 0.0, "buy_orders": 0, "sell_orders": 0}


async def best_prices_for_market_item(
    client: EsiClient,
    region_id: int,
    type_id: int,
    location_id: int | None = None,
) -> dict[str, Any]:
    try:
        orders = await client.get_public_market_orders(region_id, type_id)
    except Exception:
        return dict(EMPTY_MARKET_PRICES)
    if location_id:
        orders = [order for order in orders if int(order.get("location_id") or 0) == location_id]
    return best_prices_from_orders(orders)


def resolve_types(db: Session, lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    for line in lines:
        name = line["name"]
        item = db.scalar(select(EveType).where(EveType.name.ilike(name)).limit(1))
        if item is None:
            item = db.scalar(select(EveType).where(EveType.name.ilike(f"%{name}%")).limit(1))
        resolved.append({**line, "type_id": item.type_id if item else None, "type_name": item.name if item else name, "resolved": item is not None})
    return resolved


async def appraise_market(db: Session, text: str, hub_keys: list[str] | None = None) -> dict[str, Any]:
    lines = parse_appraisal_lines(text)
    if not lines:
        raise HTTPException(status_code=400, detail="Paste at least one item line to appraise.")
    items = resolve_types(db, lines)
    hub_map = all_trade_hubs(db)
    selected_keys = hub_keys or DEFAULT_HUB_KEYS
    selected_hubs = [hub_map[key] for key in selected_keys if key in hub_map]
    client = EsiClient()
    try:
        hub_payloads: dict[str, Any] = {}
        for hub in selected_hubs:
            if hub.npc_group:
                continue
            payload = hub_payload(db, hub)
            if not payload["available"] or payload["region_id"] is None:
                hub_payloads[hub.key] = {**payload, "items": {}, "totals": {"buy": 0, "sell": 0, "split": 0}}
                continue
            item_prices: dict[int, Any] = {}
            for item in items:
                if not item["type_id"]:
                    continue
                prices = await best_prices_for_market_item(client, int(payload["region_id"]), int(item["type_id"]), hub.location_id)
                item_prices[int(item["type_id"])] = prices
            hub_payloads[hub.key] = {**payload, "items": item_prices}

        if any(hub.npc_group for hub in selected_hubs):
            npc_items: dict[int, Any] = {}
            for item in items:
                if not item["type_id"]:
                    continue
                candidates = [hub_payloads[key]["items"].get(int(item["type_id"])) for key in NPC_GROUP_KEYS if key in hub_payloads]
                candidates = [candidate for candidate in candidates if candidate]
                if not candidates:
                    continue
                npc_items[int(item["type_id"])] = {
                    "buy": max((candidate["buy"] for candidate in candidates), default=0),
                    "sell": min((candidate["sell"] for candidate in candidates if candidate["sell"]), default=0),
                    "split": max((candidate["split"] for candidate in candidates), default=0),
                    "buy_orders": sum(candidate["buy_orders"] for candidate in candidates),
                    "sell_orders": sum(candidate["sell_orders"] for candidate in candidates),
                }
            hub_payloads["npc"] = {**hub_payload(db, TRADE_HUBS["npc"]), "items": npc_items}

        for key, payload in hub_payloads.items():
            totals = {"buy": 0.0, "sell": 0.0, "split": 0.0}
            for item in items:
                if not item["type_id"]:
                    continue
                prices = payload["items"].get(int(item["type_id"]))
                if not prices:
                    continue
                quantity = int(item["quantity"])
                totals["buy"] += prices["buy"] * quantity
                totals["sell"] += prices["sell"] * quantity
                totals["split"] += prices["split"] * quantity
            payload["totals"] = totals

        appraisal_items: list[dict[str, Any]] = []
        for item in items:
            quantity = int(item["quantity"])
            item_hubs: dict[str, Any] = {}
            if item["type_id"]:
                type_id = int(item["type_id"])
                for key, payload in hub_payloads.items():
                    prices = payload["items"].get(type_id, dict(EMPTY_MARKET_PRICES))
                    item_hubs[key] = {
                        **prices,
                        "buy_total": (prices.get("buy") or 0) * quantity,
                        "sell_total": (prices.get("sell") or 0) * quantity,
                        "split_total": (prices.get("split") or 0) * quantity,
                    }
            appraisal_items.append(
                {
                    "input": item["name"],
                    "name": item["name"],
                    "quantity": quantity,
                    "type_id": item["type_id"],
                    "type_name": item["type_name"],
                    "matched": item["resolved"],
                    "ambiguous_matches": [],
                    "hubs": item_hubs,
                }
            )

        appraisal_hubs = [
            {field: value for field, value in payload.items() if field not in {"items", "totals"}}
            for payload in hub_payloads.values()
        ]
        appraisal_totals = {
            key: {
                "buy_total": payload["totals"]["buy"],
                "sell_total": payload["totals"]["sell"],
                "split_total": payload["totals"]["split"],
            }
            for key, payload in hub_payloads.items()
        }

        return {
            "items": appraisal_items,
            "hubs": appraisal_hubs,
            "totals": appraisal_totals,
            "unmatched_count": sum(1 for item in items if not item["resolved"]),
        }
    finally:
        await client.close()

