from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import EveConstellation, EveRegion, EveSystem, EveType
from app.services.esi_client import EsiClient


QUANTITY_FIRST_RE = re.compile(r"^\s*(?P<quantity>\d[\d,]*)\s*x?\s*(?P<name>.+?)\s*$", re.IGNORECASE)
QUANTITY_LAST_RE = re.compile(r"^\s*(?P<name>.+?)\s+(?:x\s*)?(?P<quantity>\d[\d,]*)\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class MarketHub:
    key: str
    label: str
    region_id: int | None = None
    location_id: int | None = None
    system_name: str | None = None
    npc_group: bool = False


TRADE_HUBS: dict[str, MarketHub] = {
    "jita": MarketHub("jita", "Jita 4-4", region_id=10000002, location_id=60003760),
    "amarr": MarketHub("amarr", "Amarr", region_id=10000043, location_id=60008494),
    "hek": MarketHub("hek", "Hek", region_id=10000042, location_id=60005686),
    "dodixie": MarketHub("dodixie", "Dodixie", region_id=10000032, location_id=60011866),
    "rens": MarketHub("rens", "Rens", region_id=10000030, location_id=60004588),
    "c-n4od": MarketHub("c-n4od", "C-N4OD", system_name="C-N4OD"),
    "npc": MarketHub("npc", "NPC", npc_group=True),
    "dudreda": MarketHub("dudreda", "Dudreda", system_name="Dudreda"),
}

NPC_GROUP_KEYS = ("jita", "amarr", "hek", "dodixie", "rens")

STATIC_REGION_NAMES = {
    10000002: "The Forge",
    10000043: "Domain",
    10000042: "Metropolis",
    10000032: "Sinq Laison",
    10000030: "Heimatar",
}


def normalize_type_name(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value.strip().casefold())
    return normalized.replace("nullfier", "nullifier")


def parse_market_line(raw_line: str) -> dict[str, Any] | None:
    line = raw_line.strip()
    if not line:
        return None
    line = re.sub(r"\s+", " ", line.replace("\t", " "))

    for pattern in (QUANTITY_FIRST_RE, QUANTITY_LAST_RE):
        match = pattern.match(line)
        if match:
            quantity = int(match.group("quantity").replace(",", ""))
            name = match.group("name").strip()
            if quantity > 0 and name:
                return {"input": raw_line, "name": name, "quantity": quantity}

    return {"input": raw_line, "name": line, "quantity": 1}


def parse_market_lines(text: str) -> list[dict[str, Any]]:
    parsed = [parse_market_line(line) for line in text.splitlines()]
    return [line for line in parsed if line is not None]


def type_candidates(db: Session, name: str) -> list[EveType]:
    normalized = normalize_type_name(name)
    exact = db.scalars(select(EveType).where(EveType.name.ilike(name))).all()
    exact_matches = [item for item in exact if normalize_type_name(item.name) == normalized]
    if exact_matches:
        return sorted(exact_matches, key=lambda item: (not item.published, len(item.name), item.name))

    terms = [term for term in re.split(r"\s+", normalized) if term]
    if not terms:
        return []
    query = select(EveType)
    for term in terms:
        query = query.where(EveType.name.ilike(f"%{term}%"))
    return db.scalars(query.order_by(EveType.published.desc(), EveType.name).limit(8)).all()


def region_name_for_id(db: Session, region_id: int | None) -> str | None:
    if region_id is None:
        return None
    region = db.get(EveRegion, region_id)
    return region.name if region else STATIC_REGION_NAMES.get(region_id)


def region_for_system(db: Session, system_name: str) -> tuple[int | None, int | None, str | None]:
    system = db.scalar(
        select(EveSystem)
        .options(selectinload(EveSystem.constellation).selectinload(EveConstellation.region))
        .where(EveSystem.name.ilike(system_name))
        .limit(1)
    )
    if system is None:
        return None, None, None
    constellation = system.constellation
    region = constellation.region if constellation else None
    region_id = region.region_id if region else (constellation.region_id if constellation else None)
    return system.system_id, region_id, region.name if region else region_name_for_id(db, region_id)


def hub_payload(db: Session, hub: MarketHub) -> dict[str, Any]:
    system_id = None
    region_id = hub.region_id
    region_name = region_name_for_id(db, region_id)
    if hub.system_name:
        system_id, region_id, region_name = region_for_system(db, hub.system_name)
    return {
        "key": hub.key,
        "label": hub.label,
        "region_id": region_id,
        "location_id": hub.location_id,
        "system_id": system_id,
        "system_name": hub.system_name,
        "npc_group": hub.npc_group,
        "available": hub.npc_group or region_id is not None,
    }


def list_market_hubs(db: Session) -> list[dict[str, Any]]:
    return [hub_payload(db, hub) for hub in TRADE_HUBS.values()]


def order_applies_to_hub(order: dict[str, Any], hub: dict[str, Any]) -> bool:
    location_id = hub.get("location_id")
    system_id = hub.get("system_id")
    if location_id is not None:
        return int(order.get("location_id") or 0) == int(location_id)
    if system_id is not None:
        return int(order.get("system_id") or 0) == int(system_id)
    return False


def summarize_orders(orders: list[dict[str, Any]], quantity: int) -> dict[str, Any]:
    sell_orders = sorted((order for order in orders if not order.get("is_buy_order")), key=lambda order: float(order.get("price") or 0))
    buy_orders = sorted((order for order in orders if order.get("is_buy_order")), key=lambda order: float(order.get("price") or 0), reverse=True)

    sell_price = float(sell_orders[0]["price"]) if sell_orders else None
    buy_price = float(buy_orders[0]["price"]) if buy_orders else None
    split_price = (buy_price + sell_price) / 2 if buy_price is not None and sell_price is not None else None
    return {
        "buy": buy_price,
        "sell": sell_price,
        "split": split_price,
        "buy_total": buy_price * quantity if buy_price is not None else None,
        "sell_total": sell_price * quantity if sell_price is not None else None,
        "split_total": split_price * quantity if split_price is not None else None,
        "buy_orders": len(buy_orders),
        "sell_orders": len(sell_orders),
    }


async def fetch_region_orders(region_id: int, type_id: int) -> list[dict[str, Any]]:
    client = EsiClient()
    orders: list[dict[str, Any]] = []
    page = 1
    while page <= 10:
        payload, headers = await client.get_with_headers(f"/markets/{region_id}/orders/", params={"type_id": type_id, "order_type": "all", "page": page})
        orders.extend(payload or [])
        total_pages = int(headers.get("x-pages", "1"))
        if page >= total_pages:
            break
        page += 1
    return orders


async def appraise_market(db: Session, text: str, hub_keys: list[str] | None = None) -> dict[str, Any]:
    lines = parse_market_lines(text)
    if not lines:
        raise HTTPException(status_code=400, detail="Paste at least one item line.")
    if len(lines) > 50:
        raise HTTPException(status_code=400, detail="Please appraise 50 item lines or fewer at a time.")

    selected_keys = hub_keys or ["jita", "amarr", "hek", "dodixie", "rens", "dudreda"]
    selected_hubs = [TRADE_HUBS[key] for key in selected_keys if key in TRADE_HUBS]
    if not selected_hubs:
        raise HTTPException(status_code=400, detail="Select at least one market hub.")

    hub_rows = {hub.key: hub_payload(db, hub) for hub in selected_hubs}
    expanded_hub_rows: dict[str, list[dict[str, Any]]] = {}
    for hub in selected_hubs:
        if hub.npc_group:
            expanded_hub_rows[hub.key] = [hub_payload(db, TRADE_HUBS[key]) for key in NPC_GROUP_KEYS]
        else:
            expanded_hub_rows[hub.key] = [hub_rows[hub.key]]

    resolved_items: list[dict[str, Any]] = []
    for line in lines:
        candidates = type_candidates(db, line["name"])
        chosen = candidates[0] if candidates else None
        resolved_items.append({
            **line,
            "type_id": chosen.type_id if chosen else None,
            "type_name": chosen.name if chosen else None,
            "matched": chosen is not None,
            "ambiguous_matches": [{"type_id": item.type_id, "name": item.name} for item in candidates[1:5]],
            "hubs": {},
        })

    order_cache: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for item in resolved_items:
        if item["type_id"] is None:
            continue
        type_id = int(item["type_id"])
        for hub_key, targets in expanded_hub_rows.items():
            candidate_summaries: list[dict[str, Any]] = []
            for target in targets:
                region_id = target.get("region_id")
                if region_id is None:
                    continue
                cache_key = (int(region_id), type_id)
                if cache_key not in order_cache:
                    order_cache[cache_key] = await fetch_region_orders(int(region_id), type_id)
                filtered = [order for order in order_cache[cache_key] if order_applies_to_hub(order, target)]
                summary = summarize_orders(filtered, int(item["quantity"]))
                candidate_summaries.append({"hub": target, **summary})

            best_buy = max((row for row in candidate_summaries if row["buy"] is not None), key=lambda row: row["buy"], default=None)
            best_sell = min((row for row in candidate_summaries if row["sell"] is not None), key=lambda row: row["sell"], default=None)
            buy = best_buy["buy"] if best_buy else None
            sell = best_sell["sell"] if best_sell else None
            split = (buy + sell) / 2 if buy is not None and sell is not None else None
            item["hubs"][hub_key] = {
                "buy": buy,
                "sell": sell,
                "split": split,
                "buy_total": buy * int(item["quantity"]) if buy is not None else None,
                "sell_total": sell * int(item["quantity"]) if sell is not None else None,
                "split_total": split * int(item["quantity"]) if split is not None else None,
                "buy_orders": sum(row["buy_orders"] for row in candidate_summaries),
                "sell_orders": sum(row["sell_orders"] for row in candidate_summaries),
                "buy_source": best_buy["hub"]["label"] if best_buy else None,
                "sell_source": best_sell["hub"]["label"] if best_sell else None,
            }

    totals: dict[str, dict[str, float]] = {}
    for hub in selected_hubs:
        totals[hub.key] = {"buy_total": 0.0, "sell_total": 0.0, "split_total": 0.0}
        for item in resolved_items:
            hub_value = item["hubs"].get(hub.key, {})
            for key in ("buy_total", "sell_total", "split_total"):
                if hub_value.get(key) is not None:
                    totals[hub.key][key] += float(hub_value[key])

    return {
        "hubs": [hub_rows[hub.key] for hub in selected_hubs],
        "items": resolved_items,
        "totals": totals,
        "unmatched_count": sum(1 for item in resolved_items if not item["matched"]),
    }


