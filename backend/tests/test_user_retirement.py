from datetime import datetime, timezone
import unittest

from app.services.user_accounts import retire_user_account
from types import SimpleNamespace


class UserRetirementTests(unittest.TestCase):
    def test_retirement_anonymizes_identity_and_disables_login(self) -> None:
        retired_at = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
        user = SimpleNamespace(
            id=42,
            email="pilot@example.com",
            display_name="Capsuleer",
            password_hash="secret-hash",
            role="admin",
            timezone="America/Chicago",
            deleted_at=None,
        )

        retire_user_account(user, retired_at)

        self.assertEqual(user.email, "deleted-user-42@invalid.local")
        self.assertEqual(user.display_name, "Deleted user 42")
        self.assertIsNone(user.password_hash)
        self.assertEqual(user.role, "member")
        self.assertEqual(user.timezone, "UTC")
        self.assertEqual(user.deleted_at, retired_at)


if __name__ == "__main__":
    unittest.main()