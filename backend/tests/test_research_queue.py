from __future__ import annotations

from datetime import datetime, timezone
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import Base, ResearchQueueItem
from app.services.research_queue import (
    clean_queue_activity,
    clean_queue_runs,
    clean_queue_status,
    clean_source_hangar,
    serialize_queue_item,
)


class ResearchQueueValidationTests(unittest.TestCase):
    def test_activity_choices_follow_blueprint_kind(self) -> None:
        self.assertEqual(clean_queue_activity(4, is_copy=False), 4)
        self.assertEqual(clean_queue_activity(8, is_copy=True), 8)
        with self.assertRaises(HTTPException):
            clean_queue_activity(8, is_copy=False)
        with self.assertRaises(HTTPException):
            clean_queue_activity(4, is_copy=True)

    def test_runs_status_and_hangar_validation(self) -> None:
        self.assertEqual(clean_queue_runs("12"), 12)
        self.assertEqual(clean_queue_status("Completed"), "completed")
        self.assertEqual(clean_source_hangar("  Corp Hangar 3  "), "Corp Hangar 3")
        with self.assertRaises(HTTPException):
            clean_queue_runs(0)
        with self.assertRaises(HTTPException):
            clean_queue_status("running")


class ResearchQueuePersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine, tables=[ResearchQueueItem.__table__])

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_queue_entry_keeps_snapshot_and_completion_history(self) -> None:
        with Session(self.engine) as db:
            item = ResearchQueueItem(
                blueprint_name="Raven Blueprint",
                blueprint_kind="BPO",
                owner_name="Example Corporation",
                material_efficiency=10,
                time_efficiency=20,
                source_location_name="Example Station",
                source_hangar="Industry Hangar",
                activity_id=5,
                runs=10,
                status="pending",
                sort_order=0,
            )
            db.add(item)
            db.commit()
            db.refresh(item)

            saved = db.scalar(select(ResearchQueueItem))
            self.assertEqual(saved.blueprint_name, "Raven Blueprint")
            self.assertEqual(saved.source_hangar, "Industry Hangar")
            self.assertEqual(serialize_queue_item(saved)["activity_name"], "Copying")

            saved.status = "completed"
            saved.completed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(saved)
            self.assertEqual(saved.status, "completed")
            self.assertIsNotNone(saved.completed_at)


if __name__ == "__main__":
    unittest.main()
