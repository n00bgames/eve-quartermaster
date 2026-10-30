from __future__ import annotations

import json

from sqlalchemy import select, delete
from sqlalchemy.orm import Session, object_session

from app.models import AppSetting, RecruitmentUserCapability, RoleDefinition, RoleSectionPermission, User, UserSectionPermission, UserRoleAssignment

BUILT_IN_ROLES: list[str] = ["host", "admin", "director", "fleet_commander", "officer", "member", "intel_analyst", "quartermaster", "view_only", "applicant"]
ROLE_RANK: dict[str, int] = {"applicant": -1, "quartermaster": 0, "view_only": 0, "rookie": 0, "member": 1, "intel_analyst": 1, "officer": 2, "fleet_commander": 3, "director": 4, "admin": 5, "host": 6}
ROLE_LABELS: dict[str, str] = {
    "host": "Host",
    "admin": "Admin",
    "director": "Director",
    "fleet_commander": "Fleet Commander",
    "officer": "Officer",
    "member": "Member",
    "quartermaster": "Quartermaster",
    "intel_analyst": "Intel Analyst",
    "view_only": "View Only",
    "applicant": "Applicant",
}

SECTION_DEFINITIONS: dict[str, dict[str, object]] = {
    "ship_reports": {"label": "Ship Reports", "default_roles": ["admin","director", "fleet_commander","officer","member","view_only"]},
    "inventory_reports": {"label": "Inventory Reports", "default_roles": ["admin","director","officer","member","view_only"]},
    "industry_reports": {"label": "Industry Reports", "default_roles": ["admin","director","officer","member","quartermaster","view_only"]},
    "quartermaster": {"label": "Quartermaster", "default_roles": ["quartermaster"]},
    "intel_reports": {"label": "Intel Reports", "default_roles": ["admin", "director", "officer", "intel_analyst"]},
    "local_scan": {"label": "Local Scan", "default_roles": ["admin", "director", "officer", "member", "intel_analyst", "view_only"]},
    "dscan": {"label": "D-Scan", "default_roles": ["admin", "director", "officer", "member", "intel_analyst", "view_only"]},
    "fleet_assignments": {"label": "Fleet Assignments", "default_roles": ["admin", "director", "officer", "member", "view_only"]},
    "overview": {"label": "Overview", "default_roles": ["admin", "director", "officer", "member", "view_only"]},
    "ownership": {"label": "Ownership", "default_roles": ["admin", "director", "officer"]},
    "characters": {"label": "Characters", "default_roles": ["admin", "director", "officer", "member", "view_only"]},
    "roster": {"label": "Roster", "default_roles": ["admin", "director", "officer", "member", "view_only"]},
    "navigation": {"label": "Navigation", "default_roles": list(BUILT_IN_ROLES)},
    "market": {"label": "Market", "default_roles": list(BUILT_IN_ROLES)},
    "plex": {"label": "PLEX Tracker", "default_roles": ["admin", "director", "officer", "member", "view_only"]},
    "exchange": {"label": "Corporate Exchange", "default_roles": ["admin", "director", "officer", "member", "view_only"]},
    "hypernet": {"label": "HyperNet Tracker", "default_roles": ["admin", "director", "officer", "member", "view_only"]},
    "bounty_analytics": {"label": "Bounty Analytics", "default_roles": ["admin", "director", "officer", "member"]},
    "calendar_events": {"label": "Calendar & Events", "default_roles": ["admin", "director", "officer", "member", "view_only"]},
    "notes": {"label": "Notes & Lists", "default_roles": ["admin", "director", "officer", "member", "view_only"]},
    "contracts": {"label": "Contracts", "default_roles": ["admin", "director", "officer", "member"]},
    "analytics": {"label": "Analytics", "default_roles": ["admin", "director", "fleet_commander", "officer"]},
    "skills": {"label": "Skills", "default_roles": ["admin", "director", "officer", "member"]},
    "fittings": {"label": "Fittings", "default_roles": ["admin", "director", "officer", "member"]},
    "doctrines": {"label": "Doctrine Management", "default_roles": ["admin", "director", "officer", "member", "view_only"]},
    "srp": {"label": "SRP Requests", "default_roles": ["admin", "director", "officer", "member"]},
    "killboard": {"label": "Killboard", "default_roles": ["admin", "director", "officer", "member", "view_only"]},
    "battle_reports": {"label": "Battle Reports", "default_roles": ["admin", "director", "officer", "member", "intel_analyst", "view_only"]},
    "jump_clones": {"label": "Jump Clones", "default_roles": ["admin", "director", "officer", "member"]},
    "settings": {"label": "Settings", "default_roles": ["admin", "director", "officer", "member", "view_only"]},
    "corporations": {"label": "Corporations", "default_roles": ["admin", "director", "officer"]},
    "assets": {"label": "Assets", "default_roles": ["admin", "director", "officer", "member", "view_only"]},
    "industry": {"label": "Industry", "default_roles": ["admin", "director", "officer", "member"]},
    "manufacturing": {"label": "Manufacturing", "default_roles": ["admin", "director", "officer", "member"]},
    "mining": {"label": "Mining Ledger", "default_roles": ["admin", "director", "officer", "member"]},
    "planetary_industry": {"label": "Planetary Industry", "default_roles": ["admin", "director", "officer", "member"]},
    "esi": {"label": "ESI Sync", "default_roles": ["admin", "director", "officer", "member"]},
    "profile": {"label": "Profile", "default_roles": ["admin", "director", "officer", "member", "view_only"]},
    "audit": {"label": "Audit Log", "default_roles": ["admin"]},
    "recruiting": {"label": "Recruiting", "default_roles": []},
}
ALWAYS_VISIBLE_SECTIONS = {"overview", "profile"}
DISABLED_SECTIONS_KEY = "disabled_sections"


