"""Bounded public loss-fit samples and conditional counters for Matchups."""
import asyncio
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
import json
import math
import time

import httpx
from fastapi import HTTPException
from sqlalchemy import select

from app.models import CharacterFitting, CharacterFittingItem, EveGroup, EveType
from app.services import fitting_simulator as simulator
from app.services.killboard_sync import ZKILLBOARD_BASE_URL, ZKILLBOARD_HEADERS, parse_killmail_time
from app.services.matchup_weapons import fitted_weapon_family

SAMPLE_LIMIT = 40
EXAMPLE_LIMIT = 3
MAX_PAGE_BYTES = 32 * 1024 * 1024
ASSUMPTIONS = (
    "EQM estimate with all imported skills at V, recorded loaded charges, no heat, implants or boosts. "
    "Propulsion and special modes are off. EHP uses an even damage mix. "
    "DPS is a cycle estimate before reload and application. Script and Dogma effect coverage varies."
)
SLOT_FLAGS = {
    **{start + index: f"{prefix}{index}" for start, prefix in (
        (11, "LoSlot"), (19, "MedSlot"), (27, "HiSlot"),
        (92, "RigSlot"), (125, "SubSystemSlot"),
    ) for index in range(8)},
    87: "DroneBay",
    158: "FighterBay",
}


def samples_from_page(page: list, type_id: int) -> list[dict]:
    samples = []
    seen = set()
    for row in page[:SAMPLE_LIMIT]:
        if not isinstance(row, dict) or not isinstance(row.get("victim"), dict):
            continue
        victim = row["victim"]
        meta = row.get("zkb")
        if victim.get("ship_type_id") != type_id or not isinstance(meta, dict) or meta.get("npc") is True:
            continue
        kill_id = row.get("killmail_id")
        if type(kill_id) is not int or kill_id <= 0 or kill_id in seen:
            continue
        try:
            date = parse_killmail_time(row.get("killmail_time")).isoformat()
        except ValueError:
            continue
        items = victim.get("items")
        if not isinstance(items, list) or len(items) > 500:
            continue
        equipment = []
        for item in items:
            if not isinstance(item, dict):
                continue
            flag, item_type = item.get("flag"), item.get("item_type_id")
            dropped, destroyed = item.get("quantity_dropped", 0), item.get("quantity_destroyed", 0)
            if not all(type(value) is int for value in (flag, item_type, dropped, destroyed)):
                continue
            if flag in SLOT_FLAGS and item_type > 0 and 0 < dropped + destroyed <= 1_000_000:
                equipment.append((flag, item_type, dropped + destroyed))
        if not any(flag not in (87, 158) for flag, _, _ in equipment):
            continue
        seen.add(kill_id)
        value = meta.get("totalValue")
        samples.append({
            "killmail_id": kill_id,
            "killmail_time": date,
            "estimated_loss_isk": value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None,
            "equipment": equipment,
        })
    return samples


class LossFitSource:
    """One paced request at a time, with a bounded cache shared across users."""

    def __init__(self):
        self.lock = asyncio.Lock()
        self.cache = OrderedDict()
        self.next_request = 0.0

    async def sample(self, type_id: int, delay: float) -> dict:
        cached = self.cache.get(type_id)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        try:
            await asyncio.wait_for(self.lock.acquire(), timeout=3)
        except TimeoutError as exc:
            raise HTTPException(503, "Fit research is busy. Try again shortly.", headers={"Retry-After": "5"}) from exc
        try:
            cached = self.cache.get(type_id)
            if cached and cached[0] > time.monotonic():
                return cached[1]
            wait = self.next_request - time.monotonic()
            if wait > 2:
                raise HTTPException(503, "Fit research is cooling down. Try again shortly.", headers={"Retry-After": str(math.ceil(wait))})
            await asyncio.sleep(max(0.0, wait))
            url = f"{ZKILLBOARD_BASE_URL}/losses/shipTypeID/{type_id}/npc/0/page/1/"
            try:
                async with asyncio.timeout(15):
                    async with httpx.AsyncClient(headers=ZKILLBOARD_HEADERS, timeout=10) as client:
                        async with client.stream("GET", url) as response:
                            if response.status_code == 429:
                                self.next_request = time.monotonic() + 60
                                raise HTTPException(503, "zKillboard is rate limiting fit research. Try again in a minute.", headers={"Retry-After": "60"})
                            response.raise_for_status()
                            data = bytearray()
                            async for chunk in response.aiter_bytes():
                                data.extend(chunk)
                                if len(data) > MAX_PAGE_BYTES:
                                    raise ValueError("Oversized loss page")
                page = json.loads(data)
                if not isinstance(page, list):
                    raise ValueError("Invalid loss page")
            except (httpx.HTTPError, ValueError, TimeoutError) as exc:
                raise HTTPException(502, "zKillboard did not return a usable loss sample. Try again shortly.") from exc
            finally:
                self.next_request = max(self.next_request, time.monotonic() + max(1.0, delay))

            result = {
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "scanned_count": min(SAMPLE_LIMIT, len(page)),
                "samples": samples_from_page(page, type_id),
            }
            self.cache[type_id] = (time.monotonic() + 3600, result)
            self.cache.move_to_end(type_id)
            while len(self.cache) > 128:
                self.cache.popitem(last=False)
            return result
        finally:
            self.lock.release()


source = LossFitSource()


def reconstruct(equipment, types):
    slots = defaultdict(list)
    for flag, item_type, quantity in equipment:
        slots[flag].append((item_type, quantity))
    items, ambiguous = [], False
    for flag, rows in sorted(slots.items()):
        slot = SLOT_FLAGS[flag]
        if slot in {"DroneBay", "FighterBay"}:
            quantities = Counter()
            for item_type, quantity in rows:
                quantities[item_type] += quantity
            items.extend((slot, item_type, quantity, None) for item_type, quantity in quantities.items())
            continue
        modules = [item_type for item_type, _ in rows if types.get(item_type, ("", "", None, None))[2] != 8]
        charges = {item_type for item_type, _ in rows if item_type not in modules}
        if len(modules) != 1 or len(charges) > 1:
            ambiguous = True
        for item_type in modules:
            charge = next(iter(charges)) if len(modules) == 1 and len(charges) == 1 else None
            items.append((slot, item_type, 1, charge))
    return items, ambiguous


def fit_counters(families, groups, context, ship_class):
    fleet = context == "fleet"
    if ship_class in {"Titan", "Supercarrier"}:
        return [{
            "hull": "Onyx",
            "fit": "Focused Warp Disruption Script, shield buffer and cap support",
            "plan": "Coordinate focused points and capital-capable damage." if fleet else "Hold only with a supported heavy tackle plan and escalation ready.",
            "condition": "Check focused point range, fighter pressure and hostile escalation before committing.",
        }]
    results = []
    if families & {"Blasters", "Autocannons", "Pulse lasers", "Rockets", "Heavy assault missiles"}:
        results.append({
            "hull": "Orthrus" if fleet else "Vagabond",
            "fit": "Microwarpdrive and long point",
            "plan": "Screen the brawlers and hold them for the damage wing." if fleet else "Control separation and hold point while you apply from range.",
            "condition": "Check loaded ammo and hostile tackle before counting on the range advantage.",
        })
    if families & {"Railguns", "Artillery", "Beam lasers", "Entropic disintegrators"}:
        results.append({
            "hull": "Arbitrator",
            "fit": "Tracking disruptor with the appropriate script",
            "plan": "Assign disruptors to the main turret threats." if fleet else "Use range or tracking disruption to make the guns apply worse.",
            "condition": "Use the script that addresses the engagement. Drones and missiles can still apply.",
        })
    if any("missile" in family.casefold() for family in families) or families & {"Rockets", "Torpedoes"}:
        results.append({
            "hull": "Arbitrator",
            "fit": "Guidance disruptor with a range or precision script",
            "plan": "Disrupt the launchers covering your tackle screen." if fleet else "Pressure missile range or application while you control distance.",
            "condition": "Check flight range and target size. Rapid launchers can still punish small tackle.",
        })
    if groups & {"Armor Repair Unit", "Shield Booster", "Remote Armor Repairer", "Remote Shield Booster"}:
        results.append({
            "hull": "Armageddon" if fleet else "Curse",
            "fit": "Energy neutralizers with tackle support",
            "plan": "Concentrate neut pressure on the repair chain." if fleet else "Pressure the repair capacitor while keeping an exit.",
            "condition": "Requires neut range. Cap injection and other repairs can sustain the target.",
        })
    if families & {"Combat drones", "Fighters"}:
        results.append({
            "hull": "Cerberus",
            "fit": "Rapid light launchers with tackle support",
            "plan": "Assign an application wing to drones or fighters threatening your screen." if fleet else "Clear exposed drones if you can do so without being tackled.",
            "condition": "A damage-control option against deployed craft. Killing them may leave the parent hull free to escape.",
        })
    if not results and groups & {"Stasis Web", "Warp Scrambler", "Warp Disrupt Field Generator", "Sensor Dampener"}:
        results.append({
            "hull": "Celestis",
            "fit": "Range-scripted remote sensor dampeners",
            "plan": "Coordinate damps and projection against the hostile tackle or EWAR ship.",
            "condition": "Check lock range after damps and keep support outside the confirmed tackle envelope.",
        })
    return results


