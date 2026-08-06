from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import Response
from starlette.requests import Request

from app.api.auth import (
    REMEMBER_ME_COOKIE,
    clear_remember_me_cookie,
    get_current_user,
    login,
    set_remember_me_cookie,
)
from app.core.security import create_access_token, decode_token, hash_password


class _FakeSession:
    def __init__(self, user: object) -> None:
        self.user = user

    def get(self, _model: object, user_id: int) -> object | None:
        return self.user if user_id == self.user.id else None

    def scalar(self, _query: object) -> object:
        return self.user


class RememberMeTests(unittest.TestCase):
    def test_persistent_cookie_is_http_only_and_scoped_to_api(self) -> None:
        response = Response()
        set_remember_me_cookie(response, "remembered-token")

        cookie = response.headers["set-cookie"]
        self.assertIn(f"{REMEMBER_ME_COOKIE}=remembered-token", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("Max-Age=2592000", cookie)
        self.assertIn("Path=/api", cookie)
        self.assertIn("SameSite=lax", cookie)

    def test_login_keeps_remembered_token_out_of_response_body(self) -> None:
        user = SimpleNamespace(
            id=42,
            email="pilot@example.test",
            display_name="Test Pilot",
            role="member",
            timezone="UTC",
            created_at=None,
            deleted_at=None,
            password_hash=hash_password("correct-horse"),
        )
        response = Response()

        payload = login(
            {"email": user.email, "password": "correct-horse", "remember_me": True},
            response,
            _FakeSession(user),
        )

        self.assertTrue(payload["remembered"])
        self.assertIsNone(payload["access_token"])
        self.assertEqual(payload["token_type"], "cookie")
        self.assertIn(f"{REMEMBER_ME_COOKIE}=", response.headers["set-cookie"])

    def test_cookie_authenticates_without_an_authorization_header(self) -> None:
        token = create_access_token("42", {"remember_me": True}, expires_minutes=30 * 24 * 60)
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/api/auth/me",
                "headers": [(b"cookie", f"{REMEMBER_ME_COOKIE}={token}".encode("ascii"))],
            }
        )
        user = SimpleNamespace(id=42, deleted_at=None)

        self.assertIs(get_current_user(request, None, _FakeSession(user)), user)

    def test_remembered_token_uses_requested_lifetime(self) -> None:
        issued_at = datetime.now(timezone.utc).timestamp()
        payload = decode_token(create_access_token("7", expires_minutes=30 * 24 * 60))

        self.assertAlmostEqual(float(payload["exp"]) - issued_at, 30 * 24 * 60 * 60, delta=5)

    def test_logout_cookie_expires_immediately(self) -> None:
        response = Response()
        clear_remember_me_cookie(response)

        cookie = response.headers["set-cookie"]
        self.assertIn(f"{REMEMBER_ME_COOKIE}=", cookie)
        self.assertIn("Max-Age=0", cookie)
        self.assertIn("Path=/api", cookie)


if __name__ == "__main__":
    unittest.main()
