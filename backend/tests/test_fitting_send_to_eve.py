from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.fittings import esi_fitting_payload, owned_fitting_send_token, send_fitting_to_eve
from app.models import Base, CharacterFitting, CharacterFittingItem, EsiToken, EveCharacter, EveType, User


class TestFittingSendToEve:
    def setup_method(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = User(email="pilot@example.test", display_name="Pilot", role="member")
        self.other_user = User(email="other@example.test", display_name="Other", role="member")
        self.db.add_all([self.user, self.other_user])
        self.db.flush()
        self.character = EveCharacter(character_id=91_000_001, name="Linked Pilot", owner_user_id=self.user.id)
        self.other_character = EveCharacter(character_id=91_000_002, name="Other Pilot", owner_user_id=self.other_user.id)
        self.db.add_all([self.character, self.other_character])
        self.db.flush()
        self.ship = EveType(type_id=620, name="Osprey", published=True)
        self.module = EveType(type_id=2293, name="T2 Module", published=True)
        self.charge = EveType(type_id=2301, name="T2 Charge", published=True)
        self.drone = EveType(type_id=2454, name="Drone", published=True)
        self.db.add_all([self.ship, self.module, self.charge, self.drone])
        self.db.flush()
        self.fitting = CharacterFitting(
            character_id=self.character.id,
            name="  Test Fit  ",
            description="Sent by test",
            ship_type_id=self.ship.type_id,
            is_shared=True,
            is_draft=True,
        )
        self.db.add(self.fitting)
        self.db.flush()
        self.db.add_all(
            [
                CharacterFittingItem(fitting_id=self.fitting.id, type_id=self.module.type_id, charge_type_id=self.charge.type_id, flag="HiSlot0", quantity=1),
                CharacterFittingItem(fitting_id=self.fitting.id, type_id=self.drone.type_id, flag="DroneBay", quantity=5),
            ]
        )
        self.token = EsiToken(
            user_id=self.user.id,
            character_id=self.character.id,
            scopes="esi-fittings.read_fittings.v1 esi-fittings.write_fittings.v1",
            encrypted_refresh_token="encrypted",
        )
        self.other_token = EsiToken(
            user_id=self.other_user.id,
            character_id=self.other_character.id,
            scopes="esi-fittings.write_fittings.v1",
            encrypted_refresh_token="encrypted",
        )
        self.db.add_all([self.token, self.other_token])
        self.db.commit()

    def teardown_method(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_payload_preserves_slots_bays_and_selected_charge(self) -> None:
        payload = esi_fitting_payload(self.fitting)

        assert payload["name"] == "Test Fit"
        assert payload["ship_type_id"] == self.ship.type_id
        assert payload["items"] == [
            {"flag": "Cargo", "quantity": 1, "type_id": self.charge.type_id},
            {"flag": "DroneBay", "quantity": 5, "type_id": self.drone.type_id},
            {"flag": "HiSlot0", "quantity": 1, "type_id": self.module.type_id},
        ]

    def test_send_token_must_belong_to_current_account(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            owned_fitting_send_token(self.db, self.user, self.other_token.id)

        assert exc_info.value.status_code == 403

    def test_write_scope_is_required(self) -> None:
        self.token.scopes = "esi-fittings.read_fittings.v1"
        self.db.commit()

        with pytest.raises(HTTPException) as exc_info:
            owned_fitting_send_token(self.db, self.user, self.token.id)

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["code"] == "fitting_write_scope_required"

    def test_endpoint_posts_to_selected_character(self, monkeypatch) -> None:
        sent: dict[str, object] = {}

        async def fake_refresh(token: EsiToken) -> str:
            assert token.id == self.token.id
            return "access-token"

        async def fake_post(client_self, path: str, payload: dict) -> dict:
            sent.update({"access_token": client_self.access_token, "path": path, "payload": payload})
            return {"fitting_id": 9876}

        monkeypatch.setattr("app.api.fittings.refresh_access_token", fake_refresh)
        monkeypatch.setattr("app.api.fittings.EsiClient.post", fake_post)

        result = asyncio.run(
            send_fitting_to_eve(
                self.fitting.id,
                {"token_id": self.token.id},
                current_user=self.user,
                db=self.db,
            )
        )

        assert result["fitting_id"] == 9876
        assert result["character_name"] == self.character.name
        assert sent["access_token"] == "access-token"
        assert sent["path"] == f"/characters/{self.character.character_id}/fittings/"
        assert sent["payload"] == esi_fitting_payload(self.fitting)
