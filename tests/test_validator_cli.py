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
            ".sdd",
            ".claude",
            ".specify",
            "scripts",
            "src",
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
    environment_updates: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [str(root / script), *arguments]
    if through_bash:
        command.insert(0, "bash")
    environment = os.environ.copy()
    environment["POLICY_PYTHON"] = python or sys.executable
    environment.update(environment_updates or {})
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

    def test_primary_validator_rejects_stale_generated_output(self):
        with repository_copy() as root:
            canonical = root / ".sdd/modules/rules/security.md"
            canonical.write_text(canonical.read_text("utf-8") + "\nCanonical change.\n")
            result = run_script(root)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("stale_output", result.stdout)
        self.assertIn(".claude/rules/security.md", result.stdout)

    def test_primary_validator_rejects_desired_output_with_stale_manifest_metadata(self):
        with repository_copy() as root:
            canonical = root / ".sdd/modules/rules/security.md"
            generated = root / ".claude/rules/security.md"
            canonical.write_text(canonical.read_text("utf-8") + "\nCanonical change.\n")
            generated.write_bytes(canonical.read_bytes())
            result = run_script(root)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("invalid_manifest", result.stdout)
        self.assertIn(".sdd/generated-files.json", result.stdout)

    def test_primary_validator_rejects_manual_generated_edit(self):
        with repository_copy() as root:
            generated = root / ".claude/rules/security.md"
            generated.write_text(generated.read_text("utf-8") + "\nManual edit.\n")
            result = run_script(root)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("conflicting_output", result.stdout)

    def test_projection_technical_block_propagates_exit_three(self):
        with repository_copy() as root:
            (root / "scripts/render-compatibility.py").write_text(
                "#!/usr/bin/env python3\n"
                "print('ERROR: technical_block: -: cannot inspect projection')\n"
                "raise SystemExit(3)\n",
                encoding="utf-8",
            )
            result = run_script(root)

        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("technical", result.stdout.lower() + result.stderr.lower())

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

    def test_non_python_executable_cannot_spoof_runtime_probe(self):
        with repository_copy() as root:
            result = run_script(root, python="/usr/bin/true")

        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("BLOCKED_TECHNICAL", result.stderr)
        self.assertNotIn("OK: instruction system validation passed", result.stdout)

    def test_runtime_probe_rejects_extra_sentinel_output(self):
        with repository_copy() as root:
            fake_python = root.parent / "fake-python"
            fake_python.write_text(
                "#!/bin/sh\n"
                "printf 'POLICY_RUNTIME_OK_3_11_PYYAML_6_JSONSCHEMA_4\\n\\n'\n",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)

            result = run_script(root, python=str(fake_python))

        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("BLOCKED_TECHNICAL", result.stderr)
        self.assertNotIn("OK: instruction system validation passed", result.stdout)

    def test_incompatible_dependency_version_blocks_runtime_probe(self):
        with repository_copy() as root:
            site_directory = root.parent / "controlled-site"
            site_directory.mkdir()
            (site_directory / "sitecustomize.py").write_text(
                "from importlib import metadata\n"
                "_real_version = metadata.version\n"
                "def _controlled_version(name):\n"
                "    if name == 'PyYAML':\n"
                "        return '7.0'\n"
                "    return _real_version(name)\n"
                "metadata.version = _controlled_version\n",
                encoding="utf-8",
            )

            result = run_script(
                root,
                environment_updates={"PYTHONPATH": str(site_directory)},
            )

        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("BLOCKED_TECHNICAL", result.stderr)
        self.assertNotIn("OK: instruction system validation passed", result.stdout)

    def test_non_object_engine_json_is_an_actionable_validation_error(self):
        with repository_copy() as root:
            engine_path = root / "scripts/policy-engine.py"
            engine_path.write_text("print('[]')\n", encoding="utf-8")

            result = run_script(root)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("policy engine response must be a JSON object", result.stdout)
        self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_invalid_utf8_instruction_artifact_is_aggregated_without_traceback(self):
        with repository_copy() as root:
            (root / ".claude/profiles/regulated.md").write_bytes(b"\xff\xfe")

            result = run_script(root)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("ERROR:", result.stdout)
        self.assertIn(".claude/profiles/regulated.md", result.stdout)
        self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_missing_reference_definition_fails(self):
        with repository_copy() as root:
            claude_path = root / "CLAUDE.md"
            claude_path.write_text(
                claude_path.read_text(encoding="utf-8")
                + "\n[Broken reference][missing-ref]\n",
                encoding="utf-8",
            )

            result = run_script(root)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("missing reference definition", result.stdout)
        self.assertIn("missing-ref", result.stdout)

    def test_broken_reference_definition_target_fails(self):
        with repository_copy() as root:
            claude_path = root / "CLAUDE.md"
            claude_path.write_text(
                claude_path.read_text(encoding="utf-8")
                + "\n[Broken reference][missing-ref]\n"
                + "[missing-ref]: missing-reference.md\n",
                encoding="utf-8",
            )

            result = run_script(root)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("broken local Markdown link", result.stdout)
        self.assertIn("missing-reference.md", result.stdout)

    def test_balanced_parentheses_and_angle_bracket_destinations_are_valid(self):
        with repository_copy() as root:
            (root / "reference(target).md").write_text("# Target\n", encoding="utf-8")
            (root / "reference target.md").write_text("# Target\n", encoding="utf-8")
            claude_path = root / "CLAUDE.md"
            claude_path.write_text(
                claude_path.read_text(encoding="utf-8")
                + "\n[Inline parentheses](reference(target).md)\n"
                + "[Angle destination](<reference target.md>)\n"
                + "[Reference parentheses][paren-ref]\n"
                + "[paren-ref]: reference(target).md\n",
                encoding="utf-8",
            )

            result = run_script(root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(result.stdout.endswith("OK: instruction system validation passed\n"))

    def test_readme_documents_supported_python_invocation(self):
        readme = (ROOT / ".claude/README.md").read_text(encoding="utf-8")

        self.assertIn("Python 3.11+", readme)
        self.assertIn(".venv/bin/python", readme)
        self.assertNotRegex(readme, r"(?m)^python scripts/policy-engine\.py")


if __name__ == "__main__":
    unittest.main()
