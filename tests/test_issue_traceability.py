from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
P0_COMPLETED_SLICE_ARTIFACTS = {
    1: (
        "docs/design/2026-08-16-p0-package-baseline-retrospective.md",
        "docs/plans/2026-08-16-p0-package-baseline-retrospective.md",
    ),
    2: (
        "docs/design/2026-08-15-sdd-compatibility-projection.md",
        "docs/plans/2026-08-15-sdd-compatibility-projection.md",
    ),
    3: (
        "docs/design/2026-08-15-thin-root-agent-adapters.md",
        "docs/plans/2026-08-15-thin-root-agent-adapters.md",
    ),
}


class IssueTraceabilityTest(unittest.TestCase):
    def test_completed_p0_slice_artifacts_are_present_and_tracked(self):
        paths = [path for pair in P0_COMPLETED_SLICE_ARTIFACTS.values() for path in pair]
        for path in paths:
            self.assertTrue((ROOT / path).is_file(), path)
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", *paths],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_slice_one_backfill_is_explicitly_retrospective(self):
        for path in P0_COMPLETED_SLICE_ARTIFACTS[1]:
            content = (ROOT / path).read_text(encoding="utf-8").lower()
            self.assertIn("retrospective reconstruction", content)
            self.assertIn("introduces no new decision", content)
