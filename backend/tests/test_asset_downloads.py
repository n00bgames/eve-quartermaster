import csv
import io
from pathlib import Path
from unittest.mock import patch
import pytest
from sqlalchemy import select
from tests.test_local_scan import env
from app.api import asset_downloads, quartermaster
from app.models import Asset, EveType, EveCharacter, OwnershipEntity, Location, EveGroup, EveCategory
from app.models.enums import OwnerKind

@pytest.fixture
def app(env):
    env.app.include_router(asset_downloads.router,prefix='/api')
    env.app.include_router(quartermaster.router,prefix='/api')
    char=env.db.scalar(select(EveCharacter).where(EveCharacter.owner_user_id==env.users['member'].id))
    hidden=env.db.scalar(select(EveCharacter).where(EveCharacter.owner_user_id==env.users['other'].id))
    owner=OwnershipEntity(owner_kind=OwnerKind.CHARACTER,character_id=char.id,display_name='=Dangerous owner')
    private=OwnershipEntity(owner_kind=OwnerKind.CHARACTER,character_id=hidden.id,display_name='Hidden owner')
    category=EveCategory(category_id=6,name='Ship');group=EveGroup(group_id=25,name='Frigate',category=category)
    typ=EveType(type_id=123,name='Example Frigate',group=group)
    station=Location(name='Home, station')
    env.db.add_all([owner,private,typ,station]);env.db.flush()
    env.db.add_all([Asset(ownership_entity_id=owner.id,type_id=123,quantity=i+1,eve_item_id=9007199254740993+i,location_id=station.id,location_flag='Hangar') for i in range(601)])
    env.db.add(Asset(ownership_entity_id=private.id,type_id=123,quantity=999999,location_id=station.id))
    env.db.commit()
    return env

def test_full_download_page_limit_csv_escaping_and_cleanup(app):
    paths=[];original=asset_downloads.tempfile.mkstemp
    def capture(*args,**kwargs):
        fd,path=original(*args,**kwargs);paths.append(path);return fd,path
    with patch.object(asset_downloads.tempfile,'mkstemp',side_effect=capture):
        response=app.client.get('/api/quartermaster/assets-download')
    assert response.status_code==200,response.text
    rows=list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))
    assert len(rows)==601
    assert rows[0]['owner_name']=="'=Dangerous owner"
    assert rows[0]['eve_item_id']=='9007199254740993'
    assert rows[0]['owner_kind']=='character'
    assert all(r['location_name']=='Home, station' for r in rows)
    assert 'Hidden owner' not in response.text
    assert response.headers['cache-control']=='no-store'
    assert not app.db.in_transaction()
    assert paths and all(not Path(path).exists() for path in paths)

@pytest.mark.parametrize('filters',[
 {'filter_key':'item','filter_value':'example','filter_mode':'contains'},
 {'filter_key':'owner','filter_value':'=Dangerous owner'},
 {'filter_key':'location','filter_value':'Home, station'},
 {'filter_key':'flag','filter_value':'Hangar','sort_key':'flag'},
 {'filter_key':'item','filter_value':'missing'},
 {'category':'ships','subtype':'Frigate','sort_key':'quantity','sort_direction':'desc'},
 {'owner_kind':'corporation'},
 {'filter_key':'item','filter_value':'%','filter_mode':'contains'},
])
def test_filter_sort_parity(app,filters):
    page=app.client.get('/api/quartermaster/assets-page',params={**filters,'all_records':'true'})
    assert page.status_code==200,page.text
    result=app.client.get('/api/quartermaster/assets-download',params=filters)
    assert result.status_code==200,result.text
    rows=list(csv.DictReader(io.StringIO(result.content.decode('utf-8-sig'))))
    assert len(rows)==page.json()['total']
    assert [r['eve_item_id'] for r in rows]==[str(r['eve_item_id']) for r in page.json()['items']]

def test_janice_total_and_permissions(app):
    result=app.client.get('/api/quartermaster/assets-download?format=janice')
    assert result.text==f'Example Frigate\t{sum(range(1,602))}\n'
    assert 'owner' not in result.text and 'station' not in result.text
    app.current[0]=app.users['intel_analyst']
    assert app.client.get('/api/quartermaster/assets-download').status_code==403
    app.current[0]=None
    assert app.client.get('/api/quartermaster/assets-download').status_code==401

def test_empty_and_invalid(app):
    result=app.client.get('/api/quartermaster/assets-download',params={'format':'janice','filter_key':'item','filter_value':'missing'})
    assert result.status_code==200 and result.content==b''
    assert app.client.get('/api/quartermaster/assets-download?format=html').status_code==422


def test_interrupted_download_removes_private_file(tmp_path):
    import asyncio
    path=tmp_path/'private.csv';path.write_text('private stock',encoding='utf-8')
    response=asset_downloads.TemporaryDownload(path)
    async def receive():return {'type':'http.disconnect'}
    async def send(message):raise ConnectionError('browser disconnected')
    with pytest.raises(ConnectionError):
        asyncio.run(response({'type':'http','method':'GET','headers':[]},receive,send))
    assert not path.exists()
