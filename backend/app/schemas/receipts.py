from decimal import Decimal
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from app.domain.receipts import MAX_ISK

Money = Annotated[Decimal,Field(ge=0,le=MAX_ISK,max_digits=15,decimal_places=2)]
Quantity = Annotated[StrictInt,Field(ge=0,le=2147483647)]
Label = Annotated[str,Field(max_length=120)]

class Strict(BaseModel):
    model_config=ConfigDict(extra="forbid")

class PasteInput(Strict):
    text:str=Field(min_length=1,max_length=1_000_000)

class Fuel(Strict):
    item:str=Field(min_length=1,max_length=80)
    quantity:Quantity=0
    unit_price:Money=Decimal(0)

class Route(Strict):
    mode:Literal["gate","jump_freighter","mixed"]="gate"
    origin:Label=""
    destination:Label=""
    systems:list[Label]=Field(default_factory=list,max_length=500)
    jump_count:Annotated[StrictInt,Field(ge=0,le=2000)]|None=None
    source:Literal["manual","planned"]="manual"

class ReceiptInput(PasteInput):
    title:Label="Market run receipt"
    recipient:Label=""
    note:str=Field(default="",max_length=2000)
    billable_quantities:dict[Annotated[int,Field(gt=0)],Quantity]=Field(default_factory=dict,max_length=5000)
    credit:Money=Decimal(0)
    credit_reason:str=Field(default="",max_length=300)
    hauling_fee:Money=Decimal(0)
    fuel:list[Fuel]=Field(default_factory=list,max_length=8)
    route:Route=Field(default_factory=Route)
    is_private:bool=True
    anonymous:bool=False
    retention:Literal["30m","1h","2h","12h","24h","3days","7days","30days","permanent"]="30days"

class RouteInput(Strict):
    origin:str=Field(min_length=1,max_length=120)
    destination:str=Field(min_length=1,max_length=120)
    via:list[Annotated[str,Field(min_length=1,max_length=120)]]=Field(default_factory=list,max_length=8)
    preference:Literal["safer","shortest","highsec"]="safer"
