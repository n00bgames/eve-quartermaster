from __future__ import annotations

import time
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from jose import jwk, jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.services.eve_sso import validate_eve_access_token
from app.services.permissions import effective_permissions
from app.services.recruiting import missing_requirements, normalize_draft_discord_username, public_settings_payload, timezone_payload, transition_status


ACKNOWLEDGEMENTS = {
    "adult": True,
    "english": True,
    "discord": True,
    "voice": True,
    "esi": True,
    "doctrine": True,
    "defense": True,
}


class RecruitingPermissionTests(unittest.TestCase):
    def test_applicant_is_isolated_to_recruiting_and_profile(self) -> None:
        db = MagicMock()
        db.get.return_value = None
        db.scalars.return_value.all.return_value = []
        user = SimpleNamespace(id=7, role="applicant")

        permissions = effective_permissions(user, db)

        self.assertTrue(permissions["recruiting"])
        self.assertTrue(permissions["profile"])
        self.assertFalse(permissions["assets"])
        self.assertFalse(permissions["audit"])

    def test_recruiter_capability_does_not_change_main_role(self) -> None:
        db = MagicMock()
        db.get.return_value = None
        db.scalars.return_value.all.return_value = []
        db.scalar.return_value = 99
        user = SimpleNamespace(id=8, role="member")

        permissions = effective_permissions(user, db)

        self.assertEqual(user.role, "member")
        self.assertTrue(permissions["recruiting"])
        self.assertFalse(permissions["audit"])


class RecruitingApplicationTests(unittest.TestCase):
    def test_incomplete_draft_accepts_blank_discord_username(self) -> None:
        self.assertIsNone(normalize_draft_discord_username(""))

    def test_draft_rejects_discord_username_with_spaces(self) -> None:
        with self.assertRaises(HTTPException):
            normalize_draft_discord_username("pilot name")
    def complete_application(self) -> SimpleNamespace:
        linked = SimpleNamespace(is_main=True, verification_status="verified")
        return SimpleNamespace(
            discord_username="pilot",
            timezone="America/Chicago",
            primary_interest="Industry",
            acknowledgements_json=ACKNOWLEDGEMENTS,
            linked_characters=[linked],
            answers_json={"looking_for": "A good group", "contribution": "Industry support"},
        )

    def test_complete_verified_application_has_no_missing_requirements(self) -> None:
        self.assertEqual(missing_requirements(self.complete_application()), [])

    def test_unverified_character_blocks_submission(self) -> None:
        application = self.complete_application()
        application.linked_characters[0].verification_status = "pending"

        self.assertIn("Verified EVE character data", missing_requirements(application))

    def test_terminal_transition_closes_and_audits_application(self) -> None:
        db = MagicMock()
        db.get.return_value = None
        actor = SimpleNamespace(id=3)
        application = SimpleNamespace(
            id=11,
            status="Final Review",
            submitted_at=None,
            withdrawn_at=None,
            closed_at=None,
        )

        transition_status(db, application, "Accepted", actor, "Approved")

        self.assertEqual(application.status, "Accepted")
        self.assertIsNotNone(application.closed_at)
        self.assertEqual(db.add.call_count, 2)

    def test_unknown_status_is_rejected(self) -> None:
        db = MagicMock()
        db.get.return_value = None
        application = SimpleNamespace(id=11, status="Submitted", submitted_at=None, withdrawn_at=None, closed_at=None)

        with self.assertRaises(HTTPException) as raised:
            transition_status(db, application, "Invented Status", SimpleNamespace(id=3))

        self.assertEqual(raised.exception.status_code, 400)


class RecruitingPublicContentTests(unittest.TestCase):
    def test_optional_subheading_is_returned_to_public_page(self) -> None:
        settings = SimpleNamespace(
            setup_complete=True,
            corporation_eve_id=1, corporation_name="Example Corp", corporation_ticker="EX",
            corporation_logo_url=None, alliance_eve_id=None, alliance_name=None,
            alliance_ticker=None, alliance_logo_url=None, ceo_character_eve_id=2,
            ceo_character_name="Example CEO", ceo_portrait_url=None, ceo_manual_override=False,
            primary_timezone="UTC", activity_window_start="18:00", activity_window_end="23:00",
            public_headline="Example headline", public_subheading="Example subheading",
            public_summary="Example summary", public_body="## Who We Are\nExample body",
            offers_json=[], expectations_json=[], priorities_json=[], privacy_notice="Private",
            required_scopes_json=["publicData"],
        )

        payload = public_settings_payload(settings)

        self.assertEqual(payload["public_subheading"], "Example subheading")

    def test_timezone_offset_is_daylight_saving_aware(self) -> None:
        winter = timezone_payload("America/Chicago", datetime(2026, 1, 15, 12, tzinfo=timezone.utc))
        summer = timezone_payload("America/Chicago", datetime(2026, 7, 15, 12, tzinfo=timezone.utc))

        self.assertEqual(winter["utc_offset"], "UTC-06:00")
        self.assertEqual(summer["utc_offset"], "UTC-05:00")


class EveSsoValidationTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.private_pem = private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        public_pem = private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        cls.public_jwk = jwk.construct(public_pem, "RS256").to_dict()
        cls.public_jwk.update({"kid": "test-key", "alg": "RS256", "use": "sig"})

    def token(self, *, kid: str = "test-key", audience: list[str] | None = None, issuer: str = "https://login.eveonline.com/") -> str:
        claims = {
            "iss": issuer,
            "aud": audience or ["EVE Online", "test-client"],
            "sub": "CHARACTER:EVE:90000001",
            "exp": int(time.time()) + 300,
        }
        return jwt.encode(claims, self.private_pem, algorithm="RS256", headers={"kid": kid})

    async def test_valid_token_identity_is_accepted(self) -> None:
        with patch("app.services.eve_sso._load_jwks", AsyncMock(return_value={"keys": [self.public_jwk]})), patch(
            "app.services.eve_sso.get_settings", return_value=SimpleNamespace(eve_sso_client_id="test-client")
        ):
            claims = await validate_eve_access_token(self.token())

        self.assertEqual(claims["sub"], "CHARACTER:EVE:90000001")

    async def test_current_metadata_issuer_without_trailing_slash_is_accepted(self) -> None:
        with patch("app.services.eve_sso._load_jwks", AsyncMock(return_value={"keys": [self.public_jwk]})), patch(
            "app.services.eve_sso.get_settings", return_value=SimpleNamespace(eve_sso_client_id="test-client")
        ):
            claims = await validate_eve_access_token(self.token(issuer="https://login.eveonline.com"))

        self.assertEqual(claims["sub"], "CHARACTER:EVE:90000001")

    async def test_wrong_signing_key_is_rejected(self) -> None:
        with patch("app.services.eve_sso._load_jwks", AsyncMock(return_value={"keys": [self.public_jwk]})), patch(
            "app.services.eve_sso.get_settings", return_value=SimpleNamespace(eve_sso_client_id="test-client")
        ):
            with self.assertRaises(HTTPException) as raised:
                await validate_eve_access_token(self.token(kid="unknown"))

        self.assertEqual(raised.exception.status_code, 400)

    async def test_token_for_another_client_is_rejected(self) -> None:
        with patch("app.services.eve_sso._load_jwks", AsyncMock(return_value={"keys": [self.public_jwk]})), patch(
            "app.services.eve_sso.get_settings", return_value=SimpleNamespace(eve_sso_client_id="test-client")
        ):
            with self.assertRaises(HTTPException) as raised:
                await validate_eve_access_token(self.token(audience=["EVE Online", "other-client"]))

        self.assertEqual(raised.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()