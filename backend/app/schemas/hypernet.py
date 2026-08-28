from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


HyperNetStatus = Literal[
    "draft",
    "active",
    "completed",
    "expired",
    "cancelled",
    "invalid",
    "awaiting_reconciliation",
]
OfferWinner = Literal["external", "seller", "unknown"]


def require_aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone")
    return value


class HyperNetCalculatorRequest(BaseModel):
    total_offer_price: Decimal = Field(ge=0)
    total_nodes: int = Field(gt=0, le=512)
    hypercores_required: int = Field(ge=0)
    hypercore_unit_cost: Decimal = Field(default=0, ge=0)
    acquisition_cost: Decimal = Field(default=0, ge=0)
    desired_profit: Decimal = Field(default=0)
    jita_sell: Decimal | None = Field(default=None, ge=0)
    local_sell: Decimal | None = Field(default=None, ge=0)
    seller_owned_nodes: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_seeded_nodes(self) -> "HyperNetCalculatorRequest":
        if self.seller_owned_nodes > self.total_nodes:
            raise ValueError("seller_owned_nodes cannot exceed total_nodes")
        return self


class HyperNetOfferCreate(HyperNetCalculatorRequest):
    seller_character_id: int = Field(gt=0)
    type_id: int = Field(gt=0)
    quantity: int = Field(default=1, gt=0)
    location_id: int | None = Field(default=None, gt=0)
    location_name: str | None = Field(default=None, max_length=500)
    status: Literal["draft", "active"] = "draft"
    nodes_sold: int = Field(default=0, ge=0)
    created_offer_at: datetime
    expires_at: datetime
    unique_participants: int = Field(default=0, ge=0)
    notes: str | None = None
    source: Literal["manual"] = "manual"
    source_reference: str | None = Field(default=None, max_length=255)

    @field_validator("created_offer_at", "expires_at")
    @classmethod
    def timezone_required(cls, value: datetime, info):
        return require_aware(value, info.field_name)

    @model_validator(mode="after")
    def validate_offer(self) -> "HyperNetOfferCreate":
        if self.expires_at <= self.created_offer_at:
            raise ValueError("expires_at must be after created_offer_at")
        if self.nodes_sold > self.total_nodes:
            raise ValueError("nodes_sold cannot exceed total_nodes")
        if self.seller_owned_nodes > self.nodes_sold:
            raise ValueError("seller_owned_nodes cannot exceed nodes_sold")
        return self


class HyperNetOfferPatch(BaseModel):
    status: Literal["draft", "active", "cancelled", "invalid", "awaiting_reconciliation"] | None = None
    expires_at: datetime | None = None
    hypercore_unit_cost: Decimal | None = Field(default=None, ge=0)
    acquisition_cost: Decimal | None = Field(default=None, ge=0)
    desired_profit: Decimal | None = None
    notes: str | None = None

    @field_validator("expires_at")
    @classmethod
    def timezone_required(cls, value: datetime | None):
        return require_aware(value, "expires_at") if value else None


class HyperNetParticipantInput(BaseModel):
    character_id: int | None = Field(default=None, gt=0)
    participant_name: str = Field(min_length=1, max_length=255)
    nodes_owned: int = Field(ge=0)
    is_seller: bool = False


class HyperNetSnapshotCreate(BaseModel):
    captured_at: datetime
    nodes_sold: int = Field(ge=0)
    seller_owned_nodes: int = Field(default=0, ge=0)
    unique_participants: int = Field(default=0, ge=0)
    jita_buy: Decimal | None = Field(default=None, ge=0)
    jita_sell: Decimal | None = Field(default=None, ge=0)
    local_buy: Decimal | None = Field(default=None, ge=0)
    local_sell: Decimal | None = Field(default=None, ge=0)
    hypercore_buy: Decimal | None = Field(default=None, ge=0)
    hypercore_sell: Decimal | None = Field(default=None, ge=0)
    note: str | None = None
    participants: list[HyperNetParticipantInput] = Field(default_factory=list)

    @field_validator("captured_at")
    @classmethod
    def timezone_required(cls, value: datetime):
        return require_aware(value, "captured_at")

    @model_validator(mode="after")
    def validate_snapshot(self) -> "HyperNetSnapshotCreate":
        if self.seller_owned_nodes > self.nodes_sold:
            raise ValueError("seller_owned_nodes cannot exceed nodes_sold")
        if self.participants:
            seeded = sum(row.nodes_owned for row in self.participants if row.is_seller)
            if seeded != self.seller_owned_nodes:
                raise ValueError("Seller participant nodes must equal seller_owned_nodes")
            if sum(row.nodes_owned for row in self.participants) > self.nodes_sold:
                raise ValueError("Participant nodes cannot exceed nodes_sold")
        return self


class HyperNetReconcileRequest(BaseModel):
    status: Literal["completed", "expired", "cancelled", "invalid"]
    reconciled_at: datetime
    winner: OfferWinner = "unknown"
    seller_owned_nodes: int | None = Field(default=None, ge=0)
    unique_participants: int | None = Field(default=None, ge=0)
    final_payout: Decimal | None = Field(default=None, ge=0)
    actual_hypercore_cost: Decimal | None = Field(default=None, ge=0)
    final_market_value: Decimal | None = Field(default=None, ge=0)
    final_profit: Decimal | None = None
    note: str | None = None

    @field_validator("reconciled_at")
    @classmethod
    def timezone_required(cls, value: datetime):
        return require_aware(value, "reconciled_at")

    @model_validator(mode="after")
    def validate_reconciliation(self) -> "HyperNetReconcileRequest":
        if self.status == "completed" and self.winner == "unknown":
            raise ValueError("Completed offers require the winner classification")
        return self


class HyperNetParticipationCreate(BaseModel):
    character_id: int = Field(gt=0)
    external_offer_reference: str | None = Field(default=None, max_length=255)
    item_type_id: int = Field(gt=0)
    seller_name: str = Field(min_length=1, max_length=255)
    location_id: int | None = Field(default=None, gt=0)
    location_name: str | None = Field(default=None, max_length=500)
    total_nodes: int = Field(gt=0, le=512)
    nodes_purchased: int = Field(gt=0)
    node_price: Decimal = Field(ge=0)
    created_at: datetime
    notes: str | None = None

    @field_validator("created_at")
    @classmethod
    def participation_timezone_required(cls, value: datetime):
        return require_aware(value, "created_at")

    @field_validator("seller_name")
    @classmethod
    def clean_seller_name(cls, value: str):
        return value.strip()

    @model_validator(mode="after")
    def validate_nodes(self) -> "HyperNetParticipationCreate":
        if self.nodes_purchased > self.total_nodes:
            raise ValueError("nodes_purchased cannot exceed total_nodes")
        return self


class HyperNetParticipationResolve(BaseModel):
    outcome: Literal["won", "lost", "cancelled"]
    completed_at: datetime
    item_value_at_completion: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None

    @field_validator("completed_at")
    @classmethod
    def resolve_timezone_required(cls, value: datetime):
        return require_aware(value, "completed_at")

    @model_validator(mode="after")
    def validate_outcome(self) -> "HyperNetParticipationResolve":
        if self.outcome == "won" and self.item_value_at_completion is None:
            raise ValueError("Won bids require the item value at completion")
        return self
