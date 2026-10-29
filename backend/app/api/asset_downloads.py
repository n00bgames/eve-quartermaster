from collections import defaultdict
import csv
import os
import tempfile
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.auth import get_current_user
from app.api.quartermaster import list_assets_page, filtered_asset_query, serialize_asset
from app.services.corporation_metadata import corporation_hangar_names
from app.db.session import get_db
from app.models import User, Asset, OwnershipEntity, EveType
from app.services.permissions import effective_permissions

router=APIRouter(prefix="/quartermaster",tags=["asset downloads"])

class TemporaryDownload(FileResponse):
    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            # Also clean up if the browser disconnects before the response finishes.
            try:
                os.unlink(self.path)
            except FileNotFoundError:
                pass


class AssetDownloadQuery(BaseModel):
    format: Literal["csv","janice"] = "csv"
    sort_key: Literal["item","owner","quantity","location","flag"] = "item"
    sort_direction: Literal["asc","desc"] = "asc"
    owner_kind: Literal["character","corporation","alliance","manual_group"] | None = None
    category: str = Field(default="all",max_length=80)
    subtype: str | None = Field(default=None,max_length=255)
    filter_key: Literal["item","owner","location","flag"] | None = None
    filter_value: str | None = Field(default=None,max_length=1000)
    filter_mode: Literal["exact","contains"] = "exact"

def csv_cell(value):
    if value is None:
        return ""
    if isinstance(value,str) and value.lstrip().startswith(("=","+","-","@")):
        return "'"+value
    if isinstance(value,str) and value.startswith(("\t","\r","\n")):
        return "'"+value
    return value

@router.get("/assets-download")
def download_assets(query: AssetDownloadQuery = Depends(), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not effective_permissions(current_user,db).get("assets"):
        raise HTTPException(403,"Assets permission is required")
    filters=query.model_dump(exclude={"format"})
    # Most exports hydrate 500 assets at a time. Computed location/flag sorts
    # use the ledger's exact resolver and retain candidates on the server.
    computed=query.sort_key in {"location","flag"} or (query.filter_key in {"location","flag"} and query.filter_value)
    if computed:
        snapshot=list_assets_page(all_records=True,page=1,page_size=100,current_user=current_user,db=db,**filters)
        rows=iter(snapshot["items"])
    else:
        statement=filtered_asset_query(current_user,db,query.owner_kind,query.category,query.subtype,query.filter_key,query.filter_value,query.filter_mode)
        if query.sort_key=="quantity":
            column=Asset.quantity
        elif query.sort_key=="owner":
            column=select(OwnershipEntity.display_name).where(OwnershipEntity.id==Asset.ownership_entity_id).scalar_subquery()
        else:
            column=select(EveType.name).where(EveType.type_id==Asset.type_id).scalar_subquery()
        statement=statement.order_by(column.desc() if query.sort_direction=="desc" else column.asc(),Asset.id.asc()).execution_options(yield_per=500)
        def batches():
            for batch in db.scalars(statement).partitions(500):
                names=corporation_hangar_names(db,batch)
                for asset in batch:
                    yield serialize_asset(asset,names)
        rows=batches()
    row_count=0
    fd,path=tempfile.mkstemp(prefix="eqm-assets-",suffix=".csv" if query.format=="csv" else ".txt")
    try:
        with os.fdopen(fd,"w",encoding="utf-8-sig" if query.format=="csv" else "utf-8",newline="") as output:
            if query.format=="csv":
                fields=["type_name","type_id","quantity","owner_name","owner_kind","location_name","location_flag_name","eve_item_id"]
                writer=csv.writer(output)
                writer.writerow(fields)
                for row in rows:
                    row_count+=1
                    writer.writerow([csv_cell(row.get(key)) for key in fields])
            else:
                totals=defaultdict(int)
                for row in rows:
                    row_count+=1
                    # Item names only: never disclose ownership/location in a Janice list.
                    name=" ".join(str(row.get("type_name") or f'Type {row["type_id"]}').split())
                    totals[name]+=int(row["quantity"])
                for name,quantity in sorted(totals.items(),key=lambda item:item[0].casefold()):
                    if quantity>0:
                        output.write(f"{name}\t{quantity}\n")
        db.rollback()  # Release the read transaction before sending the file.
        stamp=datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        return TemporaryDownload(path,media_type="text/csv" if query.format=="csv" else "text/plain",
            filename=f"eqm-assets-{stamp}.{'csv' if query.format=='csv' else 'txt'}",
            headers={"Cache-Control":"no-store","X-Content-Type-Options":"nosniff","X-Export-Row-Count":str(row_count)})
    except BaseException:
        db.rollback()
        os.unlink(path)
        raise
