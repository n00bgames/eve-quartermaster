from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field, model_validator


class PlexTransactionInput(BaseModel):
    occurred_at: AwareDatetime
    kind: Literal["buy", "opening", "sell", "consume"]
    quantity: int = Field(gt=0, le=1_000_000_000, strict=True)
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=2)
    fees: Decimal = Field(default=Decimal(0), ge=0, max_digits=20, decimal_places=2)
    note: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def validate_transaction(self):
        if self.occurred_at > datetime.now(timezone.utc):
            raise ValueError("Record completed transactions, not future orders.")
        if self.kind in {"buy", "sell"} and (self.unit_price is None or self.unit_price <= 0):
            raise ValueError("Purchases and sales require a positive ISK price per PLEX.")
        if self.kind == "consume" and (self.unit_price is not None or self.fees != 0):
            raise ValueError("Consumption removes PLEX at its tracked cost; omit price and fees.")
        return self
