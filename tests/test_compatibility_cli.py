import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from sdd.adapters.compatibility import build_projection
from tests.projection_helpers import projection_repository, tree_snapshot


SCRIPT = Path("scripts/render-compatibility.py")


def run_cli(root: Path, *arguments: str):
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    return subprocess.run(
        [sys.executable, str(root / SCRIPT), "--root", str(root), *arguments],
        cwd=root.parent,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


class CompatibilityCliTest(unittest.TestCase):
    def prepare_script(self, root: Path) -> None:
        source = Path(__file__).resolve().parents[1] / SCRIPT
        destination = root / SCRIPT
        destination.parent.mkdir(exist_ok=True)
        destination.write_bytes(source.read_bytes())
        shutil.copytree(
            Path(__file__).resolve().parents[1] / "src",
            root / "src",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )

    def test_check_succeeds_from_unrelated_working_directory(self):
        with projection_repository() as root:
            self.prepare_script(root)
            plan = build_projection(root)
            (root / ".sdd/generated-files.json").write_bytes(plan.manifest_bytes)
            result = run_cli(root, "--check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "OK: compatibility projection is current\n")
        self.assertEqual(result.stderr, "")

    def test_stale_check_returns_one_with_stable_finding(self):
        with projection_repository() as root:
            self.prepare_script(root)
            plan = build_projection(root)
            (root / ".sdd/generated-files.json").write_bytes(plan.manifest_bytes)
            (root / ".sdd/modules/rules/security.md").write_text("# Changed\n")
            result = run_cli(root, "--check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("ERROR: stale_output: .claude/rules/security.md:", result.stdout)

    def test_invalid_invocation_returns_two(self):
        with projection_repository() as root:
            self.prepare_script(root)
            result = run_cli(root, "--check", "--write")
        self.assertEqual(result.returncode, 2)
        self.assertIn("usage:", result.stderr.lower())

    def test_check_creates_no_bytecode_or_other_files(self):
        with projection_repository() as root:
            self.prepare_script(root)
            plan = build_projection(root)
            (root / ".sdd/generated-files.json").write_bytes(plan.manifest_bytes)
            before = tree_snapshot(root)
            result = run_cli(root, "--check")
            after = tree_snapshot(root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(after, before)
        self.assertEqual(list(root.rglob("__pycache__")), [])

    def test_write_converges_stale_output(self):
        with projection_repository() as root:
            self.prepare_script(root)
            initial = build_projection(root)
            (root / ".sdd/generated-files.json").write_bytes(initial.manifest_bytes)
            source = root / ".sdd/modules/rules/security.md"
            source.write_text("# Desired\n")
            result = run_cli(root, "--write")
            desired = build_projection(root)
            check = run_cli(root, "--check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "OK: compatibility projection updated\n")
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)

    def test_nonexistent_root_returns_three_without_traceback(self):
        with projection_repository() as root:
            self.prepare_script(root)
            missing = root / "missing"
            result = subprocess.run(
                [sys.executable, str(root / SCRIPT), "--root", str(missing), "--check"],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 3)
        self.assertIn("technical_block", result.stdout)
        self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_invalid_manifest_returns_one(self):
        with projection_repository() as root:
            self.prepare_script(root)
            (root / ".sdd/generated-files.json").write_text("{}\n")
            result = run_cli(root, "--check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("invalid_manifest", result.stdout)
