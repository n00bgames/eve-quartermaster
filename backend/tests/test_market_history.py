from datetime import date,timedelta
from types import SimpleNamespace
from unittest.mock import patch
import httpx,pytest
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.models import Base,User,EveType,CustomMarketHub,EveRegion,EveConstellation,EveSystem,EveStation
from app.api import market
from app.api.auth import get_current_user
from app.db.session import get_db

class FakeEsi:
    def __init__(self):self.calls=[];self.history_failure=False;self.orders_failure=False;self.invalid=False;self.closed=0
    async def close(self):self.closed+=1
    async def get_with_headers(self,path,params=None):
        self.calls.append((path,params))
        if self.history_failure:raise HTTPException(503,'fixture error')
        if self.invalid:return {'error':'wrong payload'},httpx.Headers()
        return [{'date':str(date(2026,1,1)+timedelta(days=i)),'volume':i+1,'average':200+i,'lowest':100+i,'highest':300+i} for i in [1,4,2,5,0,3]],httpx.Headers({'Expires':'Fri, 30 Oct 2026 11:05:00 GMT'})
    async def get_public_market_orders(self,region,type_id):
        self.calls.append(('orders',(region,type_id)))
        if self.orders_failure:raise HTTPException(504,'fixture timeout')
        return [dict(location_id=60003760,is_buy_order=False,price=409600000,volume_remain=1),dict(location_id=60003760,is_buy_order=False,price=409600000,volume_remain=2),
         dict(location_id=60003760,is_buy_order=False,price=450000000,volume_remain=9),dict(location_id=60003760,is_buy_order=True,price=244800000,volume_remain=8),
         dict(location_id=60003760,is_buy_order=True,price=244500000,volume_remain=4),dict(location_id=60003760,is_buy_order=False,price=1,volume_remain=0),
         dict(location_id=60008494,is_buy_order=False,price=3,volume_remain=99),dict(location_id=60008494,is_buy_order=True,price=999999999,volume_remain=99)]

@pytest.fixture
def env():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool);Base.metadata.create_all(engine)
    db=sessionmaker(bind=engine,expire_on_commit=False)();user=User(email='market@example.test',display_name='Market viewer',role='intel_analyst');db.add(user)
    db.add(EveType(type_id=96321,name='Salvation Sanguinary Savant SKIN'));db.commit()
    app=FastAPI();app.include_router(market.router,prefix='/api');current=[user];source=FakeEsi()
    def identity():
        if current[0] is None:raise HTTPException(401,'Sign in required')
        return current[0]
    def database():
        try:yield db
        finally:db.rollback()
    app.dependency_overrides[get_current_user]=identity;app.dependency_overrides[get_db]=database
    with patch('app.services.market_history.EsiClient',return_value=source),TestClient(app) as client:
        yield SimpleNamespace(db=db,client=client,current=current,source=source,user=user)
    db.close();engine.dispose()

def test_history_sorted_latest_five_and_current_station_depth(env):
    r=env.client.get('/api/market/items/96321/history?hub=jita')
    assert r.status_code==200,r.text
    data=r.json();assert data['hub']['region_name']=='The Forge' and 'no-store' in r.headers['cache-control']
    assert [r['date'] for r in data['history']]==['2026-01-06','2026-01-05','2026-01-04','2026-01-03','2026-01-02']
    assert data['history'][0]['volume']==6 and data['history'][0]['average']==205
    assert data['current']['sell']=={'price':409600000,'units':3,'orders':2}
    assert data['current']['buy']=={'price':244800000,'units':8,'orders':1}
    assert 'entire region' in data['notice'] and 'station-specific' in data['notice'] and data['history_expires_at'].startswith('2026-10-30')
    assert env.source.closed==1

def test_invalid_types_hubs_aggregate_and_bounds_make_no_requests(env):
    for path,status in [('/api/market/items/96321/history?hub=unknown',404),('/api/market/items/99999/history',404),('/api/market/items/96321/history?hub=npc',422),
      ('/api/market/items/96321/history?hub=c-n4od',422),('/api/market/items/96321/history?limit=31',422),('/api/market/items/0/history',422)]:
        assert env.client.get(path).status_code==status
    assert env.source.calls==[]

def test_empty_history_is_distinct_from_upstream_failure(env):
    async def empty(path,params=None):return [],httpx.Headers()
    env.source.get_with_headers=empty
    data=env.client.get('/api/market/items/96321/history').json();assert data['history']==[] and data['history_error'] is None
    env.source.orders_failure=True
    data=env.client.get('/api/market/items/96321/history').json();assert data['orders_error'] and data['current'] is None and data['history_error'] is None

@pytest.mark.parametrize('failure',['history_failure','invalid'])
def test_history_errors_do_not_hide_current_orders(env,failure):
    setattr(env.source,failure,True)
    data=env.client.get('/api/market/items/96321/history').json()
    assert data['history_error'] and data['history']==[] and data['current']['buy']['price']==244800000

def test_hub_region_selection_and_authentication(env):
    data=env.client.get('/api/market/items/96321/history?hub=amarr&limit=2').json()
    assert data['hub']['region_name']=='Domain' and len(data['history'])==2
    assert env.source.calls[0][0]=='/markets/10000043/history/'
    assert data['current']['sell']['price']==3
    env.current[0]=None;assert env.client.get('/api/market/items/96321/history').status_code==401

def test_custom_hub_resolves_imported_system_and_region(env):
    env.db.add(EveRegion(region_id=10000002,name='The Forge'));env.db.add(EveConstellation(constellation_id=20000001,name='Example',region_id=10000002));env.db.flush()
    env.db.add(EveSystem(system_id=30000001,name='Example System',constellation_id=20000001));env.db.flush()
    env.db.add(EveStation(station_id=60003760,name='Example Station',system_id=30000001));env.db.add(CustomMarketHub(key='custom-example',label='Staging',system_name='Example System'));env.db.commit()
    data=env.client.get('/api/market/items/96321/history?hub=custom-example').json()
    assert data['hub']['label']=='Staging' and data['hub']['region_id']==10000002 and data['current']['sell']['units']==3
