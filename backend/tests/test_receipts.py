from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch
import pytest
from sqlalchemy import select,func
from app.api import receipts
from app.api.auth import get_current_user
from app.core.security import create_access_token
from app.domain import receipts as domain
from app.models import EveCharacter,EveSystem,EveStargate,UserSectionPermission
from app.models.local_scan import LocalScanReport
from app.schemas.receipts import ReceiptInput
from app.services.local_scan import now,RETENTIONS
from app.services import receipt_exports
from .test_local_scan import env


def purchase(quantity=3,item='Demo Module II',price='10.25',seller='PRIVATE COUNTERPARTY',station='Demo Station'):
    total=Decimal(str(quantity))*Decimal(price)
    return f'2026.11.02 12:39\t{quantity}\t{item}\t{price} ISK\t-{total:.2f} ISK\t{seller}\t{station}'


@pytest.fixture
def app(env):
    env.app.include_router(receipts.router,prefix='/api')
    return env


def save(app,**changes):
    response=app.client.post('/api/receipts',json={'text':purchase(),**changes})
    assert response.status_code==201,response.text
    return response.json()


def test_exact_grouping_partial_exclusions_credit_hauling_and_fuel():
    text=purchase(3,price='10.25')+'\n'+purchase(2,price='9.99')+'\n'+purchase(5,item='Other Module',price='2.00')
    parsed=domain.parse(text)
    assert parsed['transaction_count']==3 and parsed['purchase_total']=='60.73'
    assert 'PRIVATE COUNTERPARTY' not in str(parsed)
    data=domain.build({'text':text,'billable_quantities':{'1':2,'3':0},'credit':'5.00','credit_reason':'Prepaid credit','hauling_fee':'30.00','fuel':[{'item':'Nitrogen Isotopes','quantity':4,'unit_price':'0.50'}]})
    assert data['purchase_total']=='60.73' and data['excluded_total']=='20.25'
    assert data['included_total']=='40.48' and data['fuel_total']=='2.00' and data['grand_total']=='67.48'
    group=next(row for row in data['groups'] if row['item']=='Demo Module II')
    assert group['quantity']==4 and group['purchased_quantity']==5 and group['excluded_quantity']==1
    assert group['average_unit_price']=='10.12' and group['charged']=='40.48'


def test_average_rounding_never_reprices_charged_total():
    data=domain.build({'text':purchase(2,price='0.01')+'\n'+purchase(1,price='0.02')})
    assert data['groups'][0]['average_unit_price']=='0.01' and data['grand_total']=='0.04'


def test_credit_can_cover_items_and_hauling_but_total_cannot_be_negative():
    data=domain.build({'text':purchase(),'hauling_fee':'10','credit':'40.75','credit_reason':'Prepaid in full'})
    assert data['grand_total']=='0.00'
    with pytest.raises(ValueError):domain.build({'text':purchase(),'hauling_fee':'10','credit':'40.76','credit_reason':'Too much'})


def test_fuel_also_in_billable_purchase_warns_without_silently_rewriting_costs():
    data=domain.build({'text':purchase(item='Nitrogen Isotopes'), 'fuel':[{'item':'Nitrogen Isotopes','quantity':1,'unit_price':'10.25'}]})
    assert data['grand_total']=='41.00' and any('both' in warning for warning in data['warnings'])
    data=domain.build({'text':purchase(item='Nitrogen Isotopes'), 'billable_quantities':{'1':0}, 'fuel':[{'item':'Nitrogen Isotopes','quantity':1,'unit_price':'10.25'}]})
    assert data['grand_total']=='10.25' and not data['warnings']


def test_header_blank_bom_and_identical_lines_are_retained_with_warning():
    text='\ufeffDate\tQuantity\tItem\tUnit Price\tTotal\tSeller\tStation\n\n'+purchase()+'\n'+purchase()
    parsed=domain.parse(text)
    assert parsed['transaction_count']==2 and parsed['purchase_total']=='61.50' and parsed['duplicate_count']==1
    assert parsed['lines'][1]['duplicate_of']==1 and parsed['warnings']


