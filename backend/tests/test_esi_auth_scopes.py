from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from app.api.esi import CORE_AUTH_SCOPES, auth_scopes_for_group, build_auth_url


PLANET_SCOPE = "esi-planets.manage_planets.v1"
FITTING_WRITE_SCOPE = "esi-fittings.write_fittings.v1"


class EsiAuthScopeTests(unittest.TestCase):
    def test_normal_relinks_request_loyalty_without_expanding_recruitment(self) -> None:
        loyalty_scope = "esi-characters.read_loyalty.v1"
        for group in (None, "core", "contacts", "mail", "planetary", "fittings", "full"):
            with self.subTest(group=group):
                scopes = auth_scopes_for_group(group)
                self.assertIn(loyalty_scope, scopes)
                self.assertEqual(len(scopes), len(set(scopes)))
        self.assertNotIn(loyalty_scope, auth_scopes_for_group("recruitment"))

    def test_default_authorization_url_contains_loyalty_scope(self) -> None:
        settings = SimpleNamespace(eve_sso_client_id="test-client", eve_sso_client_secret="test-secret",
            token_encryption_key="test-key", eve_sso_callback_url="https://example.invalid/callback")
        with patch("app.api.esi.get_settings", return_value=settings), \
             patch("app.api.esi.create_sso_state", return_value="test-state"):
            result = build_auth_url(auth_scopes_for_group("core"), SimpleNamespace(id=1))
        scopes = parse_qs(urlparse(result["url"]).query)["scope"][0].split()
        self.assertIn("esi-characters.read_loyalty.v1", scopes)

    def test_core_authorization_includes_planetary_industry(self) -> None:
        self.assertIn(PLANET_SCOPE, CORE_AUTH_SCOPES)

    def test_planetary_authorization_group_includes_planetary_industry(self) -> None:
        scopes = auth_scopes_for_group("planetary")

        self.assertIn(PLANET_SCOPE, scopes)
        self.assertEqual(len(scopes), len(set(scopes)))

    def test_fitting_authorization_returns_with_write_scope(self) -> None:
        scopes = auth_scopes_for_group("fittings")

        self.assertIn(FITTING_WRITE_SCOPE, scopes)
        self.assertEqual(len(scopes), len(set(scopes)))


if __name__ == "__main__":
    unittest.main()
