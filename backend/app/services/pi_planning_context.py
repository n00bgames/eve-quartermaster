from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import CharacterSkill, EvePlanetSchematic, EvePlanetSchematicInput, EveTypeDogmaAttribute, PlanetaryColony, PlanetaryPin
from app.services.pi_catalog import FALLBACK_PINS, PLANET_TYPES, make_catalog, pin_catalog
from app.services.planetary_industry import extractor_dogma_factors, extractor_program_projection


def build_context(db: Session, characters: list) -> dict:
    # Reuse the existing SDE serializer; no private token or account fields enter snapshots.
    from app.api.planetary_industry import serialize_schematic

    ids = {c.id for c in characters}
    rows = list(db.scalars(select(EvePlanetSchematic).options(selectinload(EvePlanetSchematic.output_type), selectinload(EvePlanetSchematic.inputs).selectinload(EvePlanetSchematicInput.item_type))).all())
    catalog = make_catalog([serialize_schematic(r) for r in rows])
    overrides = {}
    for t, a, value in db.execute(select(EveTypeDogmaAttribute.type_id, EveTypeDogmaAttribute.attribute_id, EveTypeDogmaAttribute.value).where(EveTypeDogmaAttribute.type_id.in_([int(t) for t in FALLBACK_PINS]))):
        overrides.setdefault(t, {})[str(a)] = value
    skill_rows = db.scalars(select(CharacterSkill).where(CharacterSkill.character_id.in_(ids), CharacterSkill.skill_type_id.in_([2495, 2505, 33467]))).all() if ids else []
    skills = {(s.character_id, s.skill_type_id): s.active_skill_level for s in skill_rows}
    colonies = db.scalars(select(PlanetaryColony).where(PlanetaryColony.character_id.in_(ids)).options(selectinload(PlanetaryColony.pins), selectinload(PlanetaryColony.system))).all() if ids else []
    factors = extractor_dogma_factors(db, {p.type_id for c in colonies for p in c.pins if p.extractor_cycle_time})
    by_pilot, candidates = {}, {}
    stock, configured = Counter(), Counter()
    schematics = {r.schematic_id: r for r in rows}
    for colony in colonies:
        planet_type = (colony.planet_type or "").capitalize()
        observed = {"id": colony.id, "planet_id": colony.planet_id, "planet_name": colony.planet_name, "planet_type": planet_type, "upgrade_level": colony.upgrade_level, "last_synced_at": colony.last_synced_at.isoformat()}
        by_pilot.setdefault(colony.character_id, []).append(observed)
        key = str(colony.planet_id)
        candidate = None
        if planet_type in PLANET_TYPES.values():
            candidate = candidates.setdefault(key, {"key": key, "name": colony.planet_name, "planet_type": planet_type, "planet_id": colony.planet_id, "system_id": colony.solar_system_id, "security": colony.system.security_status if colony.system and colony.system.security_status is not None else .5, "diameter_km": 10000, "customs_percent": 10, "npc_tax_percent": 10, "yields": []})
        for pin in colony.pins:
            for stored in pin.contents_json or []:
                if stored.get("type_id") in catalog:
                    stock[stored["type_id"]] += max(0, stored.get("amount", 0))
            if pin.schematic_id in schematics:
                r = schematics[pin.schematic_id]
                configured[r.output_type_id] += r.output_quantity * 604800 / r.cycle_time
            if pin.extractor_product_type_id in catalog and pin.install_time and pin.expiry_time and pin.extractor_cycle_time:
                decay, noise, _ = factors[pin.type_id]
                projection = extractor_program_projection(install_time=pin.install_time, expiry_time=pin.expiry_time, cycle_time=pin.extractor_cycle_time, quantity_per_cycle=pin.extractor_qty_per_cycle, decay_factor=decay, noise_factor=noise)
                heads = len(pin.extractor_heads_json or [])
                duration = (pin.expiry_time - pin.install_time).total_seconds() / 3600
                if candidate and heads and duration > 0 and projection["program_output"] > 0 and not any(y["type_id"] == pin.extractor_product_type_id for y in candidate["yields"]):
                    candidate["yields"].append({"type_id": pin.extractor_product_type_id, "units_per_head_hour": projection["program_output"] / duration / heads, "source": "installed_program"})
    pilots = [{"character_id": c.id, "name": c.name, "ccu": skills.get((c.id, 2505), 0 if c.skills_synced_at else None), "ic": skills.get((c.id, 2495), 0 if c.skills_synced_at else None), "cce": skills.get((c.id, 33467), 0 if c.skills_synced_at else None), "skills_synced_at": c.skills_synced_at.isoformat() if c.skills_synced_at else None, "colonies": by_pilot.get(c.id, [])} for c in characters]
    return {"as_of": datetime.now(timezone.utc).isoformat(), "catalog": catalog, "pins": pin_catalog(overrides), "pilots": pilots, "planets": list(candidates.values()), "baseline": {"colonies": len(colonies), "configured_weekly_output": dict(configured), "observed_inventory": dict(stock), "note": "Configured output assumes supplied factories; inventory is the last observed ESI stock, not free recurring input."}}


def restore_snapshot(value: dict) -> tuple[dict, dict]:
    """JSON object keys are strings after persistence; restore canonical game IDs."""
    context, market = value["context"], value["market"]
    return {**context, "catalog": {int(k): v for k, v in context["catalog"].items()}, "pins": {int(k): v for k, v in context["pins"].items()}}, {**market, "books": {int(k): v for k, v in market["books"].items()}, "errors": {int(k): v for k, v in market.get("errors", {}).items()}}
