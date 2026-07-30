from __future__ import annotations

import unittest
import urllib.parse
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.api.corporate_exchange import (
    appraisal_manifest,
    appraisal_payload,
    clean_choice,
    listing_location,
    market_appraisal_payload,
    parse_datetime,
)
from app.api.corporate_exchange_bids import clean_external_identity, public_exchange_mail_auth_url
from app.api.esi import auth_callback
from app.services.exchange_bids import auction_payload, next_bid_floor, validate_bid
from app.services.exchange_mail import EXCHANGE_MAIL_SCOPE, exchange_mail_body, exchange_mail_subject
from app.services.exchange_listing_updates import apply_listing_edits
from app.core.security import create_access_token, decode_sso_state_payload


def bid(amount: str, *, status: str = "pending", bidder: str = "Bidder") -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        bidder_user=SimpleNamespace(display_name=bidder),
        bidder_user_id=8,
        bidder_name=None,
        bidder_contact=None,
        quantity=1,
        amount=Decimal(amount),
        message=None,
        status=status,
        expires_at=None,
        created_at=datetime.now(timezone.utc),
    )


def auction(*, visibility: str = "public", bids: list[SimpleNamespace] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        listing_type="auction",
        status="active",
        quantity_available=1,
        sell_as_complete_lot=False,
        minimum_bid=Decimal("100.00"),
        reserve_price=Decimal("150.00"),
        bid_visibility=visibility,
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        bids=bids or [],
    )


