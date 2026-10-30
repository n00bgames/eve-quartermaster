"""Role/section based ESI consent and collection policy for the token's owner.

An observer's ability to view organization-wide data never enrolls that observer's
own characters into private collection. This also applies to previously broad tokens.
"""
from sqlalchemy.orm import object_session
from app.models import User
from app.services.permissions import base_role_for, effective_permissions, assigned_base_roles

UTILITY_ROLES = {"quartermaster", "intel_analyst", "fleet_commander"}
UTILITY_SCOPES = {"publicData", "esi-ui.write_waypoint.v1", "esi-universe.read_structures.v1", "esi-search.search_structures.v1"}
SCOPE_SECTIONS = {
    "esi-location.read_location.v1": {"characters"},
    "esi-location.read_ship_type.v1": {"characters"},
    "esi-universe.read_structures.v1": {"navigation", "assets", "corporations"},
    "esi-search.search_structures.v1": {"navigation", "assets", "corporations"},
    "esi-ui.write_waypoint.v1": {"navigation", "market"},
    "esi-ui.open_window.v1": {"market", "exchange"},
    "esi-assets.read_assets.v1": {"assets"},
    "esi-assets.read_corporation_assets.v1": {"corporations", "assets"},
    "esi-characters.read_blueprints.v1": {"industry", "research_projects"},
    "esi-corporations.read_blueprints.v1": {"industry", "research_projects"},
    "esi-characters.read_corporation_roles.v1": {"corporations", "research_projects", "industry"},
    "esi-corporations.read_structures.v1": {"corporations", "assets"},
    "esi-corporations.read_corporation_membership.v1": {"corporations"},
    "esi-corporations.track_members.v1": {"corporations"},
    "esi-corporations.read_divisions.v1": {"corporations"},
    "esi-wallet.read_character_wallet.v1": {"bounty_analytics", "analytics"},
    "esi-wallet.read_corporation_wallets.v1": {"corporations", "analytics"},
    "esi-characters.read_loyalty.v1": {"characters"},
    "esi-industry.read_character_jobs.v1": {"research_projects", "manufacturing"},
    "esi-industry.read_corporation_jobs.v1": {"research_projects", "manufacturing"},
    "esi-industry.read_character_mining.v1": {"mining"},
    "esi-contracts.read_character_contracts.v1": {"contracts"},
    "esi-contracts.read_corporation_contracts.v1": {"contracts"},
    "esi-skills.read_skills.v1": {"skills", "fittings"},
    "esi-skills.read_skillqueue.v1": {"skills"},
    "esi-characters.read_standings.v1": {"characters"},
    "esi-fittings.read_fittings.v1": {"fittings"},
    "esi-fittings.write_fittings.v1": {"fittings"},
    "esi-clones.read_clones.v1": {"jump_clones"},
    "esi-clones.read_implants.v1": {"jump_clones"},
    "esi-planets.manage_planets.v1": {"planetary_industry"},
    "esi-killmails.read_killmails.v1": {"killboard", "battle_reports"},
    "esi-characters.read_contacts.v1": {"characters"},
    "esi-characters.write_contacts.v1": {"characters"},
    "esi-corporations.read_contacts.v1": {"corporations"},
    "esi-alliances.read_contacts.v1": {"corporations"},
    "esi-mail.read_mail.v1": {"profile"},
    "esi-mail.send_mail.v1": {"profile"},
    "esi-mail.organize_mail.v1": {"profile"},
}


def is_utility_user(db, user):
    if user is None:
        return True
    bases = assigned_base_roles(user, db)
    if bases <= UTILITY_ROLES:
        return True
    if bases == {"applicant"}:
        return False  # Recruiting requires its own explicit consent flow.
    permissions = effective_permissions(user, db)
    collection_sections = {"characters", "assets", "skills", "industry", "manufacturing", "research_projects",
                           "planetary_industry", "corporations", "mining", "contracts", "jump_clones", "fittings", "killboard"}
    return not any(permissions.get(section) for section in collection_sections)


def allowed_scopes(db, user):
    if user is None or user.deleted_at is not None:
        return set()
    permissions = effective_permissions(user, db)
    if is_utility_user(db, user):
        return {"publicData"} | ({"esi-ui.write_waypoint.v1", "esi-universe.read_structures.v1", "esi-search.search_structures.v1"} if permissions.get("navigation") else set())
    allowed = {"publicData"} | {scope for scope, sections in SCOPE_SECTIONS.items() if any(permissions.get(s) for s in sections)}
    # Recruiting consent is a separate, explicit applicant workflow.
    if base_role_for(db, user.role) == "applicant":
        allowed.add("esi-skills.read_skills.v1")
    return allowed


def effective_token_scopes(token, db=None):
    granted = set((token.scopes or "").split())
    db = db if db is not None else object_session(token) if hasattr(token, "_sa_instance_state") else None
    if db is None:
        return granted  # Non-persisted scope utility; live tokens are loaded with a session.
    return granted & allowed_scopes(db, db.get(User, token.user_id, populate_existing=True))


def private_collection_enabled(db, user):
    return bool(allowed_scopes(db, user) - UTILITY_SCOPES)


def requested_scopes(db, user, requested, group):
    allowed = allowed_scopes(db, user)
    if is_utility_user(db, user):
        # Utility registration asks for identity only unless the user deliberately
        # chooses a navigation integration. Never inherit the large core/full bundle.
        if group in {"waypoint", "destination"}:
            return [s for s in ("publicData", "esi-ui.write_waypoint.v1") if s in allowed]
        if group in {"structures", "navigation"}:
            return [s for s in ("publicData", "esi-universe.read_structures.v1", "esi-search.search_structures.v1") if s in allowed]
        return ["publicData"]
    if group in {"waypoint", "destination"}:
        requested = ["publicData", "esi-ui.write_waypoint.v1"]
    return [s for s in requested if s in allowed]
