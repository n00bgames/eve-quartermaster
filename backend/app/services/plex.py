"""FIFO personal inventory; unknown acquisition costs never count as zero."""
from collections import deque
from datetime import datetime, timezone
from decimal import Decimal, localcontext

import httpx
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.plex import PlexMarketCache
from app.services.esi_client import EsiClient

PLEX_TYPE_ID = 44992
PLEX_REGION_ID = 19000001


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def number(value):
    return float(value.quantize(Decimal("0.01"))) if value is not None else None


def ledger(rows):
    with localcontext() as context:
        context.prec = 50
        return _ledger(rows)


def _ledger(rows):
    lots = deque()
    transactions = []
    realized = Decimal(0)
    unknown_sales = 0
    cash_flow = Decimal(0)
    consumed = 0
    for row in sorted(rows, key=lambda r: (utc(r.occurred_at), r.id or 2**63)):
        price = Decimal(row.unit_price) if row.unit_price is not None else None
        fees = Decimal(row.fees)
        profit = None
        basis = None
        if row.kind in {"buy", "opening"}:
            basis = price * row.quantity + fees if price is not None else None
            lots.append([row.quantity, basis / row.quantity if basis is not None else None])
            if row.kind == "buy":
                cash_flow -= basis
        else:
            left = row.quantity
            basis = Decimal(0)
            unknown = False
            while left and lots:
                qty, cost = lots[0]
                used = min(qty, left)
                unknown |= cost is None
                if cost is not None:
                    basis += cost * used
                left -= used
                lots[0][0] -= used
                if not lots[0][0]:
                    lots.popleft()
            if left:
                raise ValueError("This change would sell or spend more PLEX than held at that date. Add earlier holdings first.")
            if unknown:
                basis = None
            if row.kind == "sell":
                proceeds = price * row.quantity - fees
                cash_flow += proceeds
                if basis is None:
                    unknown_sales += 1
                else:
                    profit = proceeds - basis
                    realized += profit
            else:
                consumed += row.quantity
        transactions.append({"id": row.id, "occurred_at": utc(row.occurred_at).isoformat(),
                             "kind": row.kind, "quantity": row.quantity, "unit_price": number(price),
                             "fees": number(fees), "note": row.note, "cost_basis": number(basis),
                             "realized_profit": number(profit)})
    quantity = sum(q for q, _ in lots)
    unknown_quantity = sum(q for q, cost in lots if cost is None)
    known_basis = sum((q * cost for q, cost in lots if cost is not None), Decimal(0))
    basis = None if unknown_quantity else known_basis
    return {"transactions": list(reversed(transactions)), "quantity": quantity,
            "unknown_cost_quantity": unknown_quantity, "cost_basis": number(basis),
            "known_cost_basis": number(known_basis), "average_cost": number(basis / quantity) if basis is not None and quantity else None,
            "realized_profit": number(realized) if not unknown_sales else None,
            "known_realized_profit": number(realized), "unknown_cost_sales": unknown_sales,
            "trade_cash_flow": number(cash_flow), "consumed_quantity": consumed}


def summarize_orders(orders):
    active = [r for r in orders if r.get("type_id") == PLEX_TYPE_ID and r.get("volume_remain", 0) > 0 and r.get("price", 0) > 0]
    bids = [r for r in active if r["is_buy_order"]]
    asks = [r for r in active if not r["is_buy_order"]]
    bid = max((r["price"] for r in bids), default=None)
    ask = min((r["price"] for r in asks), default=None)
    return {"best_bid": bid, "best_ask": ask,
            "spread": ask - bid if bid is not None and ask is not None else None,
            "buy_volume": sum(r["volume_remain"] for r in bids), "sell_volume": sum(r["volume_remain"] for r in asks),
            "best_bid_volume": sum(r["volume_remain"] for r in bids if r["price"] == bid),
            "best_ask_volume": sum(r["volume_remain"] for r in asks if r["price"] == ask)}


async def market_data(db: Session, key="orders"):
    now = datetime.now(timezone.utc)
    cached = db.get(PlexMarketCache, key)
    ttl = 300 if key == "orders" else 3600
    if cached and (now - utc(cached.fetched_at)).total_seconds() < ttl:
        return {**cached.payload, "fetched_at": utc(cached.fetched_at).isoformat(), "stale": False}
    client = EsiClient()
    try:
        if key == "orders":
            payload = summarize_orders(await client.get_public_market_orders(PLEX_REGION_ID, PLEX_TYPE_ID))
        else:
            history = await client.get(f"/markets/{PLEX_REGION_ID}/history/", params={"type_id": PLEX_TYPE_ID})
            if not isinstance(history, list):
                raise ValueError("Invalid history response")
            payload = {"history": sorted(history, key=lambda r: r["date"])[-90:]}
    except (HTTPException, httpx.HTTPError, ValueError, KeyError, TypeError):
        if cached:
            return {**cached.payload, "fetched_at": utc(cached.fetched_at).isoformat(), "stale": True,
                    "warning": "ESI is unavailable. Showing the last successful snapshot."}
        raise HTTPException(503, "PLEX market data is temporarily unavailable from ESI. Your ledger is still available.") from None
    finally:
        await client.close()
    if cached:
        cached.fetched_at, cached.payload = now, payload
    else:
        db.add(PlexMarketCache(key=key, fetched_at=now, payload=payload))
    try:
        db.commit()
    except IntegrityError:
        # Another worker may populate the shared cache first.
        db.rollback()
    return {**payload, "fetched_at": now.isoformat(), "stale": False}
