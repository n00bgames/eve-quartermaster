from __future__ import annotations

import json
import subprocess
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.services.planetary_simulation import SimulationPin
from app.services.planetary_simulation_engine import simulate_colony_with_engine


UTC = timezone.utc


class PlanetarySimulationEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.checkpoint = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
        self.projected = self.checkpoint + timedelta(minutes=5)
        self.pins = [SimulationPin(pin_id=10, kind="storage", contents={1: 42})]

    @patch("app.services.planetary_simulation_engine.subprocess.run")
    def test_rust_mode_sends_json_over_stdin_and_decodes_result(self, run) -> None:
        run.return_value = SimpleNamespace(
            returncode=0,
            stderr="",
            stdout=json.dumps({
                "checkpoint_at": "2026-08-28T12:00:00Z",
                "projected_at": "2026-08-28T12:05:00Z",
                "is_projection": True,
                "events_processed": 0,
                "truncated": False,
                "pins": {
                    "10": {
                        "contents": {"1": 42},
                        "status": "online",
                        "produced": {},
                        "blocked": {},
                    }
                },
            }),
        )

        result = simulate_colony_with_engine(
            checkpoint_at=self.checkpoint,
            projected_at=self.projected,
            pins=self.pins,
            routes=[],
            type_volumes={1: 1.0},
            engine="rust",
            binary="/test/eqm-core",
            timeout=1,
        )

        self.assertEqual(result["engine_used"], "rust")
        self.assertEqual(result["pins"][10]["contents"], {1: 42})
        command = run.call_args.args[0]
        payload = json.loads(run.call_args.kwargs["input"])
        self.assertEqual(command, ["/test/eqm-core", "colony-simulation", "--input", "-"])
        self.assertEqual(payload["schema_version"], "eqm.planetary-colony-simulation-input.v1")
        self.assertEqual(payload["pins"][0]["contents"], {"1": 42})

    @patch("app.services.planetary_simulation_engine.subprocess.run", side_effect=FileNotFoundError("missing"))
    def test_rust_mode_falls_back_to_python(self, _run) -> None:
        result = simulate_colony_with_engine(
            checkpoint_at=None,
            projected_at=self.projected,
            pins=self.pins,
            routes=[],
            type_volumes={1: 1.0},
            engine="rust",
            binary="/missing/eqm-core",
            timeout=1,
        )

        self.assertEqual(result["engine_used"], "python-fallback")
        self.assertEqual(result["pins"][10]["contents"], {1: 42})
        self.assertIn("missing", result["engine_fallback_reason"])

    @patch("app.services.planetary_simulation_engine._run_rust")
    def test_shadow_mode_retains_python_and_reports_match(self, run_rust) -> None:
        python_shape = {
            "checkpoint_at": None,
            "projected_at": self.projected,
            "is_projection": False,
            "events_processed": 0,
            "truncated": False,
            "pins": {
                10: {
                    "contents": {1: 42},
                    "status": "online",
                    "produced": {},
                    "blocked": {},
                }
            },
        }
        run_rust.return_value = python_shape

        result = simulate_colony_with_engine(
            checkpoint_at=None,
            projected_at=self.projected,
            pins=self.pins,
            routes=[],
            type_volumes={1: 1.0},
            engine="shadow",
        )

        self.assertEqual(result["engine_used"], "python-shadow")
        self.assertTrue(result["engine_shadow_match"])

    @unittest.skipUnless(Path("/usr/local/bin/eqm-core").exists(), "packaged Rust binary is unavailable")
    def test_packaged_rust_binary_accepts_fixture_over_stdin(self) -> None:
        fixtures = Path(__file__).parent / "fixtures"
        payload = json.loads(
            (fixtures / "planetary-colony-simulation-input.v1.json").read_text()
        )
        expected = json.loads(
            (fixtures / "planetary-colony-simulation-output.v1.json").read_text()
        )
        completed = subprocess.run(
            ["/usr/local/bin/eqm-core", "colony-simulation", "--input", "-"],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=5,
            check=True,
        )
        self.assertEqual(json.loads(completed.stdout), expected)


if __name__ == "__main__":
    unittest.main()
