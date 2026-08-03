from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.events import build_analytics
from app.models import (
    Base,
    Doctrine,
    EsiToken,
    EveAlliance,
    EveCharacter,
    EveCorporation,
    Event,
    EventAttendanceEntry,
    EventCharacterRegistration,
    EventUserResponse,
    User,
)
from app.schemas.events import AttendanceManualCreate, EventCreate
from app.services.events import (
    active_owned_characters,
    attendance_is_open,
    can_record_attendance,
    event_is_visible,
)


UTC = timezone.utc


class EventSchemaTests(unittest.TestCase):
    def test_event_requires_timezone_aware_start(self) -> None:
        with self.assertRaises(ValidationError):
            EventCreate(title="Timezone Test", event_type="fleet", start_at=datetime(2026, 8, 5, 1, 0))

    def test_event_rejects_invalid_time_order(self) -> None:
        start = datetime(2026, 8, 5, 1, 0, tzinfo=UTC)
        with self.assertRaises(ValidationError):
            EventCreate(
                title="Time Order Test",
                event_type="fleet",
                formup_at=start + timedelta(minutes=5),
                start_at=start,
            )

    def test_scheduled_event_requires_formup_location(self) -> None:
        with self.assertRaises(ValidationError):
            EventCreate(
                title="Missing Formup",
                event_type="fleet",
                lifecycle_status="scheduled",
                start_at=datetime(2026, 8, 5, 1, 0, tzinfo=UTC),
            )

    def test_manual_attendance_source_requirements(self) -> None:
        with self.assertRaises(ValidationError):
            AttendanceManualCreate(attendee_source="external_character", display_name="Pilot")
        guest = AttendanceManualCreate(attendee_source="public_guest", display_name="  Guest Pilot  ")
        self.assertEqual(guest.display_name, "Guest Pilot")


class EventServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(
            self.engine,
            tables=[
                User.__table__,
                EveAlliance.__table__,
                EveCorporation.__table__,
                EveCharacter.__table__,
                EsiToken.__table__,
                Doctrine.__table__,
                Event.__table__,
                EventUserResponse.__table__,
                EventCharacterRegistration.__table__,
                EventAttendanceEntry.__table__,
            ],
        )
        self.db = Session(self.engine)
        self.host = User(email="host-events@example.test", display_name="Host", role="host")
        self.officer = User(email="officer-events@example.test", display_name="Officer", role="officer")
        self.member = User(email="member-events@example.test", display_name="Member", role="member")
        self.db.add_all([self.host, self.officer, self.member])
        self.db.flush()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def add_character(self, user: User, *, active: bool, corporation_id: int | None = None) -> EveCharacter:
        sequence = self.db.query(EveCharacter).count() + 1
        character = EveCharacter(
            character_id=91_000_000 + sequence,
            name=f"Pilot {sequence}",
            owner_user_id=user.id,
            corporation_id=corporation_id,
        )
        self.db.add(character)
        self.db.flush()
        self.db.add(
            EsiToken(
                user_id=user.id,
                character_id=character.id,
                scopes="esi-assets.read_assets.v1",
                encrypted_refresh_token="encrypted",
                revoked_at=None if active else datetime.now(UTC),
            )
        )
        self.db.flush()
        return character

    def add_event(self, creator: User, **overrides) -> Event:
        values = {
            "title": "Test Operation",
            "event_type": "fleet",
            "lifecycle_status": "completed",
            "registration_status": "locked",
            "created_by_user_id": creator.id,
            "start_at": datetime.now(UTC) - timedelta(hours=3),
            "end_at": datetime.now(UTC) - timedelta(hours=1),
            "audience_kind": "all_members",
            "composition_visibility": "participants",
        }
        values.update(overrides)
        event = Event(**values)
        self.db.add(event)
        self.db.flush()
        return event

    @patch("app.services.events.can_view_section", return_value=True)
    def test_active_owned_characters_require_non_revoked_token(self, _mock) -> None:
        active = self.add_character(self.member, active=True)
        self.add_character(self.member, active=False)
        self.assertEqual([row.id for row in active_owned_characters(self.member, self.db)], [active.id])

    @patch("app.services.events.can_view_section", return_value=True)
    def test_corporation_visibility_uses_active_character_affiliation(self, _mock) -> None:
        corporation = EveCorporation(corporation_id=98_000_001, name="Event Corp")
        self.db.add(corporation)
        self.db.flush()
        event = self.add_event(
            self.host,
            audience_kind="corporation",
            audience_corporation_id=corporation.id,
        )
        self.assertFalse(event_is_visible(event, self.member, self.db))
        self.add_character(self.member, active=True, corporation_id=corporation.id)
        self.assertTrue(event_is_visible(event, self.member, self.db))

    @patch("app.services.events.can_view_section", return_value=True)
    def test_officer_can_record_post_event_attendance_without_owning_event(self, _mock) -> None:
        event = self.add_event(self.host)
        self.assertTrue(attendance_is_open(event))
        self.assertTrue(can_record_attendance(event, self.officer, self.db))
        self.assertFalse(can_record_attendance(event, self.member, self.db))

    @patch("app.services.events.can_view_section", return_value=True)
    def test_event_without_end_must_be_completed_before_attendance(self, _mock) -> None:
        event = self.add_event(
            self.host,
            lifecycle_status="scheduled",
            end_at=None,
            estimated_duration_minutes=None,
        )
        self.assertFalse(attendance_is_open(event))
        event.lifecycle_status = "completed"
        self.assertTrue(attendance_is_open(event))

    def test_one_user_can_register_multiple_characters_for_one_event(self) -> None:
        first_character = self.add_character(self.member, active=True)
        second_character = self.add_character(self.member, active=True)
        event = self.add_event(
            self.host,
            lifecycle_status="scheduled",
            registration_status="open",
            end_at=datetime.now(UTC) + timedelta(hours=2),
            start_at=datetime.now(UTC) + timedelta(hours=1),
        )
        self.db.add_all(
            [
                EventCharacterRegistration(
                    event_id=event.id,
                    user_id=self.member.id,
                    character_id=first_character.id,
                    character_eve_id_snapshot=first_character.character_id,
                    character_name_snapshot=first_character.name,
                    confirmation_status="confirmed",
                ),
                EventCharacterRegistration(
                    event_id=event.id,
                    user_id=self.member.id,
                    character_id=second_character.id,
                    character_eve_id_snapshot=second_character.character_id,
                    character_name_snapshot=second_character.name,
                    confirmation_status="tentative",
                ),
            ]
        )
        self.db.commit()
        registrations = self.db.query(EventCharacterRegistration).filter_by(
            event_id=event.id,
            user_id=self.member.id,
        ).order_by(EventCharacterRegistration.character_id).all()
        self.assertEqual([row.character_id for row in registrations], [first_character.id, second_character.id])
        self.assertEqual([row.confirmation_status for row in registrations], ["confirmed", "tentative"])
    def test_attendance_is_separate_and_unique_per_registration(self) -> None:
        character = self.add_character(self.member, active=True)
        event = self.add_event(self.host)
        response = EventUserResponse(event_id=event.id, user_id=self.member.id, status="going")
        registration = EventCharacterRegistration(
            event_id=event.id,
            user_id=self.member.id,
            character_id=character.id,
            character_eve_id_snapshot=character.character_id,
            character_name_snapshot=character.name,
            registration_status="registered",
        )
        self.db.add_all([response, registration])
        self.db.flush()
        attendance = EventAttendanceEntry(
            event_id=event.id,
            registration_id=registration.id,
            attendee_source="registration",
            attendance_status="attended",
            character_id=character.id,
            character_eve_id_snapshot=character.character_id,
            display_name_snapshot=character.name,
        )
        self.db.add(attendance)
        self.db.commit()
        self.assertEqual(response.status, "going")
        self.assertEqual(registration.registration_status, "registered")
        duplicate = EventAttendanceEntry(
            event_id=event.id,
            registration_id=registration.id,
            attendee_source="registration",
            attendance_status="no_show",
            character_id=character.id,
            character_eve_id_snapshot=character.character_id,
            display_name_snapshot=character.name,
        )
        self.db.add(duplicate)
        with self.assertRaises(IntegrityError):
            self.db.commit()


