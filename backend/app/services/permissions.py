from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AppSetting, RecruitmentUserCapability, RoleDefinition, RoleSectionPermission, User, UserSectionPermission

BUILT_IN_ROLES: list[str] = ["host", "admin", "director", "officer", "member", "view_only", "applicant"]
ROLE_RANK: dict[str, int] = {"applicant": -1, "view_only": 0, "rookie": 0, "member": 1, "officer": 2, "director": 3, "admin": 4, "host": 5}
ROLE_LABELS: dict[str, str] = {
    "host": "Host",
    "admin": "Admin",
    "director": "Director",
    "officer": "Officer",
    "member": "Member",
    "view_only": "View Only",
    "applicant": "Applicant",
}

SECTION_DEFINITIONS: dict[str, dict[str, object]] = {
    "overview": {"label": "Overview", "default_roles": ["admin", "director", "officer", "member", "view_only"]},
    "ownership": {"label": "Ownership", "default_roles": ["admin", "director", "officer"]},
    "characters": {"label": "Characters", "default_roles": ["admin", "director", "officer", "member", "view_only"]},
    "roster": {"label": "Roster", "default_roles": ["admin", "director", "officer", "member", "view_only"]},
    "navigation": {"label": "Navigation", "default_roles": ["admin", "director", "officer", "member", "view_only"]},
    "market": {"label": "Market", "default_roles": ["admin", "director", "officer", "member", "view_only"]},
    "exchange": {"label": "Corporate Exchange", "default_roles": ["admin", "director", "officer", "member", "view_only"]},
    "hypernet": {"label": "HyperNet Tracker", "default_roles": ["admin", "director", "officer", "member", "view_only"]},
    "bounty_analytics": {"label": "Bounty Analytics", "default_roles": ["admin", "director", "officer", "member"]},
    "calendar_events": {"label": "Calendar & Events", "default_roles": ["admin", "director", "officer", "member", "view_only"]},
    "notes": {"label": "Notes & Lists", "default_roles": ["admin", "director", "officer", "member", "view_only"]},
    "contracts": {"label": "Contracts", "default_roles": ["admin", "director", "officer", "member"]},
    "analytics": {"label": "Analytics", "default_roles": ["admin", "director", "officer"]},
    "skills": {"label": "Skills", "default_roles": ["admin", "director", "officer", "member"]},
    "fittings": {"label": "Fittings", "default_roles": ["admin", "director", "officer", "member"]},
    "doctrines": {"label": "Doctrine Management", "default_roles": ["admin", "director", "officer", "member", "view_only"]},
    "srp": {"label": "SRP Requests", "default_roles": ["admin", "director", "officer", "member"]},
    "killboard": {"label": "Killboard", "default_roles": ["admin", "director", "officer", "member", "view_only"]},
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
    if row is None or not isinstance(row.value, list):
        return set()
    return {str(section) for section in row.value if str(section) in SECTION_DEFINITIONS}


def set_disabled_sections(db: Session, sections: set[str]) -> None:
    clean = sorted(section for section in sections if section in SECTION_DEFINITIONS and section not in ALWAYS_VISIBLE_SECTIONS and section != "settings")
    row = db.get(AppSetting, DISABLED_SECTIONS_KEY)
    if row is None:
        row = AppSetting(key=DISABLED_SECTIONS_KEY, value=clean)
        db.add(row)
    else:
        row.value = clean


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


def role_rank(user_or_role: User | str, db: Session | None = None) -> int:
    role = user_or_role.role if isinstance(user_or_role, User) else user_or_role
    if db is not None:
        role = base_role_for(db, role)
    return ROLE_RANK.get(role, -1)


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
    base_role = base_role_for(db, user.role)
    elevated = base_role in {"host", "admin"}
    if elevated:
        values = {section: True for section in SECTION_DEFINITIONS}
    else:
        values = {section: default_section_allowed(user.role, section, db) for section in SECTION_DEFINITIONS}

        role_overrides = db.scalars(select(RoleSectionPermission).where(RoleSectionPermission.role == user.role)).all()
        for override in role_overrides:
            if override.section in values and override.section not in ALWAYS_VISIBLE_SECTIONS:
                values[override.section] = override.can_view

        user_overrides = db.scalars(select(UserSectionPermission).where(UserSectionPermission.user_id == user.id)).all()
        for override in user_overrides:
            if override.section in values and override.section not in ALWAYS_VISIBLE_SECTIONS:
                values[override.section] = override.can_view

    if user.role == "applicant":
        values = {section: section in {"recruiting", "profile"} for section in SECTION_DEFINITIONS}
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