@pytest.mark.parametrize('text',[
    '', '2026.11.02 12:39\tMarket Escrow\t-10 ISK\t100 ISK\tAuthorized',
    purchase().replace('-30.75 ISK','30.75 ISK'),
    purchase().replace('-30.75 ISK','-30.74 ISK'),
    purchase().replace('10.25 ISK','NaN ISK'),
    purchase().replace('10.25 ISK','1e2 ISK'),
    purchase().replace('10.25 ISK','-10.25 ISK'),
    purchase().replace('10.25 ISK','10.251 ISK'),
    purchase().replace('\t3\t','\t0\t'),
    purchase().replace('\t3\t','\t1,00\t'),
    purchase().replace('2026.11.02','2026.13.02'),
    purchase()+'\nnot a transaction',
])
def test_invalid_rows_reject_whole_paste_with_line_error(text):
    with pytest.raises(ValueError):domain.parse(text)


@pytest.mark.parametrize('extra',[
    {'billable_quantities':{'1':4}}, {'billable_quantities':{'1':-1}}, {'billable_quantities':{'99':0}},
    {'credit':'31','credit_reason':'Too much'}, {'credit':'1'}, {'hauling_fee':'-1'},
    {'fuel':[{'item':'Fuel','quantity':-1,'unit_price':'1'}]},
])
def test_invalid_exclusions_and_costs_rejected(extra):
    with pytest.raises(ValueError):domain.build({'text':purchase(),**extra})


def test_private_default_and_owner_isolation_including_staff(app):
    report=save(app)
    assert report['grand_total']=='30.75' and report['is_private'] and report['share_url'] is None
    assert report['draft']['text']==purchase()
    assert app.client.get('/api/receipts/public/'+report['token']).status_code==404
    for role in ('other','admin','host'):
        app.current[0]=app.users[role]
        assert app.client.get('/api/receipts/reports/'+report['token']).status_code==404
        assert app.client.get('/api/receipts/reports/'+report['token']+'/export/csv').status_code==404
        assert app.client.get('/api/receipts/reports').json()['total']==0
    app.current[0]=None
    assert app.client.get('/api/receipts/reports').status_code==401


def test_public_read_and_exports_omit_paste_sellers_and_account_names(app):
    user=app.users['member'];character=app.db.scalar(select(EveCharacter).where(EveCharacter.owner_user_id==user.id))
    user.main_character_id=character.character_id;app.db.commit()
    report=save(app,is_private=False,hauling_fee='30.00',recipient='Demo Fleet')
    assert report['creator_name']==character.name and '/#receipt/' in report['share_url']
    app.current[0]=None
    r=app.client.get('/api/receipts/public/'+report['token']);assert r.status_code==200,r.text
    assert r.headers['cache-control']=='no-store' and 'noindex' in r.headers['x-robots-tag']
    assert 'draft' not in r.json() and 'PRIVATE COUNTERPARTY' not in r.text and user.email not in r.text
    csv=app.client.get('/api/receipts/public/'+report['token']+'/export/csv')
    assert csv.status_code==200 and '60.75' in csv.text and 'PRIVATE COUNTERPARTY' not in csv.text
    pdf=app.client.get('/api/receipts/public/'+report['token']+'/export/pdf')
    assert pdf.status_code==200 and pdf.content.startswith(b'%PDF')
    from pypdf import PdfReader
    text='\n'.join(page.extract_text() for page in PdfReader(BytesIO(pdf.content)).pages)
    assert '60.75' in text and 'Generated with EVE Quartermaster' in text and character.name in text
    assert 'PRIVATE COUNTERPARTY' not in text


@pytest.mark.parametrize('retention,seconds',RETENTIONS.items())
def test_retention_and_expiry(app,retention,seconds):
    report=save(app,retention=retention,is_private=False)
    row=app.db.get(LocalScanReport,report['token'])
    if seconds is None:assert row.expires_at is None
    else:
        assert round((row.expires_at-row.created_at).total_seconds())==seconds
        row.expires_at=now()-timedelta(seconds=1);app.db.commit()
        assert app.client.get('/api/receipts/public/'+report['token']).status_code==404
        assert app.client.get('/api/receipts/reports/'+report['token']).status_code==404


