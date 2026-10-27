from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
class ResolveInput(Input):
    text: str = Field(min_length=1,max_length=30000)
class SubjectInput(Input):
    kind: Literal["character","corporation","alliance"]
    eve_id: int = Field(gt=0,le=2147483647)
class CollectInput(Input):
    days: int = Field(default=90,ge=1,le=20000)
    max_pages: int = Field(default=10,ge=1,le=100)
class NoteInput(Input):
    body: str = Field(min_length=1,max_length=5000)
class AuthorizedRefreshInput(Input):
    dataset: Literal["skills","fittings","applicant"]