class EventAnalyticsTests(unittest.TestCase):
    def test_analytics_compares_registration_with_actual_attendance(self) -> None:
        start = datetime(2026, 8, 1, 19, 0, tzinfo=UTC)
        registrations = [
            SimpleNamespace(id=1, registration_status="registered"),
            SimpleNamespace(id=2, registration_status="registered"),
            SimpleNamespace(id=3, registration_status="registered"),
            SimpleNamespace(id=4, registration_status="waitlisted"),
        ]
        attendance = [
            SimpleNamespace(registration_id=1, attendance_status="attended"),
            SimpleNamespace(registration_id=2, attendance_status="no_show"),
            SimpleNamespace(registration_id=None, attendance_status="attended"),
        ]
        event = SimpleNamespace(
            event_type="fleet",
            start_at=start,
            responses=[
                SimpleNamespace(status="going"),
                SimpleNamespace(status="maybe"),
                SimpleNamespace(status="declined"),
            ],
            registrations=registrations,
            attendance_entries=attendance,
        )
        result = build_analytics([event], start - timedelta(days=1), start + timedelta(days=1), "day")
        totals = result["totals"]
        self.assertEqual(totals["event_count"], 1)
        self.assertEqual(totals["registered_characters"], 3)
        self.assertEqual(totals["attended_registered"], 1)
        self.assertEqual(totals["attended_unregistered"], 1)
        self.assertEqual(totals["no_show"], 1)
        self.assertEqual(totals["unmarked"], 1)
        self.assertEqual(totals["attendance_rate"]["numerator"], 1)
        self.assertEqual(totals["attendance_rate"]["denominator"], 3)
        self.assertEqual(totals["attendance_rate"]["percent"], 33.3)

    def test_zero_registration_denominator_is_not_zero_percent(self) -> None:
        start = datetime(2026, 8, 1, 19, 0, tzinfo=UTC)
        event = SimpleNamespace(
            event_type="social",
            start_at=start,
            responses=[],
            registrations=[],
            attendance_entries=[SimpleNamespace(registration_id=None, attendance_status="attended")],
        )
        result = build_analytics([event], start, start + timedelta(days=1), "day")
        self.assertIsNone(result["totals"]["attendance_rate"]["percent"])


if __name__ == "__main__":
    unittest.main()
