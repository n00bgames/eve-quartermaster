"""ESI order snapshots with finite depth. No optimistic tail extrapolation."""
from __future__ import annotations

import asyncio
import math
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Callable

from app.services.esi_client import EsiClient
from app.services.market import TRADE_HUBS

_CACHE: dict[tuple[str, int], dict] = {}
_MAX_CACHE = 500


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def fetch_book(client: EsiClient, hub_key: str, type_id: int) -> dict:
    hub = TRADE_HUBS[hub_key]
    key = (hub_key, type_id)
    now = utcnow()
    cached = _CACHE.get(key)
    if cached and datetime.fromisoformat(cached["expires_at"]) > now:
        return cached
    orders, expiries, seen = [], [], set()
    page, pages = 1, None
    while pages is None or page <= pages:
        payload, headers = await client.get_with_headers(f"/markets/{hub.region_id}/orders/", params={"order_type": "all", "type_id": type_id, "page": page})
        headers = {str(k).lower(): v for k, v in headers.items()}
        count = int(headers.get("x-pages", "1"))
        if count < 1 or count > 100 or (pages is not None and pages != count):
            raise ValueError("ESI market pages changed or exceeded the snapshot limit; retry")
        pages = count
        if not isinstance(payload, list) or (not payload and pages > 1):
            raise ValueError("Incomplete ESI market snapshot")
        if headers.get("expires"):
            expiry = parsedate_to_datetime(headers["expires"])
            expiries.append(expiry if expiry.tzinfo else expiry.replace(tzinfo=timezone.utc))
        for order in payload:
            order_id = int(order["order_id"])
            if order_id in seen:
                raise ValueError("ESI order appeared on multiple pages; retry for a consistent snapshot")
            seen.add(order_id)
            # Conservative station scope. Remote ranged bids are intentionally excluded.
            if order.get("location_id") != hub.location_id or int(order.get("type_id", type_id)) != type_id:
                continue
            price, volume = float(order["price"]), int(order["volume_remain"])
            if not math.isfinite(price) or price <= 0 or volume <= 0:
                continue
            if order.get("issued") and order.get("duration"):
                issued = datetime.fromisoformat(order["issued"].replace("Z", "+00:00"))
                if issued + timedelta(days=order["duration"]) <= now:
                    continue
            orders.append({"order_id": order_id, "price": price, "volume": volume, "minimum": max(1, int(order.get("min_volume", 1))), "buy": bool(order["is_buy_order"])})
        page += 1
    expires = min(expiries) if expiries else now + timedelta(minutes=5)
    result = {"type_id": type_id, "hub": hub_key, "station_id": hub.location_id, "region_id": hub.region_id, "fetched_at": now.isoformat(), "expires_at": expires.isoformat(), "source": "ESI public regional orders, selected station only", "complete": True, "bids": sorted((o for o in orders if o["buy"]), key=lambda o: (-o["price"], o["order_id"])), "asks": sorted((o for o in orders if not o["buy"]), key=lambda o: (o["price"], o["order_id"]))}
    if len(_CACHE) >= _MAX_CACHE:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = result
    return result


async def market_snapshot(type_ids: set[int], hub: str, progress: Callable | None = None, cancelled: Callable | None = None) -> dict:
    semaphore = asyncio.Semaphore(4)
    books, errors = {}, {}
    done = 0
    client = EsiClient()

    async def load(type_id):
        nonlocal done
        async with semaphore:
            if cancelled and cancelled():
                return
            try:
                books[type_id] = await fetch_book(client, hub, type_id)
            except Exception as exc:
                # Do not include upstream response bodies, tokens, or arbitrary exception reprs.
                errors[type_id] = str(exc) if isinstance(exc, ValueError) else "ESI quote unavailable; retry later"
            done += 1
            if progress:
                progress(done, len(type_ids))

    await asyncio.wait_for(asyncio.gather(*(load(t) for t in sorted(type_ids))), timeout=120)
    return {"hub": hub, "fetched_at": utcnow().isoformat(), "books": books, "errors": errors}


def fill(orders: list[dict], quantity: float, *, buying: bool) -> dict:
    """Integer market units; a partially filled order may sell its remaining minimum."""
    remaining = max(0, math.ceil(quantity - 1e-8))
    requested = remaining
    value = 0.0
    fills = []
    for order in sorted(orders, key=lambda x: (x["price"] if buying else -x["price"], x.get("order_id", 0))):
        available = max(0, math.floor(order["volume"]))
        take = min(remaining, available)
        minimum = min(available, max(1, int(order.get("minimum", 1))))
        if take < minimum:
            continue
        if take:
            value += take * order["price"]
            fills.append({"order_id": order.get("order_id"), "quantity": take, "price": order["price"]})
            remaining -= take
        if not remaining:
            break
    return {"requested": requested, "filled": requested - remaining, "unfilled": remaining, "value": round(value, 2), "average_price": value / (requested - remaining) if requested > remaining else None, "fills": fills}


def quote(book: dict | None, quantity: float, *, buying: bool, patient: bool = False) -> dict:
    if not book or not book.get("complete"):
        return {"requested": quantity, "filled": 0, "unfilled": quantity, "value": 0, "average_price": None, "fills": [], "status": "missing"}
    if patient and not buying:
        asks = book.get("asks", [])
        if not asks:
            return {**fill([], quantity, buying=False), "status": "missing_ask"}
        price = min(o["price"] for o in asks)
        return {"requested": quantity, "filled": 0, "unfilled": quantity, "value": quantity * price, "average_price": price, "fills": [], "status": "patient_estimate"}
    result = fill(book.get("asks" if buying else "bids", []), quantity, buying=buying)
    return {**result, "status": "full" if not result["unfilled"] else "insufficient_depth"}
