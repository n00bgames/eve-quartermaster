from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
PriorityFieldType = Literal["select", "text", "number", "boolean"]
SkillPlanSource = Literal["manual", "fitting", "doctrine", "merged"]
SrpStatus = Literal["draft", "submitted", "under_review", "approved", "rejected", "paid"]
Money = Annotated[Decimal, Field(ge=0, max_digits=24, decimal_places=2)]


class PriorityOptionInput(BaseModel):
    label: NonBlank = Field(max_length=120)
    value: NonBlank = Field(max_length=120)
    short_code: str | None = Field(default=None, max_length=32)
    display_order: int = Field(default=0, ge=0)
    is_active: bool = True


class PriorityFieldInput(BaseModel):
    key: NonBlank = Field(max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    name: NonBlank = Field(max_length=120)
    field_type: PriorityFieldType = "select"
    is_required: bool = False
    display_order: int = Field(default=0, ge=0)
    is_active: bool = True
    options: list[PriorityOptionInput] = Field(default_factory=list)


class DoctrineSkillPlanLinkInput(BaseModel):
    skill_plan_id: int = Field(gt=0)
    fitting_id: int | None = Field(default=None, gt=0)


class DoctrineInput(BaseModel):
    name: NonBlank = Field(max_length=255)
    purpose: str | None = Field(default=None, max_length=500)
    fitting_id: int | None = Field(default=None, gt=0)
    fitting_ids: list[int] = Field(default_factory=list, max_length=50)
    primary_fitting_id: int | None = Field(default=None, gt=0)
    priority_values: dict[str, str | int | float | bool] = Field(default_factory=dict)
    priority_code: str | None = Field(default=None, max_length=120)
    priority_code_manual: bool = False
    notes: str | None = None
    linked_skill_plan_id: int | None = Field(default=None, gt=0)
    skill_plan_links: list[DoctrineSkillPlanLinkInput] = Field(default_factory=list, max_length=50)
    is_shared: bool = True


class DoctrinePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: NonBlank | None = Field(default=None, max_length=255)
    purpose: str | None = Field(default=None, max_length=500)
    fitting_id: int | None = Field(default=None, gt=0)
    fitting_ids: list[int] | None = Field(default=None, max_length=50)
    primary_fitting_id: int | None = Field(default=None, gt=0)
    priority_values: dict[str, str | int | float | bool] | None = None
    priority_code: str | None = Field(default=None, max_length=120)
    priority_code_manual: bool | None = None
    notes: str | None = None
    linked_skill_plan_id: int | None = Field(default=None, gt=0)
    skill_plan_links: list[DoctrineSkillPlanLinkInput] | None = Field(default=None, max_length=50)
    is_shared: bool | None = None


class SkillPlanEntryInput(BaseModel):
    skill_type_id: int = Field(gt=0)
    target_level: int = Field(ge=1, le=5)
    sort_order: int = Field(default=0, ge=0)
    notes: str | None = None
    introduced_by: list[str] = Field(default_factory=list)


class SkillPlanInput(BaseModel):
    name: NonBlank = Field(max_length=255)
    description: str | None = None
    notes: str | None = None
    character_id: int | None = Field(default=None, gt=0)
    fitting_id: int | None = Field(default=None, gt=0)
    source_doctrine_id: int | None = Field(default=None, gt=0)
    source: SkillPlanSource = "manual"
    entries: list[SkillPlanEntryInput] = Field(default_factory=list)


class SkillPlanGenerationInput(BaseModel):
    fitting_id: int | None = Field(default=None, gt=0)
    doctrine_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def require_source(self):
        if self.fitting_id is None and self.doctrine_id is None:
            raise ValueError("Choose a fitting or doctrine")
        return self


class SkillPlanMergeInput(BaseModel):
    plan_ids: list[int] = Field(min_length=2, max_length=50)

    @model_validator(mode="after")
    def distinct_plans(self):
        self.plan_ids = list(dict.fromkeys(self.plan_ids))
        if len(self.plan_ids) < 2:
            raise ValueError("Choose at least two different skill plans")
        return self


class SrpRequestInput(BaseModel):
    character_id: int = Field(gt=0)
    fitting_id: int = Field(gt=0)
    doctrine_id: int | None = Field(default=None, gt=0)
    operation_id: int | None = Field(default=None, gt=0)
    operation_token: str | None = Field(default=None, max_length=64)
    loss_reason_id: int | None = Field(default=None, gt=0)
    system_id: int | None = Field(default=None, gt=0)
    loss_date: date
    loss_time: time
    entered_timezone: str = Field(default="UTC", max_length=64)
    killmail_id: int | None = Field(default=None, gt=0)
    killmail_hash: str | None = Field(default=None, max_length=255)
    killmail_url: str | None = Field(default=None, max_length=1000)
    hull_value: Money | None = None
    fitted_module_value: Money | None = None
    cargo_value: Money | None = None
    drone_fighter_value: Money | None = None
    submission_estimated_loss_value: Money | None = None
    requested_reimbursement_amount: Money | None = None
    data_source: Literal["manual", "administrative_entry"] = "manual"
    notes: str | None = None
    status: Literal["draft", "submitted"] = "draft"


class SrpRequestPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    character_id: int | None = Field(default=None, gt=0)
    fitting_id: int | None = Field(default=None, gt=0)
    doctrine_id: int | None = Field(default=None, gt=0)
    operation_id: int | None = Field(default=None, gt=0)
    loss_reason_id: int | None = Field(default=None, gt=0)
    system_id: int | None = Field(default=None, gt=0)
    loss_date: date | None = None
    loss_time: time | None = None
    entered_timezone: str | None = Field(default=None, max_length=64)
    killmail_id: int | None = Field(default=None, gt=0)
    killmail_hash: str | None = Field(default=None, max_length=255)
    killmail_url: str | None = Field(default=None, max_length=1000)
    hull_value: Money | None = None
    fitted_module_value: Money | None = None
    cargo_value: Money | None = None
    drone_fighter_value: Money | None = None
    submission_estimated_loss_value: Money | None = None
    requested_reimbursement_amount: Money | None = None
    data_source: Literal["manual", "administrative_entry"] | None = None
    notes: str | None = None


class SrpTransitionInput(BaseModel):
    status: SrpStatus
    reason: str | None = None


class SrpOperationInput(BaseModel):
    name: NonBlank = Field(max_length=255)
    start_at: datetime
    end_at: datetime | None = None
    fleet_commander_character_id: int | None = Field(default=None, gt=0)
    doctrine_id: int | None = Field(default=None, gt=0)
    corporation_id: int | None = Field(default=None, gt=0)
    alliance_id: int | None = Field(default=None, gt=0)
    notes: str | None = None
    status: Literal["open", "closed"] = "open"


class SrpOperationPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: NonBlank | None = Field(default=None, max_length=255)
    start_at: datetime | None = None
    end_at: datetime | None = None
    fleet_commander_character_id: int | None = Field(default=None, gt=0)
    doctrine_id: int | None = Field(default=None, gt=0)
    corporation_id: int | None = Field(default=None, gt=0)
    alliance_id: int | None = Field(default=None, gt=0)
    notes: str | None = None
    status: Literal["open", "closed"] | None = None


class SrpLossReasonInput(BaseModel):
    key: NonBlank = Field(max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    name: NonBlank = Field(max_length=120)
    description: str | None = Field(default=None, max_length=500)
    display_order: int = Field(default=0, ge=0)
    is_active: bool = True


class SrpReviewPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    doctrine_id: int | None = Field(default=None, gt=0)
    fitting_id: int | None = Field(default=None, gt=0)
    operation_id: int | None = Field(default=None, gt=0)
    loss_reason_id: int | None = Field(default=None, gt=0)
    system_id: int | None = Field(default=None, gt=0)
    verified_loss_value: Money | None = None
    killmail_destroyed_value: Money | None = None
    killmail_dropped_value: Money | None = None
    killmail_total_loss_value: Money | None = None
    requested_reimbursement_amount: Money | None = None
    approved_reimbursement_amount: Money | None = None
    paid_reimbursement_amount: Money | None = None
    valuation_source: str | None = Field(default=None, max_length=64)
    valuation_status: Literal["pending", "estimated", "verified", "overridden", "unavailable"] | None = None
    valuation_market_context: str | None = Field(default=None, max_length=255)
    manual_valuation_override: Money | None = None
    valuation_override_reason: str | None = None
    record_disposition: Literal["operational", "duplicate", "invalid", "test", "cancelled"] | None = None
    duplicate_of_request_id: int | None = Field(default=None, gt=0)
    exclusion_reason: str | None = None
    reason: str | None = None
