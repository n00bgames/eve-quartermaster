from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt

try:
    from passlib.context import CryptContext
except ImportError:
    CryptContext = None

from app.core.config import get_settings

JWT_ALGORITHM = "HS256"
PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 390000
legacy_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto") if CryptContext else None


def generate_key() -> str:
    return Fernet.generate_key().decode("utf-8")


def validate_key(key: str) -> None:
    Fernet(key.encode("utf-8"))


def encrypt_secret(value: str, key: str) -> str:
    validate_key(key)
    return Fernet(key.encode("utf-8")).encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str, key: str) -> str:
    try:
        validate_key(key)
        return Fernet(key.encode("utf-8")).decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt stored secret with the configured key") from exc


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    encoded_salt = base64.urlsafe_b64encode(salt).decode("ascii")
    encoded_digest = base64.urlsafe_b64encode(digest).decode("ascii")
    return f"{PASSWORD_ALGORITHM}${PASSWORD_ITERATIONS}${encoded_salt}${encoded_digest}"


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    if password_hash.startswith(f"{PASSWORD_ALGORITHM}$"):
        try:
            algorithm, iterations, encoded_salt, encoded_digest = password_hash.split("$", 3)
            if algorithm != PASSWORD_ALGORITHM:
                return False
            salt = base64.urlsafe_b64decode(encoded_salt.encode("ascii"))
            expected = base64.urlsafe_b64decode(encoded_digest.encode("ascii"))
            actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        except (ValueError, TypeError):
            return False
        return hmac.compare_digest(actual, expected)
    if legacy_pwd_context is None:
        return False
    try:
        return legacy_pwd_context.verify(password, password_hash)
    except Exception:
        return False


def create_access_token(
    subject: str,
    extra: dict[str, Any] | None = None,
    *,
    expires_minutes: int | None = None,
) -> str:
    settings = get_settings()
    lifetime_minutes = settings.access_token_minutes if expires_minutes is None else expires_minutes
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=lifetime_minutes)
    payload: dict[str, Any] = {"sub": subject, "exp": expires_at}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.auth_secret_key, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.auth_secret_key, algorithms=[JWT_ALGORITHM])
    except JWTError as exc:
        raise ValueError("Invalid authentication token") from exc


def create_sso_state(user_id: int, mode: str = "core") -> str:
    return create_access_token(str(user_id), {"kind": "eve_sso", "mode": mode})


def decode_sso_state_payload(state: str | None) -> dict[str, Any] | None:
    if not state:
        return None
    try:
        payload = decode_token(state)
    except ValueError:
        return None
    if payload.get("kind") != "eve_sso":
        return None
    return payload


def decode_sso_state(state: str | None) -> int | None:
    payload = decode_sso_state_payload(state)
    if payload is None:
        return None
    try:
        return int(payload.get("sub"))
    except (TypeError, ValueError):
        return None
