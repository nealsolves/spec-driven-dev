import json
import subprocess
import sys
import unittest
from pathlib import Path

from tests.helpers import ROOT


ENGINE = ROOT / "scripts/policy-engine.py"
CONTEXTS = ROOT / "tests/fixtures/contexts"


def run_engine(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ENGINE), *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


class LegacyCliCharacterizationTest(unittest.TestCase):
    def test_validate_success_is_single_json_object_with_zero_exit(self):
        result = run_engine("validate", "--root", str(ROOT))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(json.loads(result.stdout), {"errors": [], "valid": True})
        self.assertEqual(result.stdout.count("\n"), 1)

    def test_evaluate_preserves_routing_risk_and_authority_outcomes(self):
        cases = (
            (
                "maintenance-low.yaml",
                "maintenance-001",
                ["documentation_only"],
                "low",
                "autonomous",
                ["workflows/maintenance.md"],
            ),
            (
                "authorization-high.yaml",
                "authorization-001",
                [
                    "security_sensitive",
                    "production_impact",
                    "observability_impact",
                    "release",
                ],
                "high",
                "autonomous_with_enhanced_gates",
                ["workflows/feature-development.md", "workflows/release.md"],
            ),
        )

        for filename, change_id, classifications, risk, authority, workflows in cases:
            with self.subTest(filename=filename):
                result = run_engine(
                    "evaluate",
                    "--root",
                    str(ROOT),
                    "--context",
                    str(CONTEXTS / filename),
                )

                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(result.stderr, "")
                payload = json.loads(result.stdout)
                self.assertTrue(payload["valid"])
                self.assertEqual(payload["change_id"], change_id)
                self.assertEqual(payload["classifications"], classifications)
                self.assertEqual(payload["risk"]["tier"], risk)
                self.assertEqual(payload["authority"]["outcome"], authority)
                self.assertEqual(payload["workflows"], workflows)
                self.assertEqual(
                    set(payload["hashes"]),
                    {"policy_hash", "context_hash", "change_hash"},
                )
                self.assertTrue(
                    all(len(value) == 64 for value in payload["hashes"].values())
                )

    def test_invalid_command_is_a_json_error_with_nonzero_exit(self):
        result = run_engine("unknown-command")

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        self.assertFalse(payload["valid"])
        self.assertEqual(len(payload["errors"]), 1)
        self.assertIn("invalid choice", payload["errors"][0])


if __name__ == "__main__":
    unittest.main()
