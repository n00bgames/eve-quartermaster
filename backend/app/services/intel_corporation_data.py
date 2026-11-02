"""Public corporation field allow-list; no private ESI data or raw HTML."""
from app.services.intel_sources import plain

FIELDS = {"alliance_id", "ceo_id", "creator_id", "date_founded", "description", "faction_id", "home_station_id",
          "member_count", "name", "shares", "tax_rate", "ticker", "url", "war_eligible", "history", "source_errors"}


def public_profile(data):
    result = {key: value for key, value in data.items() if key in FIELDS}
    for key, limit in (("name", 255), ("ticker", 20), ("description", 4000), ("url", 2000)):
        if key in result:
            result[key] = plain(result[key], limit)
    if "shares" in result:
        result["shares"] = str(result["shares"])  # Preserve int64 shares in JavaScript.
    return result
