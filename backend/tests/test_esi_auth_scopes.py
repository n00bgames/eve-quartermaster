from __future__ import annotations

import unittest

from app.api.esi import CORE_AUTH_SCOPES, auth_scopes_for_group


PLANET_SCOPE = "esi-planets.manage_planets.v1"


class EsiAuthScopeTests(unittest.TestCase):
    def test_core_authorization_includes_planetary_industry(self) -> None:
        self.assertIn(PLANET_SCOPE, CORE_AUTH_SCOPES)

    def test_planetary_authorization_group_includes_planetary_industry(self) -> None:
        scopes = auth_scopes_for_group("planetary")

        self.assertIn(PLANET_SCOPE, scopes)
        self.assertEqual(len(scopes), len(set(scopes)))


if __name__ == "__main__":
    unittest.main()
