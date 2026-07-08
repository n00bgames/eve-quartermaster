from __future__ import annotations

import re
from typing import Any

import httpx

UEDAMA_SCOUT_CHANNEL = "uedamascout"
UEDAMA_SCOUT_URL = f"https://www.twitch.tv/{UEDAMA_SCOUT_CHANNEL}"
USER_AGENT = "EVE-Quartermaster/route-intel"


async def uedama_scout_status() -> dict[str, Any]:
    """Best-effort Twitch page probe for the public Uedama scout stream.

    Twitch's first-party live status API requires app credentials, so this uses
    a conservative page/metadata check and fails closed if Twitch changes markup.
    """

    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
            timeout=8.0,
            follow_redirects=True,
        ) as client:
            response = await client.get(UEDAMA_SCOUT_URL)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        return {
            "channel": UEDAMA_SCOUT_CHANNEL,
            "url": UEDAMA_SCOUT_URL,
            "is_live": False,
            "checked": False,
            "error": str(exc),
            "source": "twitch_page_probe",
        }

    body = response.text[:500_000]
    lower_body = body.lower()
    is_live = any(
        (
            '"isLiveBroadcast":true' in body,
            '"isLive":true' in body,
            '"type":"live"' in lower_body,
            re.search(r'"stream"\s*:\s*\{[^}]*"type"\s*:\s*"live"', body, re.IGNORECASE | re.DOTALL) is not None,
        )
    )

    return {
        "channel": UEDAMA_SCOUT_CHANNEL,
        "url": UEDAMA_SCOUT_URL,
        "is_live": is_live,
        "checked": True,
        "source": "twitch_page_probe",
    }
