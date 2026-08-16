import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from sdd.adapters.agent import build_adapter_plan, serialize_adapter_manifest
from tests.agent_adapter_helpers import agent_adapter_repository, tree_snapshot


SCRIPT = Path("scripts/render-agent-adapters.py")


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


class AgentAdapterCliTest(unittest.TestCase):
    def prepare_script(self, root: Path) -> None:
        source = Path(__file__).resolve().parents[1] / SCRIPT
        self.assertTrue(source.is_file(), f"missing CLI entrypoint: {source}")
        destination = root / SCRIPT
        destination.parent.mkdir(exist_ok=True)
        destination.write_bytes(source.read_bytes())
        shutil.copytree(
            Path(__file__).resolve().parents[1] / "src",
            root / "src",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )

    def make_current(self, root: Path) -> None:
        plan = build_adapter_plan(root)
        for output in plan.outputs:
            (root / output.target).write_bytes(output.payload)
        (root / ".sdd/agent-adapters.generated.json").write_bytes(
            serialize_adapter_manifest(plan)
        )

    def test_check_succeeds_from_unrelated_working_directory(self):
        with agent_adapter_repository() as root:
            self.prepare_script(root)
            self.make_current(root)
            result = run_cli(root, "--check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "OK: root agent adapters are current\n")
        self.assertEqual(result.stderr, "")

    def test_drift_check_returns_one_with_stable_finding(self):
        with agent_adapter_repository() as root:
            self.prepare_script(root)
            self.make_current(root)
            (root / "CLAUDE.md").write_text("unmanaged change\n", encoding="utf-8")
            result = run_cli(root, "--check")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(
            result.stdout,
            "ERROR: conflicting_output: CLAUDE.md: adapter output matches neither "
            "desired nor prior ownership\n",
        )
        self.assertEqual(result.stderr, "")

    def test_invalid_invocation_returns_two(self):
        with agent_adapter_repository() as root:
            self.prepare_script(root)
            result = run_cli(root, "--check", "--write")
        self.assertEqual(result.returncode, 2)
        self.assertIn("usage:", result.stderr.lower())

    def test_check_creates_no_bytecode_or_other_files(self):
        with agent_adapter_repository() as root:
            self.prepare_script(root)
            self.make_current(root)
            before = tree_snapshot(root)
            result = run_cli(root, "--check")
            after = tree_snapshot(root)
            bytecode = list(root.rglob("__pycache__")) + list(root.rglob("*.pyc"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(after, before)
        self.assertEqual(bytecode, [])

    def test_write_converges_owned_stale_outputs(self):
        with agent_adapter_repository() as root:
            self.prepare_script(root)
            self.make_current(root)
            (root / ".sdd/adapters/root-kernel.md").write_text(
                "## Purpose and Scope\n\nUpdated canonical policy lives in `.sdd/`.\n",
                encoding="utf-8",
            )
            result = run_cli(root, "--write")
            check = run_cli(root, "--check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "OK: root agent adapters updated\n")
        self.assertEqual(result.stderr, "")
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)

    def test_write_preserves_unmanaged_divergent_legacy_file(self):
        with agent_adapter_repository() as root:
            self.prepare_script(root)
            legacy = b"legacy unmanaged root instructions\n"
            (root / "CLAUDE.md").write_bytes(legacy)
            before = tree_snapshot(root)
            result = run_cli(root, "--write")
            after = tree_snapshot(root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(
            result.stdout,
            "ERROR: conflicting_output: CLAUDE.md: adapter output matches neither "
            "desired nor prior ownership\n",
        )
        self.assertEqual(result.stderr, "")
        self.assertEqual(after, before)

    def test_nonexistent_root_returns_three_without_traceback(self):
        with agent_adapter_repository() as root:
            self.prepare_script(root)
            missing = root / "missing"
            result = subprocess.run(
                [sys.executable, str(root / SCRIPT), "--root", str(missing), "--check"],
                check=False,
                capture_output=True,
                text=True,
            )
            try:
                missing.resolve(strict=True)
            except OSError as exc:
                expected_stdout = f"ERROR: technical_block: -: {exc}\n"
            else:
                self.fail("missing root unexpectedly resolved")
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout, expected_stdout)
        self.assertEqual(result.stderr, "")

    def test_missing_package_returns_three_without_traceback(self):
        with agent_adapter_repository() as root:
            self.prepare_script(root)
            (root / "src/sdd/adapters/agent.py").unlink()
            result = run_cli(root, "--check")
        self.assertEqual(result.returncode, 3)
        self.assertEqual(
            result.stdout,
            "ERROR: technical_block: -: No module named 'sdd.adapters.agent'\n",
        )
        self.assertEqual(result.stderr, "")

    def test_corrupt_package_returns_three_without_traceback(self):
        with agent_adapter_repository() as root:
            self.prepare_script(root)
            (root / "src/sdd/adapters/agent.py").write_text("def broken(:\n")
            result = run_cli(root, "--check")
        self.assertEqual(result.returncode, 3)
        self.assertEqual(
            result.stdout,
            "ERROR: technical_block: -: invalid syntax (agent.py, line 1)\n",
        )
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
