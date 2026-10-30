"""Lazy regional completed-trade history plus hub-local active order depth."""
from __future__ import annotations
import asyncio
from datetime import date,datetime,timezone
from email.utils import parsedate_to_datetime
from pydantic import BaseModel,ConfigDict,Field,ValidationError
from fastapi import HTTPException
from app.models import EveType
from app.services.esi_client import EsiClient
from app.services.market import all_trade_hubs,hub_payload


class HistoryDay(BaseModel):
    model_config=ConfigDict(allow_inf_nan=False)
    date:date
    volume:int=Field(ge=0)
    average:float=Field(ge=0)
    lowest:float=Field(ge=0)
    highest:float=Field(ge=0)


def expiry(headers):
    try:return parsedate_to_datetime(headers.get('Expires','')).astimezone(timezone.utc).isoformat()
    except (ValueError,TypeError,AttributeError,OverflowError):return None


def completed_days(payload,limit):
    if not isinstance(payload,list):raise ValueError('Invalid history payload')
    rows=[HistoryDay.model_validate(row) for row in payload]
    today=datetime.now(timezone.utc).date()
    return [r.model_dump(mode='json') for r in sorted(rows,key=lambda r:r.date,reverse=True) if r.date<=today and r.volume>0][:limit]


def local_orders(rows,locations):
    if not isinstance(rows,list):raise ValueError('Invalid order payload')
    scoped=[r for r in rows if r.get('location_id') in locations and int(r.get('volume_remain',0))>0]
    result={}
    for key,buy in [('buy',True),('sell',False)]:
        orders=[r for r in scoped if r.get('is_buy_order') is buy and float(r.get('price',0))>0]
        price=(max if buy else min)((float(r['price']) for r in orders),default=None)
        best=[r for r in orders if float(r['price'])==price]
        result[key]={'price':price,'units':sum(int(r['volume_remain']) for r in best),'orders':len(best)}
    return result


async def market_history_summary(db,type_id,hub_key,limit=5):
    item=db.get(EveType,type_id)
    if item is None:raise HTTPException(404,'Item is not in the imported SDE')
    hub=all_trade_hubs(db).get(hub_key)
    if hub is None:raise HTTPException(404,'Market hub not found')
    payload=hub_payload(db,hub)
    if hub.npc_group:raise HTTPException(422,'Choose an individual market hub, not the NPC aggregate')
    if not payload['available'] or not payload.get('region_id'):raise HTTPException(422,'This hub needs an imported region and market location')
    locations=set(payload.get('location_ids') or [])
    if not locations:raise HTTPException(422,'No market locations are available for this hub')
    region_id=payload['region_id'];item_name=item.name
    # Release the read-only DB transaction before waiting on public ESI.
    db.rollback()
    client=EsiClient()
    try:
        # Each section reports failures independently. No upstream failure becomes zero sales.
        history,orders=await asyncio.gather(asyncio.wait_for(client.get_with_headers(f'/markets/{region_id}/history/',params={'type_id':type_id}),45),
            asyncio.wait_for(client.get_public_market_orders(region_id,type_id),45),return_exceptions=True)
    finally:await client.close()
    result={'type_id':type_id,'item':item_name,'hub':{k:payload[k] for k in ['key','label','region_id','region_name']},
        'fetched_at':datetime.now(timezone.utc).isoformat(),'history':[],'history_expires_at':None,'history_error':None,'orders_error':None,'current':None,
        'notice':'Completed trades cover the entire region, including trades into buy orders and purchases from sell orders; individual sales and station-specific sale history are not public. Current orders are located at the selected hub, not completed sales; remote ranged buy orders are not included.'}
    try:
        if isinstance(history,BaseException):raise ValueError('History request failed')
        raw,headers=history;result['history']=completed_days(raw,limit);result['history_expires_at']=expiry(headers)
    except (ValueError,TypeError,ValidationError):result['history_error']='Completed-trade history is temporarily unavailable from ESI. Try again shortly.'
    try:
        if isinstance(orders,BaseException):raise ValueError('Order request failed')
        result['current']=local_orders(orders,locations)
    except (ValueError,TypeError,KeyError):result['orders_error']='Current hub orders are temporarily unavailable from ESI. Try again shortly.'
    return result
