"""Dataset-scoped oversight, without granting general character/asset access."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from app.models import EsiToken, EveCharacter, User
from app.services.esi_scope_policy import private_collection_enabled, effective_token_scopes

CHARACTER_SCOPES = {
    "blueprints": "esi-characters.read_blueprints.v1",
    "jobs": "esi-industry.read_character_jobs.v1",
    "planets": "esi-planets.manage_planets.v1",
}
CORPORATION_SCOPES = {
    "blueprints": "esi-corporations.read_blueprints.v1",
    "jobs": "esi-industry.read_corporation_jobs.v1",
}
_GRANTS: dict[tuple, tuple[float, frozenset[str]]] = {}


def authenticated_rows(db: Session):
    # Current owner and live token must agree; historical tokens do not enroll
    # a transferred/deleted/opted-out character in organization-wide oversight.
    rows = db.execute(select(EsiToken, EveCharacter).join(
        EveCharacter, EveCharacter.id == EsiToken.character_id
    ).join(User, User.id == EveCharacter.owner_user_id).where(
        EsiToken.revoked_at.is_(None), EsiToken.user_id == EveCharacter.owner_user_id,
        User.deleted_at.is_(None), EveCharacter.sync_opt_out.is_(False),
    ).options(selectinload(EveCharacter.corporation)).order_by(EsiToken.id.desc())).all()
    return [(token, character) for token, character in rows if private_collection_enabled(db, db.get(User, token.user_id))]


async def verify_corporation_access(token: EsiToken, character: EveCharacter) -> set[str]:
    """Probe ESI itself so actual corporate roles, not just OAuth scopes, decide.

    Only authentication credentials are refreshed; no inventory or job data is
    imported. A denied/unavailable feed is excluded, rather than showing stale
    corporate records on the strength of a scope string.
    """
    from app.api.esi import refresh_access_token
    from app.services.esi_client import EsiClient

    corporation = character.corporation
    if corporation is None:
        return set()
    client = EsiClient(await refresh_access_token(token))
    try:
        profile = await client.get(f"/characters/{character.character_id}/")
        if profile.get("corporation_id") != corporation.corporation_id:
            return set()
        grants = set()
        scopes = effective_token_scopes(token)
        for dataset, scope in CORPORATION_SCOPES.items():
            if scope not in scopes:
                continue
            suffix = "blueprints" if dataset == "blueprints" else "industry/jobs"
            try:
                result = await client.get(f"/corporations/{corporation.corporation_id}/{suffix}/", params={"page": 1})
                if isinstance(result, list):
                    grants.add(dataset)
            except Exception:
                continue
        return grants
    finally:
        await client.close()


@dataclass
class OversightScope:
    characters: dict[str, set[int]] = field(default_factory=lambda: {key: set() for key in CHARACTER_SCOPES})
    corporations: dict[str, set[int]] = field(default_factory=lambda: {key: set() for key in CORPORATION_SCOPES})
    warnings: list[str] = field(default_factory=list)


async def oversight_scope(db: Session) -> OversightScope:
    result = OversightScope()
    now = time.monotonic()
    for key, (until, _) in list(_GRANTS.items()):
        if until <= now:
            _GRANTS.pop(key, None)
    for token, character in authenticated_rows(db):
        scopes = effective_token_scopes(token)
        for dataset, scope in CHARACTER_SCOPES.items():
            if scope in scopes:
                result.characters[dataset].add(character.id)
        if character.corporation_id is None or not any(scope in scopes for scope in CORPORATION_SCOPES.values()):
            continue
        requested = [dataset for dataset, scope in CORPORATION_SCOPES.items() if scope in scopes]
        if all(character.corporation_id in result.corporations[key] for key in requested):
            continue
        key = (token.id, token.user_id, character.id, character.corporation_id, tuple(sorted(scopes)))
        cached = _GRANTS.get(key)
        try:
            if cached and cached[0] > now:
                grants = cached[1]
            else:
                grants = frozenset(await verify_corporation_access(token, character))
                # Persist only SSO rotation/expiry metadata from the verifier.
                db.commit()
                if grants:
                    _GRANTS[key] = (time.monotonic() + 60, grants)
            for dataset in grants:
                if dataset in requested:
                    result.corporations[dataset].add(character.corporation_id)
            if any(scope in scopes and dataset not in grants for dataset, scope in CORPORATION_SCOPES.items()):
                result.warnings.append(f"Some corporate access could not be verified for {character.name}; unavailable feeds are excluded.")
        except Exception:
            db.rollback()
            result.warnings.append(f"Corporate access could not be verified for {character.name}; its unverified corporate feeds are excluded.")
    return result
