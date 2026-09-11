import asyncio
from types import SimpleNamespace as NS

import pytest
from fastapi import HTTPException

from app.services import pi_character_scope
from app.services.pi_character_scope import character_scopes, scoped_payload, verified_corporations


@pytest.fixture
def characters():
    return [NS(id=1, owner_user_id=7, corporation_id=10),
            NS(id=2, owner_user_id=7, corporation_id=20),
            NS(id=3, owner_user_id=8, corporation_id=10),
            NS(id=4, owner_user_id=9, corporation_id=30),
            NS(id=5, owner_user_id=7, corporation_id=None),
            NS(id=6, owner_user_id=8, corporation_id=None)]


@pytest.mark.parametrize("rank,expected", [(1, ["mine"]), (2, ["mine"]),
    (3, ["mine", "corp"]), (4, ["mine", "corp", "all"]), (5, ["mine", "corp", "all"])])
def test_groups_respect_role_and_linked_corporations(characters, rank, expected):
    groups = character_scopes(characters, 7, rank, {10})
    assert [group["id"] for group in groups] == expected
    assert groups[0]["character_ids"] == [1, 2, 5]
    if rank >= 3:
        assert groups[1]["character_ids"] == [1, 3]
    if rank >= 4:
        assert groups[2]["character_ids"] == [1, 2, 3, 4, 5, 6]


def test_no_linked_corporation_never_matches_unknown_pilots(characters):
    assert character_scopes(characters, 999, 3)[1]["character_ids"] == []


def test_scoped_report_drops_other_colonies_tokens_and_totals(characters):
    payload = {"character_scopes": character_scopes(characters, 7, 3, {10}),
               "characters": [{"id": id} for id in [1, 2, 3, 5]],
               "sync_tokens": [{"character_id": id} for id in [1, 2, 3, 5]],
               "colonies": [{"character_id": id, "summary": {
                   "expired_extractors": id, "expiring_extractors": 0,
                   "starved_factories": 0, "stored_volume": id * 10}} for id in [1, 2, 3]]}
    mine = scoped_payload(payload)
    assert [row["character_id"] for row in mine["colonies"]] == [1, 2]
    assert mine["summary"]["stored_volume"] == 30
    assert [row["character_id"] for row in mine["sync_tokens"]] == [1, 2, 5]
    assert scoped_payload(payload, "corp")["summary"]["stored_volume"] == 40
    assert scoped_payload(payload, character_id=3)["summary"]["stored_volume"] == 30
    with pytest.raises(HTTPException) as denied:
        scoped_payload(payload, "all")
    assert denied.value.status_code == 403
    with pytest.raises(HTTPException) as hidden:
        scoped_payload(payload, character_id=4)
    assert hidden.value.status_code == 404
    assert len(payload["colonies"]) == 3


def test_roles_require_own_active_token_and_verified_corporation(characters, monkeypatch):
    monkeypatch.setattr(pi_character_scope, "_ROLE_CHECKS", {})
    def token(id, character_id, user_id=7, scopes=pi_character_scope.ROLE_SCOPE, revoked_at=None):
        return NS(id=id, character_id=character_id, user_id=user_id, scopes=scopes, revoked_at=revoked_at)
    tokens = [token(1, 1), token(2, 2), token(3, 3, user_id=8), token(4, 1, scopes=""), token(5, 1, revoked_at="revoked")]
    checked = []
    async def check(token, character):
        checked.append(token.id)
        return character.corporation_id == 10
    verified, failed = asyncio.run(verified_corporations(characters, tokens, 7, check))
    assert verified == {10}
    assert failed is False
    assert checked == [1, 2]
    asyncio.run(verified_corporations(characters, tokens, 7, check))
    assert checked == [1, 2]  # Brief cache avoids repeat ESI calls during page polling.
    tokens[0].revoked_at = "revoked"
    assert asyncio.run(verified_corporations(characters, tokens, 7, check))[0] == set()
    tokens[0].revoked_at = None
    characters[0].corporation_id = 30
    assert asyncio.run(verified_corporations(characters, tokens, 7, check))[0] == set()
    assert checked[-1] == 1  # A corporation change cannot reuse the former grant.


def test_role_verification_failure_does_not_grant_access(characters, monkeypatch):
    monkeypatch.setattr(pi_character_scope, "_ROLE_CHECKS", {})
    token = NS(id=1, character_id=1, user_id=7, scopes=pi_character_scope.ROLE_SCOPE, revoked_at=None)
    async def check(*args):
        raise RuntimeError("ESI unavailable")
    assert asyncio.run(verified_corporations(characters, [token], 7, check)) == (set(), True)


@pytest.mark.parametrize("roles,affiliation,expected", [(["Director"], 1010, [1, 2, 3, 5]),
    ([], 1010, [1, 2, 5]), (["Director"], 1030, [1, 2, 5])])
def test_list_api_checks_esi_roles_and_affiliation_before_listing_corp_pilots(characters, monkeypatch, roles, affiliation, expected):
    from app.api import planetary_industry as api
    monkeypatch.setattr(pi_character_scope, "_ROLE_CHECKS", {})
    for row in characters:
        row.character_id = 9000 + row.id
        row.name, row.portrait_url = f"Pilot {row.id}", None
        row.corporation = NS(corporation_id=1000 + row.corporation_id) if row.corporation_id else None
    token = NS(id=1, user_id=7, character_id=1, scopes=pi_character_scope.ROLE_SCOPE, revoked_at=None)
    queries = []
    class Db:
        def scalars(self, statement):
            queries.append(statement)
            return NS(all=lambda: [token] if len(queries) == 1 else [])
        def commit(self):
            pass
    class Client:
        def __init__(self, access):
            pass
        async def get(self, path):
            return {"roles": roles} if path.endswith("/roles/") else {"corporation_id": affiliation}
    async def refresh(token):
        return "test-token"
    monkeypatch.setattr(api, "require_planetary_view", lambda *args: None)
    monkeypatch.setattr(api, "visible_characters", lambda *args: characters)
    monkeypatch.setattr(api, "role_rank", lambda *args: 3)
    monkeypatch.setattr(api, "EsiClient", Client)
    monkeypatch.setattr(api, "refresh_access_token", refresh)
    monkeypatch.setattr(api, "sync_token_payload", lambda *args: [])
    payload = asyncio.run(api.list_planetary_industry(NS(id=7), Db()))
    assert [row["id"] for row in payload["characters"]] == expected
    assert set(queries[1].compile().params["character_id_1"]) == set(expected)
