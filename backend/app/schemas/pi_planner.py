"""Versioned, bounded user inputs. Observed data and ESI prices are server-owned."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Amount = Annotated[float, Field(ge=0, le=1e12, allow_inf_nan=False)]
PlanetKind = Literal["Barren", "Gas", "Ice", "Lava", "Oceanic", "Plasma", "Storm", "Temperate"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class YieldEstimate(Contract):
    type_id: int = Field(gt=0)
    units_per_head_hour: float = Field(gt=0, le=1e7)
    source: Literal["estimate", "scan", "installed_program"] = "estimate"


class PlanetChoice(Contract):
    key: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    planet_type: PlanetKind
    planet_id: int | None = Field(default=None, gt=0)
    system_id: int | None = Field(default=None, gt=0)
    diameter_km: float = Field(default=10000, ge=100, le=500000)
    security: float = Field(default=0.5, ge=-1, le=1)
    customs_percent: float = Field(default=10, ge=0, le=100)
    npc_tax_percent: float = Field(default=10, ge=0, le=100)
    yields: list[YieldEstimate] = Field(default_factory=list, max_length=15)

    @model_validator(mode="after")
    def unique_yields(self):
        if len({x.type_id for x in self.yields}) != len(self.yields):
            raise ValueError("A resource can have only one yield estimate per planet")
        return self


class PilotChoice(Contract):
    character_id: int = Field(gt=0)
    enabled: bool = True
    # Null means use the synchronized active skill, never assume level V.
    planned_ccu: int | None = Field(default=None, ge=0, le=5)
    planned_ic: int | None = Field(default=None, ge=0, le=5)
    release_colony_ids: list[int] = Field(default_factory=list, max_length=6)
    planet_keys: list[str] = Field(default_factory=list, max_length=60)


class ProductTarget(Contract):
    type_id: int = Field(gt=0)
    quantity: int = Field(default=1000, gt=0, le=1000000000)


class CostSettings(Contract):
    sales_tax_percent: float = Field(default=8, ge=0, le=100)
    broker_fee_percent: float = Field(default=3, ge=0, le=100)
    freight_isk_m3: Amount = 0
    weekly_overhead: Amount = 0
    per_colony_weekly: Amount = 0
    setup_budget: Amount = 1e12
    additional_setup_per_colony: Amount = 0
    setup_amortization_weeks: float = Field(default=12, gt=0, le=520)


class Schedule(Contract):
    visits_per_week: int = Field(default=7, ge=1, le=168)
    minutes_per_visit: float = Field(default=15, gt=0, le=1440)
    haul_capacity_m3: float = Field(default=60000, gt=0, le=1e9)
    max_trips_per_visit: int = Field(default=4, ge=1, le=1000)
    program_hours: float = Field(default=24, ge=1, le=336)
    restart_minutes: float = Field(default=5, ge=0, le=1440)
    link_length_km: float = Field(default=100, ge=1, le=10000)


class PlanningRequest(Contract):
    schema_version: Literal["eqm.pi-planning-input.v1"] = "eqm.pi-planning-input.v1"
    name: str = Field(default="PI scenario", min_length=1, max_length=120)
    objective: Literal["profit", "output", "quota", "mix", "compare"] = "profit"
    products: list[ProductTarget] = Field(min_length=1, max_length=83)
    pilots: list[PilotChoice] = Field(default_factory=list, max_length=12)
    planets: list[PlanetChoice] = Field(default_factory=list, max_length=60)
    sourcing: Literal["auto", "extract", "buy_raw", "buy_p1", "buy_p2", "buy_p3"] = "auto"
    buy_type_ids: list[int] = Field(default_factory=list, max_length=83)
    hub: Literal["jita", "amarr", "hek", "dodixie", "rens"] = "jita"
    sale_mode: Literal["immediate", "patient"] = "immediate"
    costs: CostSettings = Field(default_factory=CostSettings)
    schedule: Schedule = Field(default_factory=Schedule)
    search_seconds: float = Field(default=8, ge=1, le=30)

    @model_validator(mode="after")
    def unique_entities(self):
        for rows, attr, label in [(self.products, "type_id", "products"), (self.pilots, "character_id", "pilots"), (self.planets, "key", "planets")]:
            if len({getattr(row, attr) for row in rows}) != len(rows):
                raise ValueError(f"Duplicate {label} are not allowed")
        keys = {p.key for p in self.planets}
        if any(set(p.planet_keys) - keys for p in self.pilots):
            raise ValueError("Pilot references an unknown planet")
        if self.objective == "mix" and len(self.products) > 8:
            raise ValueError("A mixed operation supports up to eight products")
        return self


class ScenarioWrite(Contract):
    request: PlanningRequest
    revision: int | None = Field(default=None, ge=1)


class InventoryItem(Contract):
    type_id: int = Field(gt=0)
    quantity: int = Field(ge=0, le=1000000000000)


class RecipeRequest(Contract):
    targets: list[ProductTarget] = Field(min_length=1, max_length=83)
    inventory: list[InventoryItem] = Field(default_factory=list, max_length=200)
    buy_type_ids: list[int] = Field(default_factory=list, max_length=83)


class ScoutRequest(Contract):
    system_ids: list[int] = Field(min_length=1, max_length=25)
    resource_type_ids: list[int] = Field(default_factory=list, max_length=15)


class TemplateRequest(Contract):
    job_id: str = Field(max_length=36)
    plan_index: int = Field(ge=0, le=100)
    colony_index: int = Field(ge=0, le=72)


class TemplateInspect(Contract):
    text: str = Field(min_length=2, max_length=250000)
