from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.services.fitting_resources_engine import evaluate_fitting_resources_with_engine


class FittingResourcesEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = {
            "schema_version": "eqm.fitting-resources-input.v1",
            "ship_attrs": {"cpuOutput": 100.0, "hiSlots": 1.0},
            "skill_levels": {},
            "items": [],
        }
        self.python_result = {
            "schema_version": "eqm.fitting-resources-output.v1",
            "effective_ship_attrs": {
                "cpuOutput": 100.0,
                "powerOutput": None,
                "hiSlots": 1.0,
                "subsystemMHTFittingReduction": None,
                "subsystemMMissileFittingReduction": None,
            },
            "resources": {
                "cpu": {"used": 0.0, "capacity": 100.0, "ok": True, "percent": 0.0},
                "powergrid": {"used": 0.0, "capacity": None, "ok": True, "percent": None},
                "calibration": {"used": 0.0, "capacity": None, "ok": True, "percent": None},
            },
            "slots": [],
            "item_usage": [],
            "stats_item_ids": [],
        }

    @patch("app.services.fitting_resources_engine.subprocess.run")
    def test_rust_mode_sends_json_over_stdin(self, run) -> None:
        run.return_value = SimpleNamespace(
            returncode=0,
            stderr="",
            stdout=json.dumps(self.python_result),
        )

        result = evaluate_fitting_resources_with_engine(
            payload=self.payload,
            python_result=self.python_result,
            engine="rust",
            binary="/test/eqm-core",
            timeout=1,
        )

        self.assertEqual(result["engine_used"], "rust")
        self.assertEqual(
            run.call_args.args[0],
            ["/test/eqm-core", "fitting-resources", "--input", "-"],
        )
        self.assertEqual(json.loads(run.call_args.kwargs["input"]), self.payload)

    @patch(
        "app.services.fitting_resources_engine.subprocess.run",
        side_effect=FileNotFoundError("missing"),
    )
    def test_rust_mode_falls_back_to_python(self, _run) -> None:
        result = evaluate_fitting_resources_with_engine(
            payload=self.payload,
            python_result=self.python_result,
            engine="rust",
            binary="/missing/eqm-core",
            timeout=1,
        )

        self.assertEqual(result["engine_used"], "python-fallback")
        self.assertEqual(result["resources"], self.python_result["resources"])
        self.assertIn("missing", result["engine_fallback_reason"])

    @patch("app.services.fitting_resources_engine._run_rust")
    def test_shadow_mode_retains_python_and_reports_match(self, run_rust) -> None:
        run_rust.return_value = self.python_result

        result = evaluate_fitting_resources_with_engine(
            payload=self.payload,
            python_result=self.python_result,
            engine="shadow",
        )

        self.assertEqual(result["engine_used"], "python-shadow")
        self.assertTrue(result["engine_shadow_match"])

    @unittest.skipUnless(Path("/usr/local/bin/eqm-core").exists(), "packaged Rust binary is unavailable")
    def test_packaged_rust_binary_accepts_fixture_over_stdin(self) -> None:
        fixtures = Path(__file__).parent / "fixtures"
        payload = json.loads((fixtures / "fitting-resources-input.v1.json").read_text())
        expected = json.loads((fixtures / "fitting-resources-output.v1.json").read_text())
        completed = subprocess.run(
            ["/usr/local/bin/eqm-core", "fitting-resources", "--input", "-"],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=5,
            check=True,
        )
        self.assertEqual(json.loads(completed.stdout), expected)


if __name__ == "__main__":
    unittest.main()