def disabled_sections(db: Session) -> set[str]:
    row = db.get(AppSetting, DISABLED_SECTIONS_KEY)
    if row is None:
        return set()
    value = row.value
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return set()
    if not isinstance(value, list):
        return set()
    return {str(section) for section in value if str(section) in SECTION_DEFINITIONS}


def set_disabled_sections(db: Session, sections: set[str]) -> None:
    clean = sorted(section for section in sections if section in SECTION_DEFINITIONS and section not in ALWAYS_VISIBLE_SECTIONS and section != "settings")
    row = db.get(AppSetting, DISABLED_SECTIONS_KEY)
    if row is None:
        row = AppSetting(key=DISABLED_SECTIONS_KEY, value=json.dumps(clean))
        db.add(row)
    else:
        row.value = json.dumps(clean)


def section_payload() -> list[dict[str, object]]:
    return [{"key": key, **definition} for key, definition in SECTION_DEFINITIONS.items()]


def role_record(db: Session, role: str) -> RoleDefinition | None:
    if role in BUILT_IN_ROLES:
        return None
    return db.get(RoleDefinition, role)


def role_exists(db: Session, role: str) -> bool:
    return role in BUILT_IN_ROLES or role_record(db, role) is not None


def base_role_for(db: Session, role: str) -> str:
    if role in BUILT_IN_ROLES:
        return role
    record = role_record(db, role)
    if record and record.base_role in BUILT_IN_ROLES:
        return record.base_role
    return "member"


def assigned_roles(user: User, db: Session | None = None) -> list[str]:
    db = db if db is not None else object_session(user) if hasattr(user, "_sa_instance_state") else None
    names = {user.role}
    if db is not None and user.id is not None:
        names.update(db.scalars(select(UserRoleAssignment.role).where(UserRoleAssignment.user_id == user.id)))
    return sorted(names)


def assigned_base_roles(user: User, db: Session) -> set[str]:
    return {base_role_for(db, role) for role in assigned_roles(user, db)}


