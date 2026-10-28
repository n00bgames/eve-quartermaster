import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.models import Base
from app.api import sde
from app.db.session import get_db
from app.services.sde_importer import import_sde


def test_full_dataset_and_nested_counts_match_processed_and_stored_rows(tmp_path):
    data={
        'types.yaml':{34:{'name':{'en':'Tritanium'}},35:{'name':{'en':'Pyerite'}}},
        'dogmaAttributes.yaml':{10:{'name':'exampleAttribute'}},
        'dogmaEffects.yaml':{20:{'name':'exampleEffect','modifierInfo':[{'func':'ItemModifier','modifiedAttributeID':10}]}},
        'typeDogma.yaml':{34:{'dogmaAttributes':[{'attributeID':10,'value':5}], 'dogmaEffects':[{'effectID':20,'isDefault':True}]}},
        'blueprints.yaml':{1000:{'activities':{'manufacturing':{'time':100,'materials':[{'typeID':34,'quantity':2}],'products':[{'typeID':35,'quantity':1}]},'unsupported_example':{}}}},
        'planetSchematics.yaml':{1:{'cycleTime':900,'types':{34:{'isInput':True,'quantity':2},35:{'isInput':False,'quantity':1}}}},
        'mapPlanets.yaml':{40000001:{'solarSystemID':30000142,'celestialIndex':1}},
        'mapMoons.yaml':{40000002:{'solarSystemID':30000142,'celestialIndex':1,'orbitIndex':1}},
        'mapAsteroidBelts.yaml':{40000003:{'solarSystemID':30000142,'celestialIndex':1,'orbitIndex':1}},
        'npcCharacters.yaml':{5001:{'name':{'en':'Example Agent'},'corporationID':1000169,'locationID':60000001,'agent':{'level':1,'divisionID':18}}},
        'npcCorporations.yaml':{1000169:{'name':{'en':'Republic Military School'}}},
    }
    for name,content in data.items():(tmp_path/name).write_text(yaml.safe_dump(content),encoding='utf-8')
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        checkpoints=[]
        result=import_sde(str(tmp_path),db,sections={'types','dogma','blueprints','planet_schematics','celestials','agents'},progress=lambda stats,stage:checkpoints.append((stage,stats.to_dict())))
        assert result['types']==2 and result['agents']==1 and result['celestials']==3
        expected={'celestial_planets':1,'celestial_moons':1,'celestial_belts':1,'dogma_modifiers':1,'type_dogma_default_effects':1,
            'blueprint_products':1,'planet_schematic_outputs':1,'planet_schematic_inputs':1,'blueprint_activities':1,'activity_inputs':1,'skipped_activities':1}
        for key,value in expected.items():assert result[key]==value,key
        assert checkpoints[-1][0]=='complete' and checkpoints[-1][1]==result
        app=FastAPI();app.include_router(sde.router);app.dependency_overrides[sde.require_admin]=lambda:None;app.dependency_overrides[get_db]=lambda:db
        with TestClient(app) as client:
            response=client.get('/sde/status');assert response.status_code==200
            stored=response.json()
            for key,value in expected.items():
                if key!='skipped_activities':assert stored[key]==value,key
            assert stored['agents']==1 and stored['celestials']==3
    engine.dispose()
