from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.services.fitting_math_engine import evaluate_fitting_math_with_engine


class FittingMathEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = {
            "schema_version": "eqm.fitting-math-input.v1",
            "stacking_cases": [],
            "capacitor_cases": [{
                "name": "test capacitor",
                "capacity": 3000.0,
                "recharge_seconds": 184800.0,
                "sample_percent": 25.0,
                "drain_per_second": 0.2,
            }],
        }
        self.python_result = {
            "schema_version": "eqm.fitting-math-output.v1",
            "stacking_cases": [],
            "capacitor_cases": [{
                "name": "test capacitor",
                "recharge_at_sample": 0.040584415584415584,
                "stable_percent": None,
                "depletion_seconds": 17429.0,
            }],
        }

    @patch("app.services.fitting_math_engine.subprocess.run")
    def test_rust_mode_sends_json_over_stdin(self, run) -> None:
        run.return_value = SimpleNamespace(
            returncode=0,
            stderr="",
            stdout=json.dumps(self.python_result),
        )

        result = evaluate_fitting_math_with_engine(
            payload=self.payload,
            python_result=self.python_result,
            engine="rust",
            binary="/test/eqm-core",
            timeout=1,
        )

        self.assertEqual(result["engine_used"], "rust")
        self.assertEqual(
            run.call_args.args[0],
            ["/test/eqm-core", "fitting-math", "--input", "-"],
        )
        self.assertEqual(json.loads(run.call_args.kwargs["input"]), self.payload)

    @patch(
        "app.services.fitting_math_engine.subprocess.run",
        side_effect=FileNotFoundError("missing"),
    )
    def test_rust_mode_falls_back_to_python(self, _run) -> None:
        result = evaluate_fitting_math_with_engine(
            payload=self.payload,
            python_result=self.python_result,
            engine="rust",
            binary="/missing/eqm-core",
            timeout=1,
        )

        self.assertEqual(result["engine_used"], "python-fallback")
        self.assertEqual(result["capacitor_cases"], self.python_result["capacitor_cases"])
        self.assertIn("missing", result["engine_fallback_reason"])

    @patch("app.services.fitting_math_engine._run_rust")
    def test_shadow_mode_retains_python_and_reports_match(self, run_rust) -> None:
        run_rust.return_value = self.python_result

        result = evaluate_fitting_math_with_engine(
            payload=self.payload,
            python_result=self.python_result,
            engine="shadow",
        )

        self.assertEqual(result["engine_used"], "python-shadow")
        self.assertTrue(result["engine_shadow_match"])

    @unittest.skipUnless(Path("/usr/local/bin/eqm-core").exists(), "packaged Rust binary is unavailable")
    def test_packaged_rust_binary_accepts_fixture_over_stdin(self) -> None:
        fixtures = Path(__file__).parent / "fixtures"
        payload = json.loads((fixtures / "fitting-math-input.v1.json").read_text())
        expected = json.loads((fixtures / "fitting-math-output.v1.json").read_text())
        completed = subprocess.run(
            ["/usr/local/bin/eqm-core", "fitting-math", "--input", "-"],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=5,
            check=True,
        )
        self.assertEqual(json.loads(completed.stdout), expected)


if __name__ == "__main__":
    unittest.main()