def render_examples(db, type_id, context, sample):
    samples = sample["samples"]
    type_ids = {type_id} | {item_type for row in samples for _, item_type, _ in row["equipment"]}
    type_rows = db.execute(select(
        EveType.type_id, EveType.name, EveGroup.name, EveGroup.category_id, EveGroup.group_id,
    ).join(EveGroup, EveGroup.group_id == EveType.group_id).where(EveType.type_id.in_(type_ids)))
    types = {row[0]: tuple(row[1:]) for row in type_rows}
    families = Counter()
    selected = []
    signatures = set()
    for row in samples:
        items, ambiguous = reconstruct(row["equipment"], types)
        if not items:
            continue
        observed = set()
        for flag, item_type, _, _ in items:
            name, group, category, _ = types.get(item_type, ("", "", None, None))
            family = fitted_weapon_family(name, group) if flag.startswith("HiSlot") else None
            if flag == "DroneBay" and category == 18 and group == "Combat Drone":
                family = "Combat drones"
            if flag == "FighterBay" and category == 87:
                family = "Fighters"
            if family:
                observed.add(family)
        families.update(observed)
        signature = tuple(sorted((flag.rstrip("0123456789"), item_type, qty) for flag, item_type, qty, _ in items))
        if signature not in signatures and len(selected) < EXAMPLE_LIMIT:
            signatures.add(signature)
            selected.append((row, items, observed, ambiguous))

    fit_type_ids = {type_id}
    for _, items, _, _ in selected:
        fit_type_ids.update(item_type for _, item_type, _, _ in items)
        fit_type_ids.update(charge for _, _, _, charge in items if charge)
    skills = dict(db.execute(select(EveType.type_id, EveType.name).join(EveGroup).where(
        EveGroup.category_id == 16, EveType.published.is_(True),
    )).all()) if selected else {}
    dogma = simulator.dogma_for_types(db, fit_type_ids | set(skills)) if selected else {}
    if type_id in dogma:
        # The fitting engine scales hull modifiers by skill level. These SDE
        # role attributes are flat percentages, so apply them once in this V/V reference.
        dogma[type_id] = {
            name: value / 5 if name.startswith("shipbonusrole") or name == "rookieshieldresistbonus" else value
            for name, value in dogma[type_id].items()
        }
    effects = simulator.dogma_effects_for_types(db, fit_type_ids) if selected else {}
    volumes = simulator.type_volumes(db, fit_type_ids) if selected else {}
    ship_mass = simulator.type_masses(db, {type_id}).get(type_id) if selected else None
    names = {key: value[0] for key, value in types.items()} | skills
    groups = {key: value[1] for key, value in types.items()}
    group_ids = {key: value[3] for key, value in types.items()}

    examples = []
    for row, items, observed, ambiguous in selected:
        fitting = CharacterFitting(ship_type_id=type_id)
        modules = []
        for index, (flag, item_type, quantity, charge) in enumerate(items, 1):
            group = groups.get(item_type, "")
            state = "online" if group in {"Propulsion Module", "Siege Module", "Bastion Module", "Triage Module", "Industrial Core", "Damage Control"} else "active"
            fitting.items.append(CharacterFittingItem(
                id=index, flag=flag, type_id=item_type, quantity=quantity,
                charge_type_id=charge, simulation_state=state,
            ))
            modules.append({
                "slot": flag, "name": names.get(item_type, f"Unknown type {item_type}"),
                "quantity": quantity, "charge": names.get(charge, f"Unknown type {charge}") if charge else None,
            })
        fitted_types = {item_type for _, item_type, _, _ in items}
        missing = {type_id} | fitted_types | {charge for _, _, _, charge in items if charge}
        missing.difference_update(dogma)
        stats = None
        if skills and not missing and not ambiguous:
            calculated = simulator.compute_fitting_stats(
                fitting, dogma, names, groups, dict.fromkeys(skills, 5),
                dict.fromkeys(skills.values(), 5), volumes, ship_mass=ship_mass,
                dogma_effects=effects, type_group_ids=group_ids, use_recorded_charges=True,
            )
            stats = {key: calculated[key] for key in ("offense", "defense", "mobility", "targeting")}
            for weapon in stats["offense"]["weapons"]:
                if weapon["group"] != "Combat Drone" and not weapon.get("charge_name") and weapon.get("dps", 0) == 0:
                    stats["offense"]["total_dps"] = None
                    stats["offense"]["volley"] = None
                    break
            # Fighter, smartbomb and special weapon damage is not an aggregate DPS promise.
            if observed & {"Fighters", "Smartbombs", "Doomsdays", "Bomb launchers", "Breacher pods", "Vorton projectors"}:
                stats["offense"]["total_dps"] = None
                stats["offense"]["volley"] = None
        examples.append({
            **{key: row[key] for key in ("killmail_id", "killmail_time", "estimated_loss_isk")},
            "modules": modules,
            "weapon_families": sorted(observed),
            "stats": stats,
            "counter_fits": fit_counters(observed, {groups.get(k, "") for k in fitted_types}, context, groups.get(type_id)),
        })
    return {
        "checked_at": sample["checked_at"], "scanned_count": sample["scanned_count"],
        "sample_count": len(samples),
        "observed_weapons": [{"name": name, "count": count} for name, count in families.most_common()],
        "assumptions": ASSUMPTIONS, "examples": examples,
    }