def test_bulk_deletion_is_owner_and_kind_scoped_and_revokes_public(app):
    one=save(app,is_private=False)
    app.current[0]=app.users['other'];two=save(app,is_private=False)
    app.current[0]=app.users['member']
    assert app.client.post('/api/receipts/reports/delete',json={'tokens':[two['token']]}).json()['deleted']==0
    row=app.db.get(LocalScanReport,one['token']);row.report_kind='local';app.db.commit()
    assert app.client.post('/api/receipts/reports/delete',json={'all_in_scope':True}).json()['deleted']==0
    row.report_kind='receipt';app.db.commit()
    assert app.client.post('/api/receipts/reports/delete',json={'tokens':[one['token']]}).json()['deleted']==1
    assert app.client.get('/api/receipts/public/'+one['token']).status_code==404
    assert app.client.get('/api/receipts/public/'+two['token']).status_code==200


def test_market_gate_and_navigation_gate_are_independent(app):
    user=app.users['member']
    app.db.add(UserSectionPermission(user_id=user.id,section='navigation',can_view=False));app.db.commit()
    assert app.client.get('/api/receipts/context').json()['can_plan_route'] is False
    assert app.client.post('/api/receipts/route',json={'origin':'Jita','destination':'Jita'}).status_code==403
    assert save(app,route={'mode':'jump_freighter','origin':'Jita','destination':'Demo Lowsec','jump_count':2,'systems':['Jita','Demo Cyno','Demo Lowsec']})['route']['mode']=='jump_freighter'
    app.db.add(UserSectionPermission(user_id=user.id,section='market',can_view=False));app.db.commit()
    assert app.client.get('/api/receipts/context').status_code==403
    assert app.client.post('/api/receipts/parse',json={'text':purchase()}).status_code==403


@pytest.mark.parametrize('role',['quartermaster','applicant','intel_analyst','member'])
def test_real_auth_allows_personal_receipt_utility_without_private_esi(app,role):
    app.app.dependency_overrides.pop(get_current_user)
    headers={'Authorization':'Bearer '+create_access_token(str(app.users[role].id))}
    response=app.client.post('/api/receipts',json={'text':purchase()},headers=headers)
    assert response.status_code==201,response.text
    assert app.client.post('/api/receipts/parse',json={'text':purchase()},headers=headers).status_code==200


def test_gate_route_uses_local_graph_and_retains_planned_stop_names(app):
    app.db.add_all([EveSystem(system_id=30000001,name='Demo Midpoint',security_status=.8),EveSystem(system_id=30000002,name='Demo End',security_status=.7)])
    app.db.flush();app.db.add_all([EveStargate(stargate_id=1,system_id=30000142,destination_system_id=30000001),EveStargate(stargate_id=2,system_id=30000001,destination_system_id=30000002)])
    app.db.commit()
    r=app.client.post('/api/receipts/route',json={'origin':'Jita','destination':'Demo End','preference':'shortest'})
    assert r.status_code==200,r.text
    assert r.json()['jump_count']==2 and r.json()['systems']==['Jita','Demo Midpoint','Demo End'] and r.json()['source']=='planned'


def test_export_rechecks_deletion_and_closes_db_during_render(app):
    report=save(app,is_private=False)
    def render(data):
        assert not app.db.in_transaction()
        app.db.delete(app.db.get(LocalScanReport,report['token']));app.db.commit()
        return b'fake exported content'
    with patch.object(receipt_exports,'csv_content',side_effect=render):
        assert app.client.get('/api/receipts/public/'+report['token']+'/export/csv').status_code==404


def test_csv_formula_injection_protection_and_pdf_escaping(app):
    report=save(app,title='=HYPERLINK("bad")',note='@SUM(1,2)',text=purchase(item='<b>Not markup</b>',station='=CMD()'))
    data=receipt_exports.csv_content(report).decode('utf-8-sig')
    assert "'=HYPERLINK" in data and "'@SUM" in data and "'=CMD()" in data
    assert receipt_exports.pdf_content(report).startswith(b'%PDF')


def test_preview_is_unsaved_and_unknown_items_do_not_require_sde(app):
    response=app.client.post('/api/receipts/preview',json={'text':purchase()})
    assert response.status_code==200 and response.json()['groups'][0]['type_id'] is None
    assert app.db.scalar(select(func.count()).select_from(LocalScanReport))==0
    assert app.client.post('/api/receipts',json={'text':purchase(),'fuel':[{'item':'Fuel','quantity':True,'unit_price':'1'}]}).status_code==422


def test_save_rate_limit(app):
    for _ in range(10):save(app)
    assert app.client.post('/api/receipts',json={'text':purchase()}).status_code==429
