from __future__ import annotations

from datetime import datetime, timezone
import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import Base, EveCategory, EveGroup, EveSystem, EveType, Note, NoteItem, User
from app.services.item_lines import parse_item_line, parse_item_lines
from app.services.notes import clean_item_status, clean_quantity, clean_tags


class ItemLineParserTests(unittest.TestCase):
    def test_supported_quantity_formats(self) -> None:
        cases = {
            "Tritanium x5,000": ("Tritanium", 5000),
            "5000 Tritanium": ("Tritanium", 5000),
            "Tritanium": ("Tritanium", 1),
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                row = parse_item_line(raw)
                self.assertIsNotNone(row)
                self.assertEqual((row.name, row.quantity), expected)

    def test_duplicate_lines_remain_separate_unless_merge_is_requested(self) -> None:
        rows, duplicates = parse_item_lines("Tritanium x5\ntritanium x7")
        self.assertEqual([row.quantity for row in rows], [5, 7])
        self.assertEqual(duplicates[0]["quantity"], 12)

        merged, _ = parse_item_lines("Tritanium x5\ntritanium x7", merge_duplicates=True)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].quantity, 12)

    def test_quantity_and_status_validation(self) -> None:
        self.assertEqual(clean_quantity("42"), 42)
        self.assertEqual(clean_item_status("In_Transit"), "in_transit")
        with self.assertRaises(Exception):
            clean_quantity(0)
        with self.assertRaises(Exception):
            clean_item_status("lost")

    def test_tags_are_deduplicated_without_changing_order(self) -> None:
        self.assertEqual(clean_tags(["Doctrine", "doctrine", "Jita"]), ["Doctrine", "Jita"])


class NotesPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        tables = [
            User.__table__,
            EveCategory.__table__,
            EveGroup.__table__,
            EveType.__table__,
            EveSystem.__table__,
            Note.__table__,
            NoteItem.__table__,
        ]
        Base.metadata.create_all(self.engine, tables=tables)

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_private_note_and_items_can_be_created_updated_and_soft_deleted(self) -> None:
        with Session(self.engine) as db:
            user = User(email="pilot@example.test", display_name="Pilot", role="member")
            item_type = EveType(type_id=34, name="Tritanium", published=True)
            system = EveSystem(system_id=30000142, name="Jita", security_status=0.945)
            db.add_all([user, item_type, system])
            db.flush()
            note = Note(
                owner_user_id=user.id,
                note_type="item_list",
                title="Jita resupply",
                destination_system_id=system.system_id,
                tags=["market"],
            )
            db.add(note)
            db.flush()
            item = NoteItem(
                note_id=note.id,
                type_id=item_type.type_id,
                original_text="Tritanium x5000",
                canonical_name=item_type.name,
                requested_quantity=5000,
                status="needed",
                sort_order=0,
            )
            db.add(item)
            db.commit()

            saved = db.scalar(select(Note).where(Note.owner_user_id == user.id))
            self.assertEqual(saved.title, "Jita resupply")
            self.assertEqual(saved.items[0].requested_quantity, 5000)

            saved.items[0].status = "delivered"
            saved.deleted_at = datetime.now(timezone.utc)
            db.commit()

            updated = db.get(Note, saved.id)
            self.assertEqual(updated.items[0].status, "delivered")
            self.assertIsNotNone(updated.deleted_at)


if __name__ == "__main__":
    unittest.main()