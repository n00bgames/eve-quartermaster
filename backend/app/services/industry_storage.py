"""Conservative station storage classification for shareable industry stock.

Selections authorize direct contents only. A ship is never a storage container;
missing, cross-owner or cyclic ancestors fail closed.
"""
import re
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models import Asset, EveType, EveGroup, OwnershipEntity, CorporationDivision

CONTAINER_GROUPS = {12, 340, 448, 649}
CONTAINER_NAMES = {"cargo container", "secure cargo container", "audit log secure container", "freight container", "station container"}
STORED_FLAGS = {None, "Hangar", "Unlocked", "Locked", "CorpDeliveries"}


def industry_category(item):
    group = item.group if item else None
    if not group:
        return None
    name = group.name.casefold()
    category = group.category.name.casefold() if group.category else ""
    if group.group_id == 18 or name == "mineral":
        return "Minerals"
    if group.category_id in {42, 43} or category in {"planetary resources", "planetary commodities"}:
        return "PI"
    if group.category_id == 4 or category == "material":
        return "Industrial materials"
    if group.category_id == 25 or category == "asteroid":
        return "Ore and ice"
    if name in {"ice product", "fuel block", "construction components", "advanced capital construction components",
                "capital construction components", "hybrid tech components", "tools", "salvaged materials",
                "ancient salvage", "compressed gas", "harvestable cloud", "moon materials", "intermediate materials",
                "composite", "biochemical material", "biochemical resources"}:
        return "Industrial materials"
    return None


def is_container(asset):
    group = asset.item_type.group if asset.item_type else None
    return bool(group and (group.group_id in CONTAINER_GROUPS or group.name.casefold() in CONTAINER_NAMES))


def is_blueprint(item):
    return bool(item and item.group and (item.group.category_id == 9 or "reaction formula" in item.group.name.casefold()))


class StorageIndex:
    def __init__(self, db, owner_ids):
        self.assets = {a.id: a for a in db.scalars(select(Asset).where(Asset.ownership_entity_id.in_(owner_ids)).options(
            selectinload(Asset.item_type).selectinload(EveType.group).selectinload(EveGroup.category),
            selectinload(Asset.location)))}
        self.owners = {o.id: o for o in db.scalars(select(OwnershipEntity).where(OwnershipEntity.id.in_(owner_ids)).options(
            selectinload(OwnershipEntity.character), selectinload(OwnershipEntity.corporation)))}
        corp_ids={owner.corporation_id for owner in self.owners.values() if owner.corporation_id}
        self.hangar_names={(d.corporation_id,f"CorpSAG{d.division}"):d.name for d in db.scalars(
            select(CorporationDivision).where(CorporationDivision.corporation_id.in_(corp_ids),CorporationDivision.division_type=="hangar"))}
        self._resolved = {}

    def office_hangar(self, asset):
        """ESI corporation offices are storage roots, not cargo containers."""
        office = self.assets.get(asset.parent_asset_id)
        owner = self.owners.get(asset.ownership_entity_id)
        if not (office and owner and owner.owner_kind.value == "corporation"
                and office.ownership_entity_id == asset.ownership_entity_id
                and office.type_id == 27 and office.item_type and office.item_type.group_id == 16
                and office.location_flag == "OfficeFolder" and office.parent_asset_id is None
                and re.fullmatch(r"CorpSAG[1-7]", asset.location_flag or "")
                and office.location and office.location.location_kind.value in {"station", "structure"}):
            return None
        return office.location, asset.location_flag

    def placement(self, asset):
        if asset.id in self._resolved:
            return self._resolved[asset.id]
        current = asset
        seen = set()
        result = None
        while current and current.id not in seen and len(seen) < 64:
            seen.add(current.id)
            flag = current.location_flag
            if flag not in STORED_FLAGS and not re.fullmatch(r"CorpSAG[1-7]", flag or ""):
                break
            if current.parent_asset_id is not None:
                office_place = self.office_hangar(current)
                if office_place:
                    result = office_place
                    break
                parent = self.assets.get(current.parent_asset_id)
                if not parent or parent.ownership_entity_id != asset.ownership_entity_id or not is_container(parent):
                    break
                current = parent
                continue
            location = current.location
            visited = set()
            while location and location.id not in visited and len(visited) < 32:
                visited.add(location.id)
                if location.location_kind.value in {"station", "structure"}:
                    result = (location, current.location_flag or "Hangar")
                    break
                # Unresolved item locations cannot masquerade as station storage.
                if location.location_kind.value != "container":
                    break
                location = location.parent
            break
        self._resolved[asset.id] = result
        return result

    def key(self, asset, container=False):
        place = self.placement(asset)
        if not place:
            return None
        loc, flag = place
        prefix = f"{asset.ownership_entity_id}:{loc.id}:"
        return "c:" + prefix + str(asset.id) if container else "h:" + prefix + flag

    def owner_label(self, oid):
        owner = self.owners[oid]
        return owner.character.name if owner.character else owner.corporation.name if owner.corporation else owner.display_name

    def options(self, owner_ids):
        options = {}
        for asset in self.assets.values():
            if asset.ownership_entity_id not in owner_ids:
                continue
            place = self.placement(asset)
            if not place:
                continue
            location, flag = place
            owner = self.owner_label(asset.ownership_entity_id)
            if asset.parent_asset_id is None or self.office_hangar(asset):
                key = self.key(asset)
                corp_id=self.owners[asset.ownership_entity_id].corporation_id
                name=self.hangar_names.get((corp_id,flag))
                options[key] = {"key": key, "kind": "hangar", "owner": owner, "location": location.name, "name": f"{name} ({flag})" if name else flag}
            if is_container(asset):
                key = self.key(asset, True)
                options[key] = {"key": key, "kind": "container", "owner": owner, "location": location.name,
                                "name": f"{asset.item_type.name} · item {asset.eve_item_id or asset.id}"}
        return sorted(options.values(), key=lambda o: (o["owner"].casefold(), o["location"], o["kind"], o["name"]))

    def selected(self, asset, keys):
        if not self.placement(asset) or is_container(asset):
            return False
        if asset.parent_asset_id and not self.office_hangar(asset):
            return self.key(self.assets[asset.parent_asset_id], True) in keys
        return self.key(asset) in keys

    def inventory_location(self, asset):
        current=asset
        seen=set()
        while current and current.id not in seen and len(seen)<64:
            seen.add(current.id)
            if current.location:
                return current.location.name
            parent=self.assets.get(current.parent_asset_id)
            if parent and parent.ownership_entity_id != asset.ownership_entity_id:
                break
            current=parent
        return "Unresolved location"

    def public_location(self, asset):
        place = self.placement(asset)
        if not place:
            return "Undisclosed location"
        location, _ = place
        # Player-assigned Upwell/container names can themselves contain pilot names.
        return location.name if location.location_kind.value == "station" else "Upwell structure"
