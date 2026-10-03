from datetime import datetime, timezone
from decimal import Decimal

from app.services.hypernet import money


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def market_sale_values(offer):
    """An expired listing and its eventual sale form one realized item result."""
    sale = offer.market_sale
    if not sale:
        return None
    gross = Decimal(sale["gross_proceeds"])
    tax = Decimal(sale["sales_tax"])
    broker = Decimal(sale["broker_fee"])
    other = Decimal(sale["other_fees"])
    cores = offer.actual_hypercore_cost if offer.actual_hypercore_cost is not None else offer.hypercores_required * offer.hypercore_unit_cost
    net = money(gross - tax - broker - other)
    return {"gross_proceeds": gross, "sales_tax": tax, "broker_fee": broker, "other_fees": other,
            "net_proceeds": net, "acquisition_cost": money(offer.acquisition_cost), "hypercore_cost": money(cores),
            "lifecycle_profit": money(net - offer.acquisition_cost - cores)}


def serialize_market_sale(offer):
    values = market_sale_values(offer)
    if values is None:
        return None
    return {"sold_at": offer.market_sale["sold_at"], "note": offer.market_sale.get("note"),
            **{key: float(value) for key, value in values.items()}}


def realized_item_result(offer):
    values = market_sale_values(offer)
    return values["lifecycle_profit"] if values is not None else offer.final_profit or Decimal("0")
