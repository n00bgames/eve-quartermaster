from urllib.parse import quote
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload
from app.models import EveConstellation, EveStation, EveStargate, EveSystem, EveType
from app.models.mission_atlas import EveAgent
from app.services.navigation import serialize_system
from app.services.atlas_distances import gate_distances

DIVISIONS = {22: "Distribution", 23: "Mining", 24: "Security", 18: "Research"}


def edges(db):
    return [list(row) for row in db.execute(select(EveStargate.system_id, EveStargate.destination_system_id)
        .where(EveStargate.destination_system_id.is_not(None))).all()]


def system_query():
    return select(EveSystem).options(selectinload(EveSystem.constellation).selectinload(EveConstellation.region))


def catalog(db):
    stations = dict(db.execute(select(EveStation.system_id, func.count()).group_by(EveStation.system_id)).all())
    agents = dict(db.execute(select(EveAgent.system_id, func.count()).group_by(EveAgent.system_id)).all())
    systems = [{**serialize_system(row), "station_count": stations.get(row.system_id, 0),
        "agent_count": agents.get(row.system_id, 0)} for row in db.scalars(system_query()).all()]
    return dict(systems=systems, edges=edges(db), source="SDE", agent_count=sum(agents.values()))


def agent_payload(agent, system=None, station=None):
    return dict(agent_id=agent.agent_id, name=agent.name, level=agent.level,
        corporation_id=agent.corporation_id, corporation_name=agent.corporation_name,
        faction_id=agent.faction_id, division_id=agent.division_id,
        division=DIVISIONS.get(agent.division_id, f"Division {agent.division_id}"),
        agent_type_id=agent.agent_type_id, is_locator=agent.is_locator,
        system_id=agent.system_id, system_name=system.name if system else None,
        security_status=system.security_status if system else None,
        station_name=station.name if station else None, location_id=agent.location_id)


def find_agents(db, q="", level=None, division_id=None, corporation_id=None,
                system_id=None, highsec_only=False, origin_id=None, max_jumps=None, offset=0, limit=100):
    statement = select(EveAgent, EveSystem, EveStation).outerjoin(EveSystem, EveSystem.system_id == EveAgent.system_id)\
        .outerjoin(EveStation, EveStation.station_id == EveAgent.location_id)
    if q.strip():
        term = f"%{q.strip()}%"
        statement = statement.where(or_(EveAgent.name.ilike(term), EveAgent.corporation_name.ilike(term), EveSystem.name.ilike(term)))
    for column, value in ((EveAgent.level, level), (EveAgent.division_id, division_id),
                           (EveAgent.corporation_id, corporation_id), (EveAgent.system_id, system_id)):
        if value is not None:
            statement = statement.where(column == value)
    if highsec_only:
        statement = statement.where(EveSystem.security_status >= .45)
    distances = gate_distances(origin_id, edges(db)) if origin_id is not None else None
    rows = []
    for agent, system, station in db.execute(statement).all():
        jumps = distances.get(agent.system_id) if distances is not None else None
        if max_jumps is not None and (jumps is None or jumps > max_jumps):
            continue
        rows.append({**agent_payload(agent, system, station), "jumps": jumps})
    rows.sort(key=lambda row: (row["jumps"] is None, row["jumps"] or 0, row["name"].lower(), row["agent_id"]))
    return dict(agents=rows[offset:offset+limit], total=len(rows), offset=offset,
        directory_count=db.scalar(select(func.count()).select_from(EveAgent)) or 0)


def system_detail(db, system_id):
    system = db.scalar(system_query().where(EveSystem.system_id == system_id))
    if system is None:
        return None
    return dict(system=serialize_system(system),
        stations=[dict(station_id=s.station_id, name=s.name, corporation_id=s.owner_id,
            corporation_name=s.owner_name, operation=s.operation_name)
            for s in db.scalars(select(EveStation).where(EveStation.system_id == system_id).order_by(EveStation.name))],
        agents=find_agents(db, system_id=system_id, limit=1000)["agents"],
        links=dict(dotlan=f"https://evemaps.dotlan.net/system/{quote(system.name, safe='')}",
            zkill=f"https://zkillboard.com/system/{system_id}/"))


def corporation_directory(db, q=""):
    # Agent and station owners are NPC corporations; do not expose player corporation records.
    names = dict(db.execute(select(EveAgent.corporation_id, EveAgent.corporation_name).distinct()).all())
    for corp_id, name in db.execute(select(EveStation.owner_id, EveStation.owner_name).distinct()):
        if corp_id and name:
            names.setdefault(corp_id, name)
    return [dict(corporation_id=k, name=v) for k,v in sorted(names.items(), key=lambda item:item[1].lower())
            if not q or q.lower() in v.lower()]


def decorate_offers(db, offers):
    ids = {row["type_id"] for row in offers}
    ids.update(item["type_id"] for row in offers for item in row.get("required_items", []))
    names = dict(db.execute(select(EveType.type_id, EveType.name).where(EveType.type_id.in_(ids))).all()) if ids else {}
    return [{**row, "name": names.get(row["type_id"], f"Type {row['type_id']}"),
        "required_items": [{**item, "name": names.get(item["type_id"], f"Type {item['type_id']}")}
            for item in row.get("required_items", [])]} for row in offers]
