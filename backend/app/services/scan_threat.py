"""Stable hull-class display order; a taxonomy, not a fitted-combat prediction."""
from collections import Counter

ORDER = ["Titan", "Supercarrier", "Lancer Dreadnought", "Dreadnought", "Command Carrier", "Carrier", "Force Auxiliary",
         "Marauder", "Black Ops", "Faction Battleship", "Battleship", "Command Ship", "Strategic Cruiser",
         "Heavy Assault Cruiser", "Heavy Interdiction Cruiser", "Combat Recon Ship", "Force Recon Ship",
         "Attack Battlecruiser", "Combat Battlecruiser", "Battlecruiser", "Logistics", "Cruiser",
         "Command Destroyer", "Tactical Destroyer", "Interdictor", "Destroyer", "Assault Frigate", "Covert Ops",
         "Electronic Attack Ship", "Interceptor", "Logistics Frigate", "Frigate", "Corvette", "Industrial Command Ship",
         "Capital Industrial Ship", "Jump Freighter", "Freighter", "Deep Space Transport", "Blockade Runner",
         "Hauler", "Mining Barge", "Exhumer", "Expedition Frigate", "Industrial", "Shuttle", "Capsule", "Unknown class"]
RANK={name.casefold():i for i,name in enumerate(ORDER)}
FACTION_BATTLESHIPS={"rattlesnake","vindicator","machariel","nightmare","bhaalgorn","barghest","nestor","thunderchild",
                    "raven state issue","tempest tribal issue","apocalypse imperial issue","megathron federate issue"}

def hull_class(row):
    group=row.get("group_name") or "Unknown class"
    name=row.get("type_name", "").casefold()
    if group.casefold()=="battleship" and (name in FACTION_BATTLESHIPS or "navy issue" in name or "fleet issue" in name):
        return "Faction Battleship"
    return group

def order_snapshot(snapshot):
    rows=[{**r,"threat_class":hull_class(r)} for r in snapshot.get("rows",[])]
    rows.sort(key=lambda r:(0 if r["category"]=="ships" else 1,
        RANK.get(r["threat_class"].casefold(),len(ORDER)-1) if r["category"]=="ships" else 0,
        -r["count"],r["type_name"].casefold(),r.get("type_id") or 0))
    classes=Counter()
    for row in rows:
        if row["category"]=="ships":classes[row["threat_class"]]+=row["count"]
    return {**snapshot,"rows":rows,"classes":[{"name":name,"count":count} for name,count in sorted(classes.items(),key=lambda p:(RANK.get(p[0].casefold(),len(ORDER)-1),-p[1],p[0].casefold()))]}
