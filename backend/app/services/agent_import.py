"""Modern npcCharacters and legacy agents SDE import; never invent locations."""
from sqlalchemy import delete, select
from app.models import EveStation
from app.models.mission_atlas import EveAgent


def import_agents(source, db):
    from app.services.sde_importer import load_optional_yaml, localized_text, optional_int
    characters = load_optional_yaml(source, "npc_characters")
    modern = any(p.get("agent") for p in characters.values())
    legacy = load_optional_yaml(source, "agents") if not modern else {}
    corporations = load_optional_yaml(source, "npc_corporations")
    names = load_optional_yaml(source, "station_names") if not modern else {}
    if isinstance(names, list):
        names = {int(p["itemID"]): p.get("itemName") for p in names}
    stations = dict(db.execute(select(EveStation.station_id, EveStation.system_id)).all())
    rows = []
    for raw_id, payload in (characters if modern else legacy).items():
        agent = payload.get("agent") if modern else payload
        if not agent or not agent.get("level"):
            continue
        agent_id = int(raw_id)
        corp_id = optional_int(payload.get("corporationID"))
        if corp_id is None:
            continue
        corp = corporations.get(corp_id, {})
        location = optional_int(payload.get("locationID"))
        raw_name = names.get(agent_id)
        if isinstance(raw_name, dict):
            raw_name = raw_name.get("itemName") or raw_name.get("name")
        rows.append(dict(agent_id=agent_id,
            name=localized_text(payload.get("name"), raw_name or f"Agent {agent_id}"),
            corporation_id=corp_id, corporation_name=localized_text(corp.get("name"), f"Corporation {corp_id}"),
            faction_id=optional_int(corp.get("factionID")), division_id=optional_int(agent.get("divisionID")),
            level=int(agent["level"]), agent_type_id=optional_int(agent.get("agentTypeID")),
            is_locator=bool(agent.get("isLocator", False)), location_id=location,
            system_id=stations.get(location) or optional_int(payload.get("solarSystemID"))))
    # Preserve an existing directory if an older/incomplete source has no agent data.
    if rows:
        db.execute(delete(EveAgent))
        db.execute(EveAgent.__table__.insert(), rows)
        db.flush()
    return len(rows)
