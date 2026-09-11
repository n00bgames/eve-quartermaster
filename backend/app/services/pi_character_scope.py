"""PI character groups, intersected with existing character visibility."""
import time

from fastapi import HTTPException

from app.services.permissions import ROLE_RANK


ROLE_SCOPE = "esi-characters.read_corporation_roles.v1"
_ROLE_CHECKS = {}


async def verified_corporations(characters, tokens, viewer_id, check):
    """Verify only the viewer's own tokens; cache successful checks for 60 seconds."""
    own = {row.id: row for row in characters if row.owner_user_id == viewer_id}
    verified, failed = set(), False
    now = time.monotonic()
    for key, (expires, _) in list(_ROLE_CHECKS.items()):
        if expires <= now:
            _ROLE_CHECKS.pop(key, None)
    for token in tokens:
        character = own.get(token.character_id)
        if token.user_id != viewer_id or token.revoked_at is not None or not character or character.corporation_id is None:
            continue
        if ROLE_SCOPE not in (token.scopes or "").split() or character.corporation_id in verified:
            continue
        key = (viewer_id, token.id, character.id, character.corporation_id, token.scopes)
        cached = _ROLE_CHECKS.get(key)
        try:
            if cached and cached[0] > time.monotonic():
                authorized = cached[1]
            else:
                authorized = await check(token, character)
                _ROLE_CHECKS[key] = (time.monotonic() + 60, authorized)
        except Exception:
            failed = True
            continue
        if authorized:
            verified.add(character.corporation_id)
    return verified, failed


def character_scopes(characters, viewer_id, rank, verified_corporation_ids=()):
    mine = [row for row in characters if row.owner_user_id == viewer_id]
    corporation_ids = {row.corporation_id for row in mine if row.corporation_id is not None} & set(verified_corporation_ids)
    scopes = [{"id": "mine", "name": "My Characters Only", "character_ids": [row.id for row in mine]}]
    if rank >= ROLE_RANK["director"]:
        scopes.append({"id": "corp", "name": "My Corp Pilots", "character_ids": [row.id for row in characters if row.corporation_id in corporation_ids]})
    if rank >= ROLE_RANK["admin"]:
        scopes.append({"id": "all", "name": "All Characters", "character_ids": [row.id for row in characters]})
    return scopes


def scoped_payload(payload, scope="mine", character_id=None):
    groups = payload.get("character_scopes", [])
    selected = next((group for group in groups if group["id"] == scope), None)
    if selected is None:
        raise HTTPException(403, "PI character group is unavailable for your role")
    allowed = set(selected["character_ids"])
    if character_id is not None:
        visible = {row["id"] for row in payload["characters"]}
        if character_id not in visible:
            raise HTTPException(404, "PI character is unavailable")
        allowed = {character_id}
    colonies = [row for row in payload["colonies"] if row["character_id"] in allowed]
    return {**payload,
            "characters": [row for row in payload["characters"] if row["id"] in allowed],
            "sync_tokens": [row for row in payload["sync_tokens"] if row["character_id"] in allowed],
            "colonies": colonies,
            "summary": {"colonies": len(colonies), "characters": len({row["character_id"] for row in colonies}),
                        **{key: sum(row["summary"][key] for row in colonies) for key in
                           ("expired_extractors", "expiring_extractors", "starved_factories", "stored_volume")}}}