class CorporateExchangeTests(unittest.TestCase):
    def test_exchange_mail_template_targets_the_seller_and_package(self) -> None:
        listing = SimpleNamespace(
            public_id="PACKAGE42",
            title="Capital Components Bundle",
            seller_character=SimpleNamespace(name="Seller Prime"),
            location_text="Amarr VIII (Oris) - Emperor Family Academy",
            location=None,
            division_name="Contracts",
        )
        self.assertEqual(EXCHANGE_MAIL_SCOPE, "esi-ui.open_window.v1")
        self.assertEqual(exchange_mail_subject(listing), "EQM purchase request: Capital Components Bundle")
        body = exchange_mail_body(listing)
        self.assertIn("Greetings Seller Prime", body)
        self.assertIn("Capital Components Bundle", body)
        self.assertIn("Please issue a private item-exchange contract to this character", body)
        self.assertIn("Amarr VIII (Oris) - Emperor Family Academy - Contracts", body)
        self.assertIn("PACKAGE42", body)

    def test_exchange_mail_body_escapes_listing_markup(self) -> None:
        listing = SimpleNamespace(
            public_id="SAFE42",
            title="<b>Not markup</b>",
            seller_character=SimpleNamespace(name="Seller <Prime>"),
            location_text="Jita <Trade Hub>",
            location=None,
            division_name=None,
        )
        body = exchange_mail_body(listing)
        self.assertNotIn("<b>Not markup</b>", body)
        self.assertIn("&lt;b&gt;Not markup&lt;/b&gt;", body)
        self.assertIn("Seller &lt;Prime&gt;", body)

    def test_public_exchange_mail_auth_requests_open_window_scope(self) -> None:
        listing = SimpleNamespace(public_id="PACKAGE42", seller_character=SimpleNamespace(name="Seller Prime"))
        settings = SimpleNamespace(
            eve_sso_client_id="client-id",
            eve_sso_client_secret="client-secret",
            eve_sso_callback_url="https://eqm.example/api/esi/auth/callback",
        )
        with patch("app.api.corporate_exchange_bids.load_public_listing", return_value=listing), patch(
            "app.api.corporate_exchange_bids.get_settings", return_value=settings
        ):
            result = public_exchange_mail_auth_url("PACKAGE42", db=SimpleNamespace())
        self.assertTrue(result["ready"])
        self.assertEqual(result["required_scopes"], ["esi-ui.open_window.v1"])
        query = urllib.parse.parse_qs(urllib.parse.urlparse(result["url"]).query)
        self.assertEqual(query["scope"], ["esi-ui.open_window.v1"])
        state = decode_sso_state_payload(query["state"][0])
        self.assertIsNotNone(state)
        self.assertEqual(state["mode"], "exchange_mail")
        self.assertEqual(state["listing_id"], "PACKAGE42")

    def test_listing_location_includes_authorized_division(self) -> None:
        listing = SimpleNamespace(
            location_text=None,
            location=SimpleNamespace(name="Hahda VII - Moon 1 - Factory"),
            division_name="Ships",
        )
        self.assertEqual(listing_location(listing), "Hahda VII - Moon 1 - Factory - Ships")

    def test_appraisal_payload_calculates_discount(self) -> None:
        row = SimpleNamespace(
            hub_key="amarr",
            hub_name="Amarr",
            immediate_buy_value=Decimal("850.00"),
            immediate_sell_value=Decimal("1000.00"),
            replacement_value=Decimal("1000.00"),
            source="ESI market orders",
            priced_at=None,
        )
        payload = appraisal_payload(row, 900.0)
        self.assertEqual(payload["asking_delta"], -100.0)
        self.assertEqual(payload["asking_delta_percent"], -10.0)

    def test_appraisal_manifest_prices_every_package(self) -> None:
        manifest = appraisal_manifest(
            [{"name": "Valkyrie II", "quantity": 5}, {"name": "Warrior II", "quantity": 10}],
            quantity_total=3,
        )
        self.assertEqual(manifest, "15 Valkyrie II\n30 Warrior II")

    def test_market_appraisal_payload_uses_shared_totals(self) -> None:
        payload = market_appraisal_payload(
            {
                "hubs": [{"key": "jita", "label": "Jita 4-4"}],
                "totals": {"jita": {"buy_total": 125.0, "sell_total": 150.0}},
            }
        )
        self.assertEqual(payload[0]["hub_name"], "Jita 4-4")
        self.assertEqual(payload[0]["replacement_value"], 150.0)

    def test_parse_datetime_adds_utc_to_naive_input(self) -> None:
        parsed = parse_datetime("2026-07-29T12:30:00", "expires_at")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.tzinfo, timezone.utc)

    def test_auction_listing_type_is_supported(self) -> None:
        self.assertEqual(clean_choice("auction", {"fixed", "auction"}, "fixed", "listing type"), "auction")
        with self.assertRaises(HTTPException):
            clean_choice("barter", {"fixed", "auction"}, "fixed", "listing type")

    def test_next_bid_floor_uses_highest_active_bid(self) -> None:
        listing = auction(bids=[bid("125.00"), bid("140.00")])
        self.assertEqual(next_bid_floor(listing), 140.01)
        with self.assertRaises(HTTPException):
            validate_bid(listing, amount=140.0, quantity=1)
        validate_bid(listing, amount=140.01, quantity=1)

    def test_expired_auction_rejects_new_bid(self) -> None:
        listing = auction()
        listing.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        with self.assertRaises(HTTPException):
            validate_bid(listing, amount=100.0, quantity=1)

    def test_bid_visibility_controls_public_history(self) -> None:
        public_payload = auction_payload(auction(bids=[bid("175.00")]), is_owner=False, public_view=True)
        self.assertEqual(public_payload["highest_bid"], 175.0)
        self.assertEqual(len(public_payload["bids"]), 1)
        self.assertTrue(public_payload["reserve_met"])

        private_payload = auction_payload(auction(visibility="private", bids=[bid("175.00")]), is_owner=False, public_view=True)
        self.assertIsNone(private_payload["highest_bid"])
        self.assertEqual(private_payload["bids"], [])

    def test_fixed_listing_can_restock_and_reprice_per_package(self) -> None:
        listing = SimpleNamespace(
            listing_type="fixed",
            status="active",
            quantity_total=10,
            quantity_available=7,
            asking_price=Decimal("1000.00"),
            bids=[],
            appraisals=[SimpleNamespace()],
        )
        changed = apply_listing_edits(
            SimpleNamespace(),
            listing,
            {"quantity_total": 12, "quantity_available": 9, "unit_price": 125},
        )
        self.assertEqual(listing.quantity_total, 12)
        self.assertEqual(listing.quantity_available, 9)
        self.assertEqual(listing.asking_price, 1500)
        self.assertEqual(listing.appraisals, [])
        self.assertIn("stock", changed)
        self.assertIn("price per package", changed)

    def test_listing_stock_cannot_remove_committed_packages(self) -> None:
        listing = SimpleNamespace(
            listing_type="fixed",
            status="partially_claimed",
            quantity_total=10,
            quantity_available=7,
            asking_price=Decimal("1000.00"),
            bids=[],
            appraisals=[],
        )
        with self.assertRaises(HTTPException) as context:
            apply_listing_edits(SimpleNamespace(), listing, {"quantity_total": 2, "quantity_available": 0})
        self.assertEqual(context.exception.status_code, 409)

    def test_auction_economics_lock_after_first_bid(self) -> None:
        listing = auction(bids=[bid("125.00")])
        listing.quantity_total = 1
        listing.asking_price = None
        listing.appraisals = []
        with self.assertRaises(HTTPException) as context:
            apply_listing_edits(SimpleNamespace(), listing, {"minimum_bid": 110, "reserve_price": 160})
        self.assertEqual(context.exception.status_code, 409)

    def test_restocking_completed_listing_reactivates_it(self) -> None:
        listing = SimpleNamespace(
            listing_type="fixed",
            status="completed",
            quantity_total=4,
            quantity_available=0,
            asking_price=Decimal("400.00"),
            bids=[],
            appraisals=[],
        )
        apply_listing_edits(SimpleNamespace(), listing, {"quantity_total": 6, "quantity_available": 2})
        self.assertEqual(listing.status, "active")
        self.assertEqual(listing.asking_price, 600)

    def test_external_bidder_requires_identity_and_contact(self) -> None:
        self.assertEqual(
            clean_external_identity({"bidder_name": "  Alliance Pilot  ", "bidder_contact": " Pilot Name "}),
            ("Alliance Pilot", "Pilot Name"),
        )
        with self.assertRaises(HTTPException):
            clean_external_identity({"bidder_name": "Pilot", "bidder_contact": "x"})
        with self.assertRaises(HTTPException):
            clean_external_identity({"bidder_name": "Pilot", "bidder_contact": "Contact", "website": "spam"})


class PublicExchangeMailCallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_callback_opens_prefilled_mail_in_selected_eve_client(self) -> None:
        state = create_access_token(
            "public-exchange",
            {"kind": "eve_sso", "mode": "exchange_mail", "listing_id": "PACKAGE42"},
        )
        listing = SimpleNamespace(
            public_id="PACKAGE42",
            visibility="public",
            status="active",
            title="Capital Components Bundle",
            seller_character=SimpleNamespace(character_id=123456, name="Seller Prime"),
            location_text="Amarr VIII (Oris)",
            location=None,
            division_name=None,
        )
        settings = SimpleNamespace(
            eve_sso_client_id="client-id",
            eve_sso_client_secret="client-secret",
            token_encryption_key="",
            frontend_url="https://eqm.example",
        )
        token_response = SimpleNamespace(status_code=200, json=lambda: {"access_token": "buyer-token"})
        sso_client = AsyncMock()
        sso_client.__aenter__.return_value.post.return_value = token_response
        mail_client = SimpleNamespace(post=AsyncMock(return_value=None))
        db = SimpleNamespace(scalar=lambda _query: listing)
        with patch("app.api.esi.get_settings", return_value=settings), patch(
            "app.api.esi.httpx.AsyncClient", return_value=sso_client
        ), patch("app.api.esi.validate_eve_access_token", AsyncMock(return_value={"sub": "CHARACTER:EVE:987654"})), patch(
            "app.api.esi.EsiClient", return_value=mail_client
        ):
            response = await auth_callback(code="authorization-code", state=state, db=db)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "https://eqm.example/?eve_mail=opened#exchange/PACKAGE42")
        mail_client.post.assert_awaited_once()
        path, payload = mail_client.post.await_args.args
        self.assertEqual(path, "/ui/openwindow/newmail/")
        self.assertEqual(payload["recipients"], [123456])
        self.assertIn("Capital Components Bundle", payload["body"])
        self.assertIn("contract to this character", payload["body"])


if __name__ == "__main__":
    unittest.main()