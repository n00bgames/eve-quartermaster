from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from fastapi import HTTPException

from app.api.corporate_exchange import (
    appraisal_manifest,
    appraisal_payload,
    clean_choice,
    listing_location,
    market_appraisal_payload,
    parse_datetime,
)
from app.api.corporate_exchange_bids import clean_external_identity
from app.services.exchange_bids import auction_payload, next_bid_floor, validate_bid
from app.services.exchange_listing_updates import apply_listing_edits


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


if __name__ == "__main__":
    unittest.main()