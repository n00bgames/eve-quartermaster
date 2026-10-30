"""Server-side snapshot search, applied after authorization and before pagination."""
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import JSON,String,select,cast,case,literal,func,and_,or_,exists,type_coerce
from sqlalchemy.dialects.postgresql import JSONB
from app.models import BattleReportShare,EveGroup,EveType,EveCategory
from app.services.ship_hulls import capital_group_ids

RANGES={'solo':(1,1),'2-4':(2,4),'5-9':(5,9),'10-25':(10,25),'26-50':(26,50),
 '51-100':(51,100),'101-150':(101,150),'151-250':(151,250),'251-350':(251,350),
 '351-500':(351,500),'501-1000':(501,1000),'1001+':(1001,None)}

class SearchFilters(BaseModel):
    model_config=ConfigDict(extra='forbid')
    side:Literal['my','hostile']='my'
    match:Literal['all','any']='all'
    pilot_name:str=Field(default='',max_length=120)
    combat_corporation:str=Field(default='',max_length=120)
    alliance_name:str=Field(default='',max_length=120)
    system_name:str=Field(default='',max_length=120)
    class_key:str=Field(default='',max_length=40,pattern=r'^(|capitals|deployables|structures|g:[1-9][0-9]{0,9})$')
    type_id:int|None=Field(default=None,gt=0,le=2147483647)
    combatants:Literal['','solo','2-4','5-9','10-25','26-50','51-100','101-150','151-250','251-350','351-500','501-1000','1001+']=''

def supported_groups():
    categories=select(EveCategory.category_id).where(func.lower(EveCategory.name).in_(
        ['ship','deployable','structure','starbase','sovereignty structure','orbital']))
    return or_(EveGroup.category_id.in_([6,22,23,40,46,65]),EveGroup.category_id.in_(categories))

def class_groups(db,key):
    if not key:return None
    if key=='capitals':return capital_group_ids(db)
    if key in {'deployables','structures'}:
        ids=[22] if key=='deployables' else [23,40,46,65]
        return set(db.scalars(select(EveGroup.group_id).where(EveGroup.category_id.in_(ids))))
    gid=int(key[2:])
    if db.scalar(select(EveGroup.group_id).where(EveGroup.group_id==gid,supported_groups())) is None:
        raise HTTPException(422,'Choose an imported ship, deployable or structure class')
    return {gid}

def validate_hull(db,search):
    groups=class_groups(db,search.class_key)
    if search.type_id is not None:
        item=db.scalar(select(EveType).join(EveGroup,EveGroup.group_id==EveType.group_id).where(EveType.type_id==search.type_id,supported_groups()))
        if item is None or (groups is not None and item.group_id not in groups):
            raise HTTPException(422,'Choose a hull/object belonging to the selected class')
    return groups

def options(db,key=''):
    groups=class_groups(db,key)
    rows=db.execute(select(EveGroup.group_id,EveGroup.name,EveGroup.category_id).where(supported_groups(),EveGroup.published.is_(True)).order_by(EveGroup.name)).all()
    classes=[{'key':'capitals','name':'Any capital hull','section':'Ship classes'},
        {'key':'deployables','name':'Any deployable','section':'Deployables'},
        {'key':'structures','name':'Any structure','section':'Structures'}]
    for gid,name,category in rows:
        classes.append({'key':f'g:{gid}','name':name,'section':'Ship classes' if category==6 else 'Deployables' if category==22 else 'Structures'})
    types=[]
    if groups is not None:
        types=[{'id':tid,'name':name} for tid,name in db.execute(select(EveType.type_id,EveType.name)
            .where(EveType.group_id.in_(groups),EveType.published.is_(True)).order_by(EveType.name))]
    return {'classes':classes,'types':types,'combatant_ranges':[{'key':k,'label':'Solo' if k=='solo' else f'{k} Combatants'} for k in RANGES]}

def conditions(db,search):
    groups=validate_hull(db,search)
    postgres=db.get_bind().dialect.name=='postgresql'
    json_type=JSONB if postgres else JSON
    doc=cast(BattleReportShare.report_payload,JSONB) if postgres else BattleReportShare.report_payload
    battle=doc['report']
    def array(expr,name,text=False):
        if postgres:
            safe=case((func.jsonb_typeof(expr)=='array',expr),else_=cast(literal('[]'),JSONB))
            source=func.jsonb_array_elements_text(safe) if text else func.jsonb_array_elements(safe)
        else:
            safe=case((func.json_type(expr)=='array',expr),else_=func.json_array())
            source=func.json_each(safe)
        rows=source.table_valued('value').alias(name)
        return rows,(rows.c.value if text else type_coerce(rows.c.value,json_type))
    def value(row,key):return cast(row[key].as_string(),String)
    def like(expr,term):
        term=term.strip().replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        return expr.ilike('%'+term+'%',escape='\\')
    side='0' if search.side=='my' else '1'
    hull=search.type_id is not None or bool(search.class_key)
    def typed(tid,gid=None):
        if search.type_id is not None:return tid==str(search.type_id)
        if groups is None:return literal(True)
        sde=tid.in_(select(cast(EveType.type_id,String)).where(EveType.group_id.in_(groups)))
        return or_(gid.in_([str(x) for x in groups]),and_(gid.is_(None),sde)) if gid is not None else sde
    def ships(p):
        entries,obj=array(p['ships'],'br_hulls')
        known=exists(select(1).select_from(entries).where(typed(value(obj,'type_id'),value(obj,'ship_group_id'))))
        # Older snapshots retained hull names but not structured per-pilot ship rows.
        labels,label=array(p['ship_type_names'],'br_hull_names',text=True)
        type_query=select(EveType.name).where(EveType.type_id==search.type_id) if search.type_id else select(EveType.name).where(EveType.group_id.in_(groups))
        legacy=exists(select(1).select_from(labels).where(cast(label,String).in_(type_query)))
        return or_(known,and_(~exists(select(1).select_from(entries)),legacy))
    def details(row,timeline=False):
        terms=[]
        for term,field in [(search.pilot_name,'victim_name' if timeline else 'character_name'),
            (search.combat_corporation,'victim_corporation_name' if timeline else 'corporation_name'),
            (search.alliance_name,'victim_alliance_name' if timeline else 'alliance_name')]:
            if term.strip():
                condition=like(value(row,field),term)
                if timeline and field=='victim_name':condition=and_(value(row,'victim_character_id').is_not(None),value(row,'victim_character_id')!='0',condition)
                terms.append(condition)
        if hull:terms.append(typed(value(row,'victim_ship_type_id')) if timeline else ships(row))
        return (and_ if search.match=='all' else or_)(*terms)
    result=[]
    has_identity=any(s.strip() for s in [search.pilot_name,search.combat_corporation,search.alliance_name])
    if has_identity or hull:
        participants,p=array(battle['participants'],'br_pilots')
        pilots=exists(select(1).select_from(participants).where(value(p,'side')==side,details(p)))
        timeline,t=array(battle['timeline'],'br_victims')
        victims=exists(select(1).select_from(timeline).where(value(t,'victim_side')==side,details(t,True)))
        matches=[pilots,victims]
        if hull and (not has_identity or search.match=='any'):
            compositions,c=array(battle['composition'],'br_composition')
            matches.append(exists(select(1).select_from(compositions).where(value(c,'side')==side,typed(value(c,'ship_type_id'),value(c,'ship_group_id')))))
        result.append(or_(*matches))
    if search.combatants:
        participants,p=array(battle['participants'],'br_counts')
        count=select(func.count(func.distinct(value(p,'character_id')))).select_from(participants).where(
            value(p,'side')==side,value(p,'character_id').is_not(None),value(p,'character_id').notin_(['','0'])).correlate(BattleReportShare).scalar_subquery()
        low,high=RANGES[search.combatants];result.append(count>=low)
        if high is not None:result.append(count<=high)
    if search.system_name.strip():
        systems,s=array(battle['systems'],'br_systems')
        timeline,t=array(battle['timeline'],'br_places')
        result.append(or_(exists(select(1).select_from(systems).where(like(value(s,'system_name'),search.system_name))),
            exists(select(1).select_from(timeline).where(like(value(t,'system_name'),search.system_name)))))
    return result

def summary(payload,side='my'):
    report=payload.get('report') or {};report=report if isinstance(report,dict) else {};participants=report.get('participants') or []
    counts={str(n):len({p.get('character_id') for p in participants if isinstance(p,dict) and p.get('side')==n and p.get('character_id')}) for n in (0,1)}
    chosen=0 if side=='my' else 1
    names=sorted({r['ship_type_name'] for r in (report.get('composition') or []) if isinstance(r,dict) and r.get('side')==chosen and r.get('ship_type_name')})
    return {'battle_start':report.get('start_time'),'battle_end':report.get('end_time'),
        'systems':[s.get('system_name') for s in (report.get('systems') or []) if isinstance(s,dict) and s.get('system_name')],
        'my_pilots':counts['0'],'hostile_pilots':counts['1'],'side':side,'side_hulls':names[:8],'side_hull_types':len(names)}
