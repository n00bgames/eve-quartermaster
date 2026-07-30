from __future__ import annotations

import html
from typing import Any

EXCHANGE_MAIL_SCOPE = "esi-ui.open_window.v1"


def _listing_value(listing: Any, attribute: str, default: str) -> str:
    value = str(getattr(listing, attribute, "") or "").strip()
    return value or default


def exchange_mail_subject(listing: Any) -> str:
    title = _listing_value(listing, "title", "Corporate Exchange package")
    return f"EQM purchase request: {title}"[:1000]


def exchange_mail_body(listing: Any) -> str:
    title = _listing_value(listing, "title", "Corporate Exchange package")
    seller = getattr(listing, "seller_character", None)
    seller_name = _listing_value(seller, "name", "capsuleer")
    location = _listing_value(listing, "location_text", "")
    if not location and getattr(listing, "location", None) is not None:
        location = _listing_value(listing.location, "name", "")
    if getattr(listing, "division_name", None):
        location = f"{location} - {listing.division_name}" if location else str(listing.division_name)
    safe_title = html.escape(title)
    safe_seller_name = html.escape(seller_name)
    safe_location = html.escape(location)
    handoff = f"\nHandoff location: {safe_location}" if safe_location else ""
    reference = html.escape(_listing_value(listing, "public_id", "unavailable"))
    return (
        f"Greetings {safe_seller_name},\n\n"
        f"I found your \"{safe_title}\" package on the EQM Corporate Exchange and would like to purchase it "
        "under the advertised terms.\n\n"
        "Please issue a private item-exchange contract to this character when ready."
        f"{handoff}\n"
        f"EQM listing reference: {reference}\n\n"
        "Thank you, and fly safe."
    )