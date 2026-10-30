"""Shared hull classification for reports and private inventory analytics."""
from sqlalchemy import and_, exists, func, select
from app.models import Asset, EveGroup, EveType, EveTypeDogmaAttribute, EveDogmaAttribute

CAPSULE_GROUP = 29
CAPITAL_NAMES = frozenset({'carrier','supercarrier','titan','dreadnought','lancer dreadnought',
    'command carrier','force auxiliary','capital industrial ship','freighter','jump freighter'})
CAPITAL_GROUPS = {30, 485, 513, 547, 659, 883, 902, 1538}


def capsule_class(group_id=None, name=None):
    return group_id == CAPSULE_GROUP or (name or '').casefold() in {'capsule','capsules'}


def capital_group_ids(db):
    # Capital rigs cover XL/XXL hulls, including new capital classes in the SDE.
    rigged = exists(select(EveType.type_id).join(EveTypeDogmaAttribute, EveTypeDogmaAttribute.type_id==EveType.type_id)
        .join(EveDogmaAttribute, EveDogmaAttribute.attribute_id==EveTypeDogmaAttribute.attribute_id)
        .where(EveType.group_id==EveGroup.group_id, EveDogmaAttribute.name=='rigSize', EveTypeDogmaAttribute.value>=4))
    return set(db.scalars(select(EveGroup.group_id).where(EveGroup.category_id==6,
        (EveGroup.group_id.in_(CAPITAL_GROUPS)) | (func.lower(EveGroup.name).in_(CAPITAL_NAMES)) | rigged)))


def hull_predicate():
    return and_(EveGroup.category_id==6, EveGroup.group_id!=CAPSULE_GROUP,
        func.lower(EveGroup.name).notin_({'capsule','capsules'}), Asset.quantity>0)


def ship_classes(db):
    capitals = capital_group_ids(db)
    groups = db.scalars(select(EveGroup).where(EveGroup.category_id==6,EveGroup.published.is_(True)).order_by(EveGroup.name))
    return [{'id':g.group_id,'name':g.name,'subcaps_excluded':g.group_id in capitals or g.name.casefold() in {'shuttle','shuttles'}}
        for g in groups if not capsule_class(g.group_id,g.name)]
