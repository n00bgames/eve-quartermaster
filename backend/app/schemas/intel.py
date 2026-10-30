from __future__ import annotations
from typing import Literal
from uuid import UUID
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
class ResolveInput(Input):
    text: str = Field(min_length=1,max_length=30000)
class SightingInput(Input):
    system_id: int = Field(gt=0,le=2147483647,strict=True)
    ship_type_id: int | None = Field(default=None,gt=0,le=2147483647,strict=True)
    request_id: UUID
    observed_at: AwareDatetime | None = None

class SubjectInput(Input):
    sighting: SightingInput | None = None
    kind: Literal["character","corporation","alliance"]
    eve_id: int = Field(gt=0,le=2147483647)
class CollectInput(Input):
    days: int = Field(default=90,ge=1,le=20000)
    max_pages: int = Field(default=10,ge=1,le=100)
class NoteInput(Input):
    body: str = Field(min_length=1,max_length=5000)
class AuthorizedRefreshInput(Input):
    dataset: Literal["skills","fittings","applicant"]

class NoteEditInput(NoteInput):
    expected_body: str = Field(min_length=1,max_length=5000)

class NoteDeleteInput(Input):
    expected_body: str = Field(min_length=1,max_length=5000)
