from __future__ import annotations

import time
from typing import Any

import httpx
from fastapi import HTTPException
from jose import JWTError, jwt

from app.core.config import get_settings

SSO_METADATA_URL = "https://login.eveonline.com/.well-known/oauth-authorization-server"
ACCEPTED_ISSUERS = ("https://login.eveonline.com", "https://login.eveonline.com/", "login.eveonline.com")
EXPECTED_AUDIENCE = "EVE Online"
JWKS_CACHE_SECONDS = 300

_jwks: dict[str, Any] | None = None
_jwks_expires_at = 0.0


async def _load_jwks() -> dict[str, Any]:
    global _jwks, _jwks_expires_at
    if _jwks is not None and _jwks_expires_at > time.monotonic():
        return _jwks

    async with httpx.AsyncClient(timeout=15.0) as client:
        metadata_response = await client.get(SSO_METADATA_URL)
        metadata_response.raise_for_status()
        jwks_response = await client.get(metadata_response.json()["jwks_uri"])
        jwks_response.raise_for_status()

    _jwks = jwks_response.json()
    _jwks_expires_at = time.monotonic() + JWKS_CACHE_SECONDS
    return _jwks


async def validate_eve_access_token(token: str) -> dict[str, Any]:
    """Validate an EVE SSO access token before trusting its character identity."""
    try:
        header = jwt.get_unverified_header(token)
        keys = (await _load_jwks()).get("keys", [])
        key = next(
            item
            for item in keys
            if item.get("kid") == header.get("kid") and item.get("alg") == header.get("alg")
        )
        claims = jwt.decode(
            token,
            key=key,
            algorithms=[header["alg"]],
            issuer=ACCEPTED_ISSUERS,
            audience=EXPECTED_AUDIENCE,
        )
    except (JWTError, KeyError, StopIteration, httpx.HTTPError) as exc:
        raise HTTPException(status_code=400, detail="EVE SSO returned an invalid access token") from exc

    audience = claims.get("aud", [])
    audience_values = {audience} if isinstance(audience, str) else set(audience)
    if get_settings().eve_sso_client_id not in audience_values:
        raise HTTPException(status_code=400, detail="EVE SSO token was not issued for this application")
    return claims
