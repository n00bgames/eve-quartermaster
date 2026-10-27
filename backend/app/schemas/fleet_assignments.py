from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]

class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
class OperationCreate(Input):
    name: Name
    briefing: str = Field(default="", max_length=10000)
    preset_id: int | None = Field(default=None, gt=0)
class Revision(Input):
    revision: int = Field(gt=0)
class OperationPatch(Revision):
    name: Name | None = None
    briefing: str | None = Field(default=None, max_length=10000)
    status: Literal["draft", "published", "archived"] | None = None
class RosterImport(Revision):
    text: str = Field(min_length=1, max_length=60000)
class SlotCreate(Revision):
    fitting_id: int = Field(gt=0)
    doctrine_id: int | None = Field(default=None, gt=0)
    role: str = Field(default="", max_length=120)
    target_count: int = Field(default=1, ge=1, le=500)
class SlotPatch(Revision):
    role: str = Field(max_length=120)
    target_count: int = Field(ge=1, le=500)
class AssignmentInput(Revision):
    pilot_ids: list[int] = Field(min_length=1, max_length=500)
    slot_key: str | None = Field(default=None, max_length=36)
class PresetCreate(Revision):
    name: Name