def assign_roles(db: Session, user: User, roles: list[str]) -> None:
    # Retain the highest role in the legacy column for callers/clients that
    # still display one role. The extra assignments are additive.
    user.role = min(roles, key=lambda role: (-ROLE_RANK.get(base_role_for(db, role), -1),
        BUILT_IN_ROLES.index(role) if role in BUILT_IN_ROLES else len(BUILT_IN_ROLES), role))
    db.flush()
    db.execute(delete(UserRoleAssignment).where(UserRoleAssignment.user_id == user.id))
    for role in sorted(set(roles) - {user.role}):
        db.add(UserRoleAssignment(user_id=user.id, role=role))
    db.flush()


def quartermaster_read_only(user: User, db: Session) -> bool:
    bases = assigned_base_roles(user, db)
    return "quartermaster" in bases and bases <= {"quartermaster", "view_only"}


def role_rank(user_or_role: User | str, db: Session | None = None) -> int:
    if isinstance(user_or_role, User):
        db = db if db is not None else object_session(user_or_role)
        names = assigned_roles(user_or_role, db)
    else:
        names = [user_or_role]
    return max((ROLE_RANK.get(base_role_for(db, role) if db is not None else role, -1) for role in names), default=-1)


def role_payload(db: Session) -> list[dict[str, object]]:
    roles: list[dict[str, object]] = [
        {
            "name": name,
            "display_name": ROLE_LABELS[name],
            "base_role": name,
            "is_system": True,
            "sort_order": index * 10,
            "rank": ROLE_RANK[name],
        }
        for index, name in enumerate(BUILT_IN_ROLES)
    ]
    custom_roles = db.scalars(select(RoleDefinition).order_by(RoleDefinition.sort_order, RoleDefinition.display_name)).all()
    roles.extend(
        {
            "name": role.name,
            "display_name": role.display_name,
            "base_role": role.base_role,
            "is_system": role.is_system,
            "sort_order": role.sort_order,
            "rank": ROLE_RANK.get(base_role_for(db, role.name), ROLE_RANK["member"]),
        }
        for role in custom_roles
    )
    return roles


def role_names(db: Session) -> list[str]:
    return [str(role["name"]) for role in role_payload(db)]


def default_section_allowed(role: str, section: str, db: Session | None = None) -> bool:
    base_role = base_role_for(db, role) if db is not None else role
    if base_role in {"host", "admin"}:
        return True
    if section in ALWAYS_VISIBLE_SECTIONS:
        return True
    definition = SECTION_DEFINITIONS.get(section)
    return bool(definition and base_role in definition["default_roles"])


def effective_permissions(user: User, db: Session) -> dict[str, bool]:
    roles = assigned_roles(user, db)
    bases = {base_role_for(db, role) for role in roles}
    elevated = bool(bases & {"host", "admin"})
    values = {section: elevated or section in ALWAYS_VISIBLE_SECTIONS for section in SECTION_DEFINITIONS}
    if not elevated:
        overrides = db.scalars(select(RoleSectionPermission).where(RoleSectionPermission.role.in_(roles))).all()
        by_role = {(row.role, row.section): row.can_view for row in overrides}
        for role in roles:
            for section in SECTION_DEFINITIONS:
                allowed = by_role.get((role, section), default_section_allowed(role, section, db))
                values[section] = values[section] or allowed
        for override in db.scalars(select(UserSectionPermission).where(UserSectionPermission.user_id == user.id)):
            if override.section in values and override.section not in ALWAYS_VISIBLE_SECTIONS:
                values[override.section] = override.can_view
    if bases == {"applicant"}:
        values = {section: section in {"recruiting", "profile"} or (section in {"navigation", "market"} and values.get(section, False)) for section in SECTION_DEFINITIONS}
    elif db.scalar(select(RecruitmentUserCapability.id).where(RecruitmentUserCapability.user_id == user.id).limit(1)):
        values["recruiting"] = True
    for section in disabled_sections(db):
        if section not in ALWAYS_VISIBLE_SECTIONS and section != "settings":
            values[section] = False
    return values


def can_view_section(user: User, section: str, db: Session) -> bool:
    return effective_permissions(user, db).get(section, False)


def can_view_at_least(user: User, minimum_role: str, db: Session | None = None) -> bool:
    return role_rank(user, db) >= ROLE_RANK[minimum_role]
