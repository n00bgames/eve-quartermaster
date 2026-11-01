"""Read-only PvP reference built from imported SDE and explicit scenarios."""
from collections import Counter
from copy import deepcopy
import math
from fastapi import HTTPException
from sqlalchemy import func, select
from app.models import EveType,EveGroup,EveCategory,EveTypeDogmaAttribute,EveDogmaAttribute
from app.services import dscan
from app.services.matchup_knowledge import HULLS,COUNTERS,SOURCES,REVIEWED,WEAPONS

DAMAGE=('em','thermal','kinetic','explosive')
SUFFIX=('Em','Thermal','Kinetic','Explosive')

def ships():
    return select(EveType,EveGroup.name.label('class_name')).join(EveGroup,EveType.group_id==EveGroup.group_id).join(EveCategory,EveGroup.category_id==EveCategory.category_id).where(EveCategory.category_id==6,EveType.published.is_(True))

def identity(item,group):
    return {'type_id':item.type_id,'name':item.name,'class_name':group,'curated':item.name.casefold() in HULLS}

def search(db,q):
    pattern='%'+q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
    query=ships().where(EveType.name.ilike(pattern,escape='\\')).order_by(func.lower(EveType.name)).limit(30)
    return [identity(item,group) for item,group in db.execute(query)]

def catalog(db):
    names=list(HULLS)
    starters=[identity(item,group) for item,group in db.execute(ships().where(func.lower(EveType.name).in_(names)).order_by(EveType.name))]
    return {'reviewed_at':REVIEWED,'sources':SOURCES,'weapons':WEAPONS,'starters':starters,
        'curated_hulls':len(HULLS),'contexts':['small_gang','fleet'],
        'limits':'Reference scenarios, not detected fits or win probabilities. Missing profiles stay unknown. No private ESI access or scan storage.'}

def card(db,type_id,context):
    row=db.execute(ships().where(EveType.type_id==type_id)).first()
    if row is None:raise HTTPException(404,'Published ship hull not found in imported SDE')
    item,group=row
    attributes=dict(db.execute(select(EveDogmaAttribute.name,EveTypeDogmaAttribute.value).join(EveTypeDogmaAttribute,EveTypeDogmaAttribute.attribute_id==EveDogmaAttribute.attribute_id).where(EveTypeDogmaAttribute.type_id==type_id)).all())
    layers=[]
    for key,prefix in [('shield','shield'),('armor','armor'),('hull','')]:
        values={}
        for damage,suffix in zip(DAMAGE,SUFFIX):
            name=(prefix+suffix+'DamageResonance') if prefix else damage+'DamageResonance'
            value=attributes.get(name)
            values[damage]=round((1-value)*100,2) if value is not None and math.isfinite(value) and 0<=value<=1 else None
        complete=all(v is not None for v in values.values())
        low=min(values.values()) if complete else None
        layers.append({'name':key,'resists':values,'weakest':[k for k,v in values.items() if complete and v==low]})
    profiles=deepcopy(HULLS.get(item.name.casefold(),[]))
    for profile in profiles:
        profile['plan']=profile[context]
        profile['counter_tools']=[{**COUNTERS[key],'plan':COUNTERS[key][context]} for key in profile.pop('counters')]
        profile['source']=SOURCES[item.name.casefold()]
        profile['reviewed_at']=REVIEWED
    return {**identity(item,group),'layers':layers,'variants':profiles,'context':context,
        'fact_source':SOURCES['sde'],'resist_note':'Imported base hull resistances only: no fitted modules, skills, heat, links or local effects. The lowest base resist is a starting hypothesis, not a fitted ammo recommendation.'}

def analyze(db,text):
    objects,ignored=dscan.parse(text)
    snapshot=dscan.summarize(db,objects,{})
    return project(snapshot,ignored)

def project(snapshot,ignored=None):
    rows=[{key:r[key] for key in ('type_id','type_name','count','observed','manual')} for r in snapshot.get('rows',[]) if r.get('category')=='ships']
    rows.sort(key=lambda r:(-r['count'],r['type_name']))
    roles=Counter()
    covered=0
    for row in rows:
        variants=HULLS.get(row['type_name'].casefold(),[])
        if variants:covered+=row['count']
        for tag in {tag for v in variants for tag in v['tags']}:roles[tag]+=row['count']
    return {'ships':rows,'total':sum(r['count'] for r in rows),'covered':covered,
        'possible_roles':[{'name':tag,'count':n} for tag,n in sorted(roles.items(),key=lambda x:(-x[1],x[0]))],
        'unresolved':snapshot.get('unresolved_count',0),'ignored':ignored or [],
        'note':'Possible roles count each hull once per role across its reference variants; totals overlap. They do not confirm fittings, pilots or allegiance. Cloaked ships and combat recons may be absent; manual additions are not detections.'}
