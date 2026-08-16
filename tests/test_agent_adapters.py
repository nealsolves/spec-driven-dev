import dataclasses
import errno
import hashlib
import json
import os
import re
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from unittest import mock

from sdd.adapters import agent
from sdd.adapters.agent import (
    AdapterFailure,
    AdapterLimits,
    build_adapter_plan,
)
from tests.agent_adapter_helpers import (
    CONFIG,
    agent_adapter_repository,
    tree_snapshot,
)


class AdapterPlanningTest(unittest.TestCase):
    def assert_plan_code(self, root: Path, expected_code: str) -> None:
        with self.assertRaises(AdapterFailure) as raised:
            build_adapter_plan(root)
        self.assertIn(expected_code, {finding.code for finding in raised.exception.findings})
        for finding in raised.exception.findings:
            if finding.path is not None:
                self.assertFalse(finding.path.is_absolute())

    def write_config(self, root: Path, content: str | bytes) -> None:
        path = root / ".sdd/controls/adapters.yaml"
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")

    def test_plan_has_deterministic_target_order_and_exact_shared_body(self):
        with agent_adapter_repository() as root:
            first = build_adapter_plan(root)
            second = build_adapter_plan(root)
            kernel = (root / ".sdd/adapters/root-kernel.md").read_bytes()
            raw_config = (root / ".sdd/controls/adapters.yaml").read_bytes()

        self.assertEqual(first, second)
        self.assertEqual(
            [item.target.as_posix() for item in first.outputs],
            ["AGENTS.md", "CLAUDE.md"],
        )
        self.assertEqual(first.format, 1)
        self.assertEqual(first.renderer, "sdd.adapters.agent:v1")
        self.assertEqual(first.config_sha256, hashlib.sha256(raw_config).hexdigest())
        self.assertEqual(first.kernel_sha256, hashlib.sha256(kernel).hexdigest())
        for output in first.outputs:
            self.assertTrue(output.payload.endswith(kernel))
            self.assertEqual(output.payload, output.preamble + kernel)
            self.assertEqual(output.sha256, hashlib.sha256(output.payload).hexdigest())
            self.assertEqual(output.byte_count, len(output.payload))
            self.assertEqual(output.line_count, output.payload.count(b"\n"))
        self.assertNotEqual(first.outputs[0].preamble, first.outputs[1].preamble)

    def test_preambles_are_informational_and_only_preambles_differ(self):
        with agent_adapter_repository() as root:
            plan = build_adapter_plan(root)
            kernel = (root / ".sdd/adapters/root-kernel.md").read_bytes()

        codex, claude = plan.outputs
        self.assertIn(b"generated", codex.preamble.lower())
        self.assertIn(b"Codex", codex.preamble)
        self.assertIn(b"Claude", claude.preamble)
        self.assertIn(b"do not edit", codex.preamble.lower())
        self.assertIn(b".sdd/controls/adapters.yaml", codex.preamble)
        self.assertIn(b".sdd/adapters/root-kernel.md", codex.preamble)
        self.assertEqual(
            codex.preamble.replace(b"Codex", b"host"),
            claude.preamble.replace(b"Claude", b"host"),
        )
        self.assertEqual(codex.payload[len(codex.preamble) :], kernel)
        self.assertEqual(claude.payload[len(claude.preamble) :], kernel)

    def test_planning_is_non_mutating_and_dataclasses_are_immutable(self):
        with agent_adapter_repository(include_outputs=True) as root:
            before = tree_snapshot(root)
            plan = build_adapter_plan(root)
            after = tree_snapshot(root)

        self.assertEqual(after, before)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            plan.outputs[0].name = "changed"  # type: ignore[misc]
        with self.assertRaises(dataclasses.FrozenInstanceError):
            AdapterLimits(280, 180, 16384).max_lines = 1  # type: ignore[misc]

    def test_kernel_requires_utf8_lf_and_exactly_one_trailing_newline(self):
        invalid_kernels = {
            "invalid UTF-8": b"## Purpose\n\xff\n",
            "CRLF": b"## Purpose\r\n",
            "missing trailing newline": b"## Purpose",
            "two trailing newlines": b"## Purpose\n\n",
        }
        for label, payload in invalid_kernels.items():
            with self.subTest(label=label), agent_adapter_repository() as root:
                (root / ".sdd/adapters/root-kernel.md").write_bytes(payload)
                self.assert_plan_code(root, "invalid_kernel")

    def test_config_requires_utf8_lf_and_exactly_one_trailing_newline(self):
        invalid_configs = {
            "invalid UTF-8": CONFIG.encode("utf-8") + b"\xff",
            "CRLF": CONFIG.replace("\n", "\r\n").encode("utf-8"),
            "missing trailing newline": CONFIG.rstrip("\n"),
            "two trailing newlines": CONFIG + "\n",
        }
        for label, payload in invalid_configs.items():
            with self.subTest(label=label), agent_adapter_repository() as root:
                self.write_config(root, payload)
                self.assert_plan_code(root, "invalid_config")

    def test_config_rejects_unknown_missing_and_non_mapping_fields(self):
        invalid_configs = {
            "unknown root key": CONFIG + "unexpected: true\n",
            "missing root key": CONFIG.replace("format: 1\n", ""),
            "root sequence": "- format\n- 1\n",
            "unknown limit key": CONFIG.replace(
                "  max_bytes: 16384\n", "  max_bytes: 16384\n  unexpected: 1\n"
            ),
            "missing limit key": CONFIG.replace("  target_lines: 180\n", ""),
            "limits sequence": CONFIG.replace(
                "limits:\n  max_lines: 280\n  target_lines: 180\n  max_bytes: 16384\n",
                "limits: [280, 180, 16384]\n",
            ),
            "unknown output key": CONFIG + "  other: OTHER.md\n",
            "missing output key": CONFIG.replace("  claude: CLAUDE.md\n", ""),
            "outputs sequence": CONFIG.replace(
                "outputs:\n  claude: CLAUDE.md\n  codex: AGENTS.md\n",
                "outputs: [CLAUDE.md, AGENTS.md]\n",
            ),
        }
        for label, content in invalid_configs.items():
            with self.subTest(label=label), agent_adapter_repository() as root:
                self.write_config(root, content)
                self.assert_plan_code(root, "invalid_config")

    def test_config_rejects_duplicate_mapping_keys(self):
        duplicate_configs = {
            "root": CONFIG.replace("format: 1\n", "format: 1\nformat: 1\n"),
            "limits": CONFIG.replace(
                "  max_lines: 280\n", "  max_lines: 280\n  max_lines: 280\n"
            ),
            "outputs": CONFIG.replace(
                "  claude: CLAUDE.md\n", "  claude: CLAUDE.md\n  claude: CLAUDE.md\n"
            ),
        }
        for label, content in duplicate_configs.items():
            with self.subTest(label=label), agent_adapter_repository() as root:
                self.write_config(root, content)
                self.assert_plan_code(root, "invalid_config")

    def test_config_rejects_unsupported_or_non_integer_values(self):
        invalid_configs = {
            "unsupported format": CONFIG.replace("format: 1", "format: 2"),
            "boolean format": CONFIG.replace("format: 1", "format: true"),
            "string max lines": CONFIG.replace("max_lines: 280", "max_lines: '280'"),
            "boolean target lines": CONFIG.replace("target_lines: 180", "target_lines: false"),
            "float max bytes": CONFIG.replace("max_bytes: 16384", "max_bytes: 16384.0"),
            "hard line limit above 280": CONFIG.replace("max_lines: 280", "max_lines: 281"),
            "nonpositive target": CONFIG.replace("target_lines: 180", "target_lines: 0"),
            "target above hard limit": CONFIG.replace("target_lines: 180", "target_lines: 281"),
            "nonpositive byte limit": CONFIG.replace("max_bytes: 16384", "max_bytes: 0"),
        }
        for label, content in invalid_configs.items():
            with self.subTest(label=label), agent_adapter_repository() as root:
                self.write_config(root, content)
                self.assert_plan_code(root, "invalid_config")

    def test_config_rejects_noncanonical_and_unsafe_paths(self):
        invalid_configs = {
            "absolute kernel": CONFIG.replace(
                ".sdd/adapters/root-kernel.md", "/tmp/root-kernel.md"
            ),
            "traversing kernel": CONFIG.replace(
                ".sdd/adapters/root-kernel.md", ".sdd/adapters/../root-kernel.md"
            ),
            "wrong kernel": CONFIG.replace(
                ".sdd/adapters/root-kernel.md", ".sdd/adapters/other.md"
            ),
            "absolute output": CONFIG.replace("CLAUDE.md", "/tmp/CLAUDE.md"),
            "traversing output": CONFIG.replace("AGENTS.md", "nested/../AGENTS.md"),
            "wrong output": CONFIG.replace("AGENTS.md", "OTHER.md"),
            "duplicate output": CONFIG.replace("CLAUDE.md", "AGENTS.md"),
            "swapped outputs": CONFIG.replace("CLAUDE.md", "TEMP.md")
            .replace("AGENTS.md", "CLAUDE.md")
            .replace("TEMP.md", "AGENTS.md"),
        }
        for label, content in invalid_configs.items():
            with self.subTest(label=label), agent_adapter_repository() as root:
                self.write_config(root, content)
                self.assert_plan_code(root, "invalid_config")

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable")
    def test_symlinked_control_or_kernel_fails_closed(self):
        for relative in (
            PurePosixPath(".sdd/controls/adapters.yaml"),
            PurePosixPath(".sdd/adapters/root-kernel.md"),
        ):
            with self.subTest(path=relative.as_posix()), agent_adapter_repository() as root:
                source = root / relative
                alternate = source.with_name("alternate")
                source.rename(alternate)
                source.symlink_to(alternate)
                self.assert_plan_code(root, "unsafe_path")

    @unittest.skipUnless(
        hasattr(os, "symlink")
        and hasattr(os, "mkfifo")
        and hasattr(os, "O_NOFOLLOW")
        and os.open in os.supports_dir_fd,
        "descriptor-relative no-follow traversal is unavailable",
    )
    def test_source_replacement_at_read_boundary_fails_without_blocking(self):
        with agent_adapter_repository() as root:
            kernel = root / ".sdd/adapters/root-kernel.md"
            alternate = kernel.with_name("alternate-kernel.md")
            alternate.write_text("## Replaced\n", encoding="utf-8")
            real_read_bytes = Path.read_bytes
            real_open = os.open
            swap_kind: str | None = None

            def legacy_read_bytes(path: Path) -> bytes:
                nonlocal swap_kind
                if path == kernel and swap_kind is None:
                    path.unlink()
                    path.symlink_to(alternate.name)
                    swap_kind = "symlink"
                return real_read_bytes(path)

            def adversarial_open(
                path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
                flags: int,
                mode: int = 0o777,
                *,
                dir_fd: int | None = None,
            ) -> int:
                nonlocal swap_kind
                if path == agent.KERNEL_PATH.name and dir_fd is not None and swap_kind is None:
                    kernel.unlink()
                    os.mkfifo(kernel)
                    swap_kind = "fifo"
                return real_open(path, flags, mode, dir_fd=dir_fd)

            with mock.patch.object(Path, "read_bytes", legacy_read_bytes), mock.patch.object(
                os, "open", adversarial_open
            ):
                self.assert_plan_code(root, "unsafe_path")

        self.assertIsNotNone(swap_kind)

    def test_missing_or_special_sources_fail_closed(self):
        for relative in (
            PurePosixPath(".sdd/controls/adapters.yaml"),
            PurePosixPath(".sdd/adapters/root-kernel.md"),
        ):
            with self.subTest(path=relative.as_posix()), agent_adapter_repository() as root:
                (root / relative).unlink()
                self.assert_plan_code(root, "unsafe_path")

        if hasattr(os, "mkfifo"):
            with agent_adapter_repository() as root:
                kernel = root / ".sdd/adapters/root-kernel.md"
                kernel.unlink()
                os.mkfifo(kernel)
                self.assert_plan_code(root, "unsafe_path")

    def test_output_line_and_byte_hard_limits_are_enforced_without_truncation(self):
        with agent_adapter_repository() as root:
            kernel = root / ".sdd/adapters/root-kernel.md"
            kernel.write_bytes((b"line\n" * 280))
            self.assert_plan_code(root, "limit_exceeded")

        with agent_adapter_repository() as root:
            kernel = root / ".sdd/adapters/root-kernel.md"
            kernel.write_bytes((b"x" * 16384) + b"\n")
            self.assert_plan_code(root, "limit_exceeded")

    def test_output_at_exact_hard_limits_is_accepted(self):
        with agent_adapter_repository() as root:
            baseline = build_adapter_plan(root)
            longest_preamble = max(len(output.preamble) for output in baseline.outputs)
            kernel = root / ".sdd/adapters/root-kernel.md"
            kernel.write_bytes((b"x" * (16384 - longest_preamble - 1)) + b"\n")
            plan = build_adapter_plan(root)

        self.assertEqual(max(output.byte_count for output in plan.outputs), 16384)

        with agent_adapter_repository() as root:
            baseline = build_adapter_plan(root)
            preamble_lines = max(output.preamble.count(b"\n") for output in baseline.outputs)
            kernel = root / ".sdd/adapters/root-kernel.md"
            kernel.write_bytes(b"line\n" * (280 - preamble_lines))
            plan = build_adapter_plan(root)

        self.assertEqual(max(output.line_count for output in plan.outputs), 280)

    def test_repository_target_line_budget_is_met(self):
        repository = Path(__file__).resolve().parents[1]
        plan = build_adapter_plan(repository)

        self.assertTrue(plan.outputs)
        self.assertTrue(all(output.line_count <= 180 for output in plan.outputs))

    def test_repository_kernel_preserves_compact_contract(self):
        repository = Path(__file__).resolve().parents[1]
        kernel = (repository / ".sdd/adapters/root-kernel.md").read_text(encoding="utf-8")
        headings = [line for line in kernel.splitlines() if line.startswith("## ")]

        self.assertEqual(
            headings,
            [
                "## Purpose and Scope",
                "## Authority and Canonical Sources",
                "## Startup and Change Discovery",
                "## Routing and Deterministic Decisions",
                "## Implementation, Validation, and Review",
                "## Lifecycle and Stop Conditions",
                "## Git, CI, and Documentation Parity",
                "## Completion and Escalation",
            ],
        )
        required_literals = (
            "`.sdd/README.md`",
            "`.sdd/controls/project.yaml`",
            "`.sdd/controls/routing.yaml`",
            "`.sdd/controls/policy.yaml`",
            "`.sdd/controls/lifecycle.yaml`",
            "`.specify/memory/constitution.md`",
            "`implementation_status.md`",
            "`.venv/bin/python scripts/policy-engine.py validate --root . [--context PATH]`",
            "`.venv/bin/python scripts/policy-engine.py evaluate --root . --context PATH "
            "[--output PATH]`",
            "prohibited > human_required > autonomous_with_enhanced_gates > autonomous",
            "Required CI on the exact merge candidate is authoritative for merge.",
            "Work test-first",
            "every instruction-system change requires human authority",
            "`BLOCKED_REQUIREMENT`",
            "`BLOCKED_POLICY`",
            "`BLOCKED_TECHNICAL`",
            "`HUMAN_DECISION_REQUIRED`",
            "`ROLLBACK_REQUIRED`",
            "`INCIDENT`",
            "decision ID",
            "policy trigger",
            "bounded options",
            "recommended option",
            "required response fields",
            "policy, context, and change hashes",
        )
        for literal in required_literals:
            with self.subTest(literal=literal):
                self.assertIn(literal, kernel)

        self.assertLessEqual(len(kernel.splitlines()), 165)
        self.assertIsNone(re.search(r"\[[^]]+\]\([^)]+\)", kernel))
        self.assertNotIn(".claude/", kernel)
        non_path_text = kernel.replace("implementation_status.md", "")
        self.assertIsNone(
            re.search(r"\b(?:status|history|histories|historical)\b", non_path_text, re.I)
        )

    def test_repository_root_must_be_a_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "not-a-directory"
            root.write_text("file\n", encoding="utf-8")
            self.assert_plan_code(root, "technical_block")


