from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.services.planetary_simulation import (
    SimulationPin,
    SimulationRoute,
    SimulationSchematic,
    known_pin_capacity_m3,
    simulate_colony,
)


UTC = timezone.utc


class PlanetarySimulationTests(unittest.TestCase):
    def test_shared_colony_fixture_matches_python_reference(self) -> None:
        fixtures = Path(__file__).parent / "fixtures"
        payload = json.loads(
            (fixtures / "planetary-colony-simulation-input.v1.json").read_text()
        )
        expected = json.loads(
            (fixtures / "planetary-colony-simulation-output.v1.json").read_text()
        )

        def parse_time(value: str | None) -> datetime | None:
            return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None

        pins = []
        for item in payload["pins"]:
            schematic = item.get("schematic")
            pins.append(
                SimulationPin(
                    pin_id=item["pin_id"],
                    kind=item["kind"],
                    contents={int(key): value for key, value in item.get("contents", {}).items()},
                    capacity_m3=item.get("capacity_m3"),
                    schematic=SimulationSchematic(
                        cycle_time=schematic["cycle_time"],
                        inputs={int(key): value for key, value in schematic["inputs"].items()},
                        output_type_id=schematic["output_type_id"],
                        output_quantity=schematic["output_quantity"],
                    ) if schematic else None,
                    last_cycle_start=parse_time(item.get("last_cycle_start")),
                    install_time=parse_time(item.get("install_time")),
                    expiry_time=parse_time(item.get("expiry_time")),
                    extractor_cycle_time=item.get("extractor_cycle_time"),
                    extractor_product_type_id=item.get("extractor_product_type_id"),
                    extractor_quantity_per_cycle=item.get("extractor_quantity_per_cycle"),
                    extractor_decay_factor=item.get("extractor_decay_factor", 0.012),
                    extractor_noise_factor=item.get("extractor_noise_factor", 0.8),
                )
            )
        result = simulate_colony(
            checkpoint_at=parse_time(payload["checkpoint_at"]),
            projected_at=parse_time(payload["projected_at"]),
            pins=pins,
            routes=[SimulationRoute(**item) for item in payload["routes"]],
            type_volumes={int(key): value for key, value in payload["type_volumes"].items()},
            max_events=payload["max_events"],
        )
        result["checkpoint_at"] = result["checkpoint_at"].isoformat().replace("+00:00", "Z")
        result["projected_at"] = result["projected_at"].isoformat().replace("+00:00", "Z")

        self.assertEqual(json.loads(json.dumps(result)), expected)

    def test_running_factory_consumes_routed_inputs_and_projects_output(self) -> None:
        checkpoint = datetime(2026, 8, 4, 0, 30, tzinfo=UTC)
        schematic = SimulationSchematic(
            cycle_time=3600,
            inputs={1: 40, 2: 40},
            output_type_id=3,
            output_quantity=3,
        )
        result = simulate_colony(
            checkpoint_at=checkpoint,
            projected_at=checkpoint + timedelta(hours=1, minutes=31),
            pins=[
                SimulationPin(pin_id=10, kind="storage", contents={1: 80, 2: 80}, capacity_m3=10_000),
                SimulationPin(
                    pin_id=20,
                    kind="factory",
                    schematic=schematic,
                    last_cycle_start=checkpoint - timedelta(minutes=30),
                ),
                SimulationPin(pin_id=30, kind="storage", capacity_m3=10_000),
            ],
            routes=[
                SimulationRoute(10, 20, 1, 40),
                SimulationRoute(10, 20, 2, 40),
                SimulationRoute(20, 30, 3, 3),
            ],
            type_volumes={1: 1.0, 2: 1.0, 3: 6.0},
        )

        self.assertEqual(result["pins"][30]["contents"], {3: 6})
        self.assertEqual(result["pins"][10]["contents"], {})
        self.assertEqual(result["pins"][20]["status"], "running")
        self.assertEqual(result["events_processed"], 2)

    def test_factory_output_respects_destination_capacity(self) -> None:
        checkpoint = datetime(2026, 8, 4, 0, 30, tzinfo=UTC)
        result = simulate_colony(
            checkpoint_at=checkpoint,
            projected_at=checkpoint + timedelta(minutes=31),
            pins=[
                SimulationPin(
                    pin_id=20,
                    kind="factory",
                    schematic=SimulationSchematic(3600, {}, 3, 3),
                    last_cycle_start=checkpoint - timedelta(minutes=30),
                ),
                SimulationPin(pin_id=30, kind="storage", capacity_m3=1.0),
            ],
            routes=[SimulationRoute(20, 30, 3, 3)],
            type_volumes={3: 1.0},
        )

        self.assertEqual(result["pins"][30]["contents"], {3: 1})
        self.assertEqual(result["pins"][20]["blocked"], {3: 2})
        self.assertEqual(result["pins"][20]["status"], "blocked")

    def test_missing_checkpoint_preserves_observed_contents(self) -> None:
        now = datetime(2026, 8, 4, tzinfo=UTC)
        result = simulate_colony(
            checkpoint_at=None,
            projected_at=now,
            pins=[SimulationPin(pin_id=10, kind="storage", contents={1: 42})],
            routes=[],
            type_volumes={1: 1.0},
        )

        self.assertFalse(result["is_projection"])
        self.assertEqual(result["pins"][10]["contents"], {1: 42})

    def test_known_storage_capacities(self) -> None:
        self.assertEqual(known_pin_capacity_m3("Temperate Launchpad"), 10_000)
        self.assertEqual(known_pin_capacity_m3("Storage Facility"), 12_000)
        self.assertEqual(known_pin_capacity_m3("Command Center"), 500)
        self.assertIsNone(known_pin_capacity_m3("High-Tech Production Plant"))


if __name__ == "__main__":
    unittest.main()
