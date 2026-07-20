import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

import yaml

from tests.helpers import ROOT


VALIDATOR = Path("scripts/validate-instructions.sh")
WRAPPER = Path("scripts/validate-feature-context.sh")


@contextmanager
def repository_copy():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "repository"
        root.mkdir()
        for name in (
            ".claude",
            ".specify",
            "scripts",
            "CLAUDE.md",
            "implementation_status.md",
            "requirements-policy.txt",
        ):
            source = ROOT / name
            destination = root / name
            if source.is_dir():
                shutil.copytree(
                    source,
                    destination,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                )
            else:
                shutil.copy2(source, destination)
        yield root


def run_script(
    root: Path,
    script: Path = VALIDATOR,
    *arguments: str,
    cwd: Path | None = None,
    python: str | None = None,
    through_bash: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = [str(root / script), *arguments]
    if through_bash:
        command.insert(0, "bash")
    environment = os.environ.copy()
    environment["POLICY_PYTHON"] = python or sys.executable
    return subprocess.run(
        command,
        cwd=cwd or root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


class ValidatorCliTest(unittest.TestCase):
    def test_repository_passes_from_an_unrelated_working_directory(self):
        with repository_copy() as root, tempfile.TemporaryDirectory() as cwd:
            result = run_script(root, cwd=Path(cwd))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            result.stdout,
            "WARNING: no context supplied; repository-only validation performed\n"
            "OK: instruction system validation passed\n",
        )

    def test_validator_aggregates_missing_rule_line_limit_and_broken_link(self):
        with repository_copy() as root:
            (root / ".claude/rules/security.md").unlink()
            claude_path = root / "CLAUDE.md"
            claude_path.write_text(
                claude_path.read_text(encoding="utf-8")
                + "\n[Broken validator fixture](missing-target.md)\n"
                + ("padding\n" * 351),
                encoding="utf-8",
            )

            result = run_script(root)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertGreaterEqual(result.stdout.count("ERROR:"), 3, result.stdout)
        self.assertIn(".claude/rules/security.md", result.stdout)
        self.assertIn("350", result.stdout)
        self.assertIn("missing-target.md", result.stdout)

    def test_unexpected_instruction_artifact_fails_exact_inventory(self):
        with repository_copy() as root:
            (root / ".claude/rules/unexpected.md").write_text(
                "# Unexpected\n", encoding="utf-8"
            )

            result = run_script(root)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("unexpected artifact", result.stdout.lower())
        self.assertIn(".claude/rules/unexpected.md", result.stdout)

    def test_instruction_artifact_symlink_cannot_escape_repository(self):
        with repository_copy() as root:
            security_rule = root / ".claude/rules/security.md"
            security_rule.unlink()
            outside_rule = root.parent / "outside-security.md"
            outside_rule.write_text("# External file\n", encoding="utf-8")
            security_rule.symlink_to(outside_rule)

            result = run_script(root)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("symlink escapes repository", result.stdout)
        self.assertIn(".claude/rules/security.md", result.stdout)

    def test_unconfigured_repository_rejects_enabled_remote_actions_semantically(self):
        with repository_copy() as root:
            project_path = root / ".claude/project.yaml"
            project = yaml.safe_load(project_path.read_text(encoding="utf-8"))
            project["remote_actions"]["enabled"] = True
            project["remote_actions"]["push_branch"] = True
            project_path.write_text(
                yaml.safe_dump(project, sort_keys=False), encoding="utf-8"
            )

            result = run_script(root)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("unconfigured", result.stdout.lower())
        self.assertIn("remote_actions", result.stdout)

    def test_missing_lifecycle_term_fails(self):
        with repository_copy() as root:
            claude_path = root / "CLAUDE.md"
            claude_path.write_text(
                claude_path.read_text(encoding="utf-8").replace(
                    "ROLLBACK_REQUIRED", "ROLLBACK_NEEDED"
                ),
                encoding="utf-8",
            )

            result = run_script(root)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("ROLLBACK_REQUIRED", result.stdout)

    def test_required_ci_sentence_is_exact(self):
        with repository_copy() as root:
            claude_path = root / "CLAUDE.md"
            claude_path.write_text(
                claude_path.read_text(encoding="utf-8").replace(
                    "Required CI on the exact merge candidate is authoritative for merge.",
                    "Required CI is useful for merge.",
                ),
                encoding="utf-8",
            )

            result = run_script(root)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("exact merge candidate", result.stdout)

    def test_script_executable_bits_are_validated(self):
        with repository_copy() as root:
            policy_engine = root / "scripts/policy-engine.py"
            policy_engine.chmod(0o644)

            result = run_script(root, through_bash=True)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("not executable", result.stdout)
        self.assertIn("scripts/policy-engine.py", result.stdout)

    def test_feature_context_wrapper_forwards_context_and_status(self):
        with repository_copy() as root:
            feature_directory = root / "specs/001-validator"
            feature_directory.mkdir(parents=True)
            shutil.copy2(
                ROOT / "tests/fixtures/contexts/maintenance-low.yaml",
                feature_directory / "instruction-context.yaml",
            )

            result = run_script(root, WRAPPER, str(feature_directory))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "OK: instruction system validation passed\n")

    def test_feature_context_wrapper_requires_exactly_one_directory(self):
        with repository_copy() as root:
            result = run_script(root, WRAPPER)

        self.assertEqual(result.returncode, 2)
        self.assertIn("Usage:", result.stderr)

    def test_primary_validator_rejects_unknown_arguments_with_usage_status(self):
        with repository_copy() as root:
            result = run_script(root, VALIDATOR, "--unknown")

        self.assertEqual(result.returncode, 2)
        self.assertIn("Usage:", result.stderr)

    def test_explicit_missing_python_is_a_stable_technical_block(self):
        with repository_copy() as root:
            result = run_script(root, python=str(root / "missing-python"))

        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("Python 3.11+", result.stderr)
        self.assertIn("PyYAML", result.stderr)
        self.assertIn("jsonschema", result.stderr)

    def test_readme_documents_supported_python_invocation(self):
        readme = (ROOT / ".claude/README.md").read_text(encoding="utf-8")

        self.assertIn("Python 3.11+", readme)
        self.assertIn(".venv/bin/python", readme)
        self.assertNotRegex(readme, r"(?m)^python scripts/policy-engine\.py")


if __name__ == "__main__":
    unittest.main()