class AdapterCheckingTest(unittest.TestCase):
    def initialize_parity(self, root: Path):
        plan = build_adapter_plan(root)
        for output in plan.outputs:
            target = root / output.target
            target.write_bytes(output.payload)
            target.chmod(0o644)
        (root / agent.MANIFEST_PATH).write_bytes(agent.serialize_adapter_manifest(plan))
        return plan

    def finding_codes(self, root: Path, plan) -> set[str]:
        return {finding.code for finding in agent.check_agent_adapters(root, plan)}

    def assert_invalid_manifest(self, root: Path) -> None:
        with self.assertRaises(AdapterFailure) as raised:
            agent.load_adapter_manifest(root)
        self.assertEqual(
            {finding.code for finding in raised.exception.findings},
            {"invalid_manifest"},
        )

    def canonical_manifest_value(self, plan) -> dict:
        return json.loads(agent.serialize_adapter_manifest(plan))

    def write_canonical_manifest(self, root: Path, value: object) -> None:
        (root / agent.MANIFEST_PATH).write_bytes(
            (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")
        )

    def test_manifest_serialization_is_exact_canonical_json_and_loads_immutably(self):
        with agent_adapter_repository() as root:
            plan = build_adapter_plan(root)
            agents, claude = plan.outputs
            expected = f'''{{
  "adapter_format": 1,
  "config": {{
    "path": ".sdd/controls/adapters.yaml",
    "sha256": "{plan.config_sha256}"
  }},
  "files": [
    {{
      "bytes": {agents.byte_count},
      "executable": false,
      "lines": {agents.line_count},
      "path": "AGENTS.md",
      "sha256": "{agents.sha256}"
    }},
    {{
      "bytes": {claude.byte_count},
      "executable": false,
      "lines": {claude.line_count},
      "path": "CLAUDE.md",
      "sha256": "{claude.sha256}"
    }}
  ],
  "format": 1,
  "kernel": {{
    "path": ".sdd/adapters/root-kernel.md",
    "sha256": "{plan.kernel_sha256}"
  }},
  "renderer": "sdd.adapters.agent:v1"
}}
'''.encode("utf-8")
            raw = agent.serialize_adapter_manifest(plan)
            (root / agent.MANIFEST_PATH).write_bytes(raw)
            manifest = agent.load_adapter_manifest(root)

        self.assertEqual(raw, expected)
        self.assertEqual(manifest.raw_bytes, expected)
        self.assertEqual(
            tuple(item[0].as_posix() for item in manifest.files),
            ("AGENTS.md", "CLAUDE.md"),
        )
        with self.assertRaises(dataclasses.FrozenInstanceError):
            manifest.renderer = "changed"  # type: ignore[misc]

    def test_manifest_rejects_missing_malformed_noncanonical_and_duplicate_keys(self):
        with agent_adapter_repository() as root:
            plan = build_adapter_plan(root)
            manifest = root / agent.MANIFEST_PATH
            invalid = (
                b"{",
                b"[]\n",
                agent.serialize_adapter_manifest(plan).replace(
                    b'  "format": 1,\n', b'  "format": 1,\n  "format": 1,\n'
                ),
                json.dumps(self.canonical_manifest_value(plan), separators=(",", ":")).encode(
                    "utf-8"
                ),
            )
            self.assert_invalid_manifest(root)
            for raw in invalid:
                with self.subTest(raw=raw[:40]):
                    manifest.write_bytes(raw)
                    self.assert_invalid_manifest(root)

    def test_manifest_rejects_every_non_strict_field_variant(self):
        def missing_root(value):
            value.pop("renderer")

        def unknown_root(value):
            value["host"] = "local"

        def boolean_format(value):
            value["format"] = True

        def wrong_renderer(value):
            value["renderer"] = "other:v1"

        def missing_nested(value):
            value["config"].pop("path")

        def unknown_file_key(value):
            value["files"][0]["mtime"] = 0

        def uppercase_digest(value):
            value["kernel"]["sha256"] = "A" * 64

        def short_digest(value):
            value["files"][0]["sha256"] = "0" * 63

        def negative_count(value):
            value["files"][0]["bytes"] = -1

        def boolean_count(value):
            value["files"][0]["lines"] = False

        def executable_true(value):
            value["files"][0]["executable"] = True

        def executable_integer(value):
            value["files"][0]["executable"] = 0

        def wrong_config_path(value):
            value["config"]["path"] = ".sdd/controls/other.yaml"

        def wrong_kernel_path(value):
            value["kernel"]["path"] = ".sdd/adapters/other.md"

        def wrong_output_path(value):
            value["files"][0]["path"] = "OTHER.md"

        def reversed_outputs(value):
            value["files"].reverse()

        def duplicate_outputs(value):
            value["files"][1] = dict(value["files"][0])

        mutations = (
            missing_root,
            unknown_root,
            boolean_format,
            wrong_renderer,
            missing_nested,
            unknown_file_key,
            uppercase_digest,
            short_digest,
            negative_count,
            boolean_count,
            executable_true,
            executable_integer,
            wrong_config_path,
            wrong_kernel_path,
            wrong_output_path,
            reversed_outputs,
            duplicate_outputs,
        )
        with agent_adapter_repository() as root:
            plan = build_adapter_plan(root)
            original = self.canonical_manifest_value(plan)
            for mutation in mutations:
                with self.subTest(mutation=mutation.__name__):
                    candidate = json.loads(json.dumps(original))
                    mutation(candidate)
                    self.write_canonical_manifest(root, candidate)
                    self.assert_invalid_manifest(root)

    def test_manifest_rejects_unrepresentable_paths(self):
        with agent_adapter_repository() as root:
            plan = build_adapter_plan(root)
            value = self.canonical_manifest_value(plan)
            value["files"][0]["path"] = "AGENTS\ud800.md"
            self.write_canonical_manifest(root, value)
            self.assert_invalid_manifest(root)

    def test_exact_parity_is_empty_and_check_does_not_mutate(self):
        with agent_adapter_repository() as root:
            plan = self.initialize_parity(root)
            before = tree_snapshot(root)
            findings = agent.check_agent_adapters(root, plan)
            after = tree_snapshot(root)

        self.assertEqual(findings, ())
        self.assertEqual(after, before)

    def test_missing_manifest_is_invalid_without_hiding_output_state(self):
        with agent_adapter_repository() as root:
            plan = build_adapter_plan(root)
            findings = agent.check_agent_adapters(root, plan)

        self.assertEqual(
            {(finding.code, finding.path) for finding in findings},
            {
                ("invalid_manifest", agent.MANIFEST_PATH),
                ("missing_output", PurePosixPath("AGENTS.md")),
                ("missing_output", PurePosixPath("CLAUDE.md")),
            },
        )

    def test_stale_canonical_digest_and_prior_owned_outputs_are_classified(self):
        with agent_adapter_repository() as root:
            prior = self.initialize_parity(root)
            (root / agent.KERNEL_PATH).write_text(
                "## Purpose and Scope\n\nChanged canonical policy.\n",
                encoding="utf-8",
            )
            desired = build_adapter_plan(root)
            findings = agent.check_agent_adapters(root, desired)

        self.assertNotEqual(prior.kernel_sha256, desired.kernel_sha256)
        self.assertEqual(
            {(finding.code, finding.path) for finding in findings},
            {
                ("invalid_source", agent.KERNEL_PATH),
                ("stale_output", PurePosixPath("AGENTS.md")),
                ("stale_output", PurePosixPath("CLAUDE.md")),
            },
        )

    def test_missing_divergent_and_executable_drift_outputs_are_classified(self):
        with agent_adapter_repository() as root:
            plan = self.initialize_parity(root)
            (root / "AGENTS.md").unlink()
            (root / "CLAUDE.md").write_text("unmanaged divergence\n", encoding="utf-8")
            findings = agent.check_agent_adapters(root, plan)
        self.assertEqual(
            {(finding.code, finding.path) for finding in findings},
            {
                ("missing_output", PurePosixPath("AGENTS.md")),
                ("conflicting_output", PurePosixPath("CLAUDE.md")),
            },
        )

        with agent_adapter_repository() as root:
            plan = self.initialize_parity(root)
            target = root / "AGENTS.md"
            target.chmod(target.stat().st_mode | 0o100)
            findings = agent.check_agent_adapters(root, plan)
        self.assertEqual(
            {(finding.code, finding.path) for finding in findings},
            {("conflicting_output", PurePosixPath("AGENTS.md"))},
        )

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable")
    def test_symlinked_manifest_and_symlinked_or_special_targets_fail_closed(self):
        with agent_adapter_repository() as root:
            plan = self.initialize_parity(root)
            manifest = root / agent.MANIFEST_PATH
            alternate = manifest.with_name("alternate.json")
            manifest.rename(alternate)
            manifest.symlink_to(alternate.name)
            self.assertEqual(self.finding_codes(root, plan), {"invalid_manifest"})

        with agent_adapter_repository() as root:
            plan = self.initialize_parity(root)
            target = root / "AGENTS.md"
            alternate = root / "alternate.md"
            target.rename(alternate)
            target.symlink_to(alternate.name)
            self.assertEqual(self.finding_codes(root, plan), {"unsafe_path"})

        if hasattr(os, "mkfifo"):
            with agent_adapter_repository() as root:
                plan = self.initialize_parity(root)
                target = root / "AGENTS.md"
                target.unlink()
                os.mkfifo(target)
                self.assertEqual(self.finding_codes(root, plan), {"unsafe_path"})

    def test_malformed_manifest_does_not_hide_conflicting_output(self):
        with agent_adapter_repository() as root:
            plan = self.initialize_parity(root)
            (root / agent.MANIFEST_PATH).write_bytes(b"{\n")
            (root / "AGENTS.md").write_text("unmanaged\n", encoding="utf-8")
            findings = agent.check_agent_adapters(root, plan)

        self.assertEqual(
            {(finding.code, finding.path) for finding in findings},
            {
                ("invalid_manifest", agent.MANIFEST_PATH),
                ("conflicting_output", PurePosixPath("AGENTS.md")),
            },
        )

    @unittest.skipUnless(
        hasattr(os, "symlink")
        and hasattr(os, "mkfifo")
        and hasattr(os, "O_NOFOLLOW")
        and os.open in os.supports_dir_fd,
        "descriptor-relative no-follow traversal is unavailable",
    )
    def test_manifest_and_target_replacement_at_read_boundary_fail_closed(self):
        with agent_adapter_repository() as root:
            plan = self.initialize_parity(root)
            manifest = root / agent.MANIFEST_PATH
            alternate = manifest.with_name("alternate.json")
            alternate.write_bytes(manifest.read_bytes())
            real_open = os.open
            swapped = False

            def adversarial_manifest_open(path, flags, mode=0o777, *, dir_fd=None):
                nonlocal swapped
                if path == agent.MANIFEST_PATH.name and dir_fd is not None and not swapped:
                    manifest.unlink()
                    manifest.symlink_to(alternate.name)
                    swapped = True
                return real_open(path, flags, mode, dir_fd=dir_fd)

            with mock.patch.object(Path, "read_bytes", side_effect=AssertionError), mock.patch.object(
                os, "open", adversarial_manifest_open
            ):
                self.assertEqual(self.finding_codes(root, plan), {"invalid_manifest"})
            self.assertTrue(swapped)

        with agent_adapter_repository() as root:
            plan = self.initialize_parity(root)
            target = root / "AGENTS.md"
            real_open = os.open
            swapped = False

            def adversarial_target_open(path, flags, mode=0o777, *, dir_fd=None):
                nonlocal swapped
                if path == "AGENTS.md" and dir_fd is not None and not swapped:
                    target.unlink()
                    os.mkfifo(target)
                    swapped = True
                return real_open(path, flags, mode, dir_fd=dir_fd)

            with mock.patch.object(Path, "read_bytes", side_effect=AssertionError), mock.patch.object(
                os, "open", adversarial_target_open
            ):
                self.assertEqual(self.finding_codes(root, plan), {"unsafe_path"})
            self.assertTrue(swapped)

    def test_unrepresentable_root_is_a_structured_technical_block(self):
        with agent_adapter_repository() as root:
            plan = build_adapter_plan(root)
        findings = agent.check_agent_adapters(Path("repository\ud800"), plan)
        self.assertEqual({finding.code for finding in findings}, {"technical_block"})

    def test_findings_are_sorted_by_path_then_code(self):
        with agent_adapter_repository() as root:
            plan = build_adapter_plan(root)
            findings = agent.check_agent_adapters(root, plan)

        keys = [
            (finding.path.as_posix() if finding.path is not None else "", finding.code)
            for finding in findings
        ]
        self.assertEqual(keys, sorted(keys))

    def test_limit_finding_aggregates_manifest_and_fixed_target_findings(self):
        with agent_adapter_repository() as root:
            plan = self.initialize_parity(root)
            payload = (b"x" * 16384) + b"\n"
            oversized = dataclasses.replace(
                plan.outputs[0],
                payload=payload,
                sha256=hashlib.sha256(payload).hexdigest(),
                byte_count=len(payload),
                line_count=payload.count(b"\n"),
            )
            forged = dataclasses.replace(plan, outputs=(oversized, plan.outputs[1]))
            (root / agent.MANIFEST_PATH).write_bytes(b"{\n")
            (root / "AGENTS.md").unlink()
            (root / "AGENTS.md").mkdir()
            (root / "CLAUDE.md").write_text("unmanaged\n", encoding="utf-8")
            findings = agent.check_agent_adapters(root, forged)

            with self.assertRaises(AdapterFailure) as raised:
                agent.serialize_adapter_manifest(forged)

        self.assertEqual(
            {(finding.code, finding.path) for finding in findings},
            {
                ("limit_exceeded", PurePosixPath("AGENTS.md")),
                ("invalid_manifest", agent.MANIFEST_PATH),
                ("unsafe_path", PurePosixPath("AGENTS.md")),
                ("conflicting_output", PurePosixPath("CLAUDE.md")),
            },
        )
        self.assertEqual(
            {(finding.code, finding.path) for finding in raised.exception.findings},
            {("limit_exceeded", PurePosixPath("AGENTS.md"))},
        )

    def test_manifest_capability_and_resource_failures_are_technical_blocks(self):
        with agent_adapter_repository() as root:
            self.initialize_parity(root)
            with mock.patch.object(agent, "_OPEN_SUPPORTS_DIR_FD", False):
                with self.assertRaises(AdapterFailure) as raised:
                    agent.load_adapter_manifest(root)
            self.assertEqual(
                {finding.code for finding in raised.exception.findings},
                {"technical_block"},
            )

            for error_number in (errno.EACCES, errno.EMFILE, errno.EIO):
                with self.subTest(error_number=error_number):
                    real_open = os.open

                    def failing_open(path, flags, mode=0o777, *, dir_fd=None):
                        if path == agent.MANIFEST_PATH.name and dir_fd is not None:
                            raise OSError(error_number, "mocked operational failure")
                        return real_open(path, flags, mode, dir_fd=dir_fd)

                    with mock.patch.object(os, "open", failing_open):
                        with self.assertRaises(AdapterFailure) as raised:
                            agent.load_adapter_manifest(root)
                    self.assertEqual(
                        {finding.code for finding in raised.exception.findings},
                        {"technical_block"},
                    )

    def test_unrepresentable_plan_target_blocks_all_filesystem_inspection(self):
        with agent_adapter_repository() as root:
            plan = build_adapter_plan(root)
            unsafe = dataclasses.replace(
                plan.outputs[0],
                target=PurePosixPath("AGENTS\ud800.md"),
            )
            forged = dataclasses.replace(plan, outputs=(unsafe, plan.outputs[1]))
            with mock.patch.object(os, "open", side_effect=AssertionError):
                findings = agent.check_agent_adapters(root, forged)

        self.assertEqual({finding.code for finding in findings}, {"invalid_source"})

    def test_target_io_failure_is_a_technical_block(self):
        with agent_adapter_repository() as root:
            plan = self.initialize_parity(root)
            real_open = os.open

            def failing_open(path, flags, mode=0o777, *, dir_fd=None):
                if path == "AGENTS.md" and dir_fd is not None:
                    raise OSError(errno.EIO, "mocked I/O failure")
                return real_open(path, flags, mode, dir_fd=dir_fd)

            with mock.patch.object(os, "open", failing_open):
                findings = agent.check_agent_adapters(root, plan)

        self.assertEqual(
            {(finding.code, finding.path) for finding in findings},
            {("technical_block", PurePosixPath("AGENTS.md"))},
        )


if __name__ == "__main__":
    unittest.main()
