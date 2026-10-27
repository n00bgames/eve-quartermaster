from datetime import datetime, timezone
from decimal import Decimal

from app.services.hypernet import FEE_RATE, money


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def market_sale_values(offer):
    """An ended listing and its retained item's sale form one cash result."""
    sale = offer.market_sale
    if not sale:
        return None
    gross = Decimal(sale["gross_proceeds"])
    tax = Decimal(sale["sales_tax"])
    broker = Decimal(sale["broker_fee"])
    other = Decimal(sale["other_fees"])
    cores = offer.actual_hypercore_cost if offer.actual_hypercore_cost is not None else offer.hypercores_required * offer.hypercore_unit_cost
    net = money(gross - tax - broker - other)
    completed = offer.status == "completed"
    payout = money(offer.payout if offer.payout is not None else offer.total_offer_price * (Decimal("1") - FEE_RATE)) if completed else Decimal("0")
    seeded = money(offer.seller_owned_nodes * (offer.total_offer_price / offer.total_nodes)) if completed else Decimal("0")
    return {"gross_proceeds": gross, "sales_tax": tax, "broker_fee": broker, "other_fees": other,
            "net_proceeds": net, "acquisition_cost": money(offer.acquisition_cost), "hypercore_cost": money(cores),
            "hypernet_payout": payout, "seeded_node_spend": seeded,
            "lifecycle_profit": money(payout + net - offer.acquisition_cost - cores - seeded)}


def serialize_market_sale(offer):
    values = market_sale_values(offer)
    if values is None:
        return None
    return {"sold_at": offer.market_sale["sold_at"], "note": offer.market_sale.get("note"),
            **{key: float(value) for key, value in values.items()}}


def realized_item_result(offer):
    values = market_sale_values(offer)
    return values["lifecycle_profit"] if values is not None else offer.final_profit or Decimal("0")
