import dataclasses
import errno
import hashlib
import json
import os
import re
import stat
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

    def test_repository_root_path_shape_is_unsafe_but_resource_failure_is_technical(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "not-a-directory"
            root.write_text("file\n", encoding="utf-8")
            self.assert_plan_code(root, "unsafe_path")

            missing = Path(directory) / "missing"
            self.assert_plan_code(missing, "unsafe_path")

        with agent_adapter_repository() as root:
            real_lstat = Path.lstat

            def fail_root_inspection(path):
                if path == root:
                    raise OSError(errno.EIO, "simulated root I/O failure")
                return real_lstat(path)

            with mock.patch.object(Path, "lstat", fail_root_inspection):
                self.assert_plan_code(root, "technical_block")

        if hasattr(os, "symlink"):
            with agent_adapter_repository() as root:
                displaced = root.with_name("real-repository")
                root.rename(displaced)
                root.symlink_to(displaced, target_is_directory=True)
                self.assert_plan_code(root, "unsafe_path")


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
            shared_body = (b"x" * 16213) + b"\n"
            outputs = tuple(
                dataclasses.replace(
                    output,
                    payload=output.preamble + shared_body,
                    sha256=hashlib.sha256(output.preamble + shared_body).hexdigest(),
                    byte_count=len(output.preamble + shared_body),
                    line_count=(output.preamble + shared_body).count(b"\n"),
                )
                for output in plan.outputs
            )
            forged = dataclasses.replace(
                plan,
                kernel_sha256=hashlib.sha256(shared_body).hexdigest(),
                outputs=outputs,
            )
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
                ("invalid_source", agent.KERNEL_PATH),
                ("invalid_manifest", agent.MANIFEST_PATH),
                ("unsafe_path", PurePosixPath("AGENTS.md")),
                ("conflicting_output", PurePosixPath("CLAUDE.md")),
                ("limit_exceeded", PurePosixPath("CLAUDE.md")),
            },
        )
        self.assertEqual(
            {(finding.code, finding.path) for finding in raised.exception.findings},
            {("limit_exceeded", PurePosixPath("CLAUDE.md"))},
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

    def test_forged_plan_names_preambles_bodies_and_kernel_digest_are_rejected(self):
        with agent_adapter_repository() as root:
            plan = build_adapter_plan(root)
            agents, claude = plan.outputs
            shared_body = agents.payload[len(agents.preamble) :]

            forged_preamble = b"<!-- forged preamble -->\n\n"
            forged_preamble_payload = forged_preamble + shared_body
            wrong_preamble = dataclasses.replace(
                agents,
                preamble=forged_preamble,
                payload=forged_preamble_payload,
                sha256=hashlib.sha256(forged_preamble_payload).hexdigest(),
                byte_count=len(forged_preamble_payload),
                line_count=forged_preamble_payload.count(b"\n"),
            )

            divergent_body = shared_body.replace(b"Canonical", b"Divergent", 1)
            divergent_payload = agents.preamble + divergent_body
            wrong_body = dataclasses.replace(
                agents,
                payload=divergent_payload,
                sha256=hashlib.sha256(divergent_payload).hexdigest(),
                byte_count=len(divergent_payload),
                line_count=divergent_payload.count(b"\n"),
            )

            for label, forged in (
                (
                    "name-to-target mapping",
                    dataclasses.replace(
                        plan,
                        outputs=(dataclasses.replace(agents, name="claude"), claude),
                    ),
                ),
                (
                    "fixed preamble",
                    dataclasses.replace(plan, outputs=(wrong_preamble, claude)),
                ),
                (
                    "identical shared body",
                    dataclasses.replace(plan, outputs=(wrong_body, claude)),
                ),
                (
                    "kernel body digest",
                    dataclasses.replace(plan, kernel_sha256="0" * 64),
                ),
            ):
                with self.subTest(label=label):
                    before = tree_snapshot(root)
                    with self.assertRaises(AdapterFailure) as serialized:
                        agent.serialize_adapter_manifest(forged)
                    findings = agent.check_agent_adapters(root, forged)
                    with self.assertRaises(AdapterFailure) as written:
                        agent.write_agent_adapters(root, forged)

                    self.assertEqual(
                        {finding.code for finding in serialized.exception.findings},
                        {"invalid_source"},
                    )
                    self.assertIn("invalid_source", {finding.code for finding in findings})
                    self.assertEqual(
                        {finding.code for finding in written.exception.findings},
                        {"invalid_source"},
                    )
                    self.assertEqual(tree_snapshot(root), before)

    def test_check_and_write_reject_plan_stale_against_live_fixed_sources(self):
        mutations = (
            (
                agent.CONTROL_PATH,
                lambda payload: b"# digest-changing comment\n" + payload,
            ),
            (
                agent.KERNEL_PATH,
                lambda payload: payload.replace(b"Canonical", b"Changed", 1),
            ),
        )
        for relative, mutate in mutations:
            with self.subTest(path=relative), agent_adapter_repository() as root:
                stale = build_adapter_plan(root)
                source = root / relative
                source.write_bytes(mutate(source.read_bytes()))
                before = tree_snapshot(root)

                findings = agent.check_agent_adapters(root, stale)
                with self.assertRaises(AdapterFailure) as raised:
                    agent.write_agent_adapters(root, stale)

                self.assertIn(
                    ("invalid_source", relative),
                    {(finding.code, finding.path) for finding in findings},
                )
                self.assertIn(
                    ("invalid_source", relative),
                    {
                        (finding.code, finding.path)
                        for finding in raised.exception.findings
                    },
                )
                self.assertEqual(tree_snapshot(root), before)

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


class AdapterWritingTest(unittest.TestCase):
    def initialize_owned(self, root: Path):
        plan = build_adapter_plan(root)
        for output in plan.outputs:
            target = root / output.target
            target.write_bytes(output.payload)
            target.chmod(0o644)
        (root / agent.MANIFEST_PATH).write_bytes(agent.serialize_adapter_manifest(plan))
        return plan

    def assert_failure_code(self, raised, expected: str) -> None:
        self.assertIn(expected, {finding.code for finding in raised.exception.findings})

    def test_new_repository_creates_two_outputs_and_manifest(self):
        with agent_adapter_repository() as root:
            plan = build_adapter_plan(root)

            agent.write_agent_adapters(root, plan)

            for output in plan.outputs:
                target = root / output.target
                self.assertEqual(target.read_bytes(), output.payload)
                self.assertEqual(target.stat().st_mode & 0o777, 0o644)
            manifest = root / agent.MANIFEST_PATH
            self.assertEqual(manifest.read_bytes(), agent.serialize_adapter_manifest(plan))
            self.assertEqual(manifest.stat().st_mode & 0o777, 0o644)
            self.assertEqual(agent.check_agent_adapters(root, plan), ())

    def test_repeated_write_is_byte_and_mtime_idempotent(self):
        with agent_adapter_repository() as root:
            plan = build_adapter_plan(root)
            agent.write_agent_adapters(root, plan)
            paths = [root / output.target for output in plan.outputs]
            paths.append(root / agent.MANIFEST_PATH)
            before = {
                path: (path.read_bytes(), path.stat().st_mtime_ns)
                for path in paths
            }

            agent.write_agent_adapters(root, plan)

            after = {
                path: (path.read_bytes(), path.stat().st_mtime_ns)
                for path in paths
            }
            self.assertEqual(after, before)

    def test_unmanaged_divergent_root_file_is_preserved_and_blocks(self):
        with agent_adapter_repository() as root:
            plan = build_adapter_plan(root)
            conflict = root / "AGENTS.md"
            conflict.write_text("unmanaged instructions\n", encoding="utf-8")
            before = tree_snapshot(root)

            with self.assertRaises(AdapterFailure) as raised:
                agent.write_agent_adapters(root, plan)

            self.assertEqual(tree_snapshot(root), before)
            self.assertEqual(conflict.read_bytes(), b"unmanaged instructions\n")
            self.assertFalse((root / agent.MANIFEST_PATH).exists())
        self.assert_failure_code(raised, "conflicting_output")

    def test_prior_owned_output_can_converge_to_desired(self):
        with agent_adapter_repository() as root:
            prior = self.initialize_owned(root)
            (root / agent.KERNEL_PATH).write_text(
                "## Purpose and Scope\n\nChanged canonical policy.\n",
                encoding="utf-8",
            )
            desired = build_adapter_plan(root)

            agent.write_agent_adapters(root, desired)

            self.assertNotEqual(prior.kernel_sha256, desired.kernel_sha256)
            for output in desired.outputs:
                target = root / output.target
                self.assertEqual(target.read_bytes(), output.payload)
                self.assertEqual(target.stat().st_mode & 0o777, 0o644)
            self.assertEqual(agent.check_agent_adapters(root, desired), ())

    def test_missing_owned_output_is_recreated(self):
        with agent_adapter_repository() as root:
            plan = self.initialize_owned(root)
            missing = root / "AGENTS.md"
            missing.unlink()
            manifest = root / agent.MANIFEST_PATH
            manifest_before = (manifest.read_bytes(), manifest.stat().st_mtime_ns)

            agent.write_agent_adapters(root, plan)

            self.assertEqual(missing.read_bytes(), plan.outputs[0].payload)
            self.assertEqual(missing.stat().st_mode & 0o777, 0o644)
            self.assertEqual(
                (manifest.read_bytes(), manifest.stat().st_mtime_ns),
                manifest_before,
            )
            self.assertEqual(agent.check_agent_adapters(root, plan), ())

    def test_target_change_after_preflight_blocks_replacement(self):
        with agent_adapter_repository() as root:
            self.initialize_owned(root)
            (root / agent.KERNEL_PATH).write_text(
                "## Purpose and Scope\n\nChanged canonical policy.\n",
                encoding="utf-8",
            )
            desired = build_adapter_plan(root)
            before = tree_snapshot(root)
            prior_manifest = (root / agent.MANIFEST_PATH).read_bytes()
            external = b"concurrent unmanaged edit\n"
            real_read = agent._read_regular_file_state
            target_reads = 0

            def change_target_on_boundary(repository, relative, **kwargs):
                nonlocal target_reads
                if relative == PurePosixPath("AGENTS.md"):
                    target_reads += 1
                    if target_reads == 2:
                        (root / relative).write_bytes(external)
                return real_read(repository, relative, **kwargs)

            with mock.patch.object(
                agent, "_read_regular_file_state", change_target_on_boundary
            ):
                with self.assertRaises(AdapterFailure) as raised:
                    agent.write_agent_adapters(root, desired)

            after = tree_snapshot(root)
            expected = dict(before)
            expected["AGENTS.md"] = (external, 0)
            self.assertEqual(after, expected)
            self.assertEqual((root / "AGENTS.md").read_bytes(), external)
            self.assertEqual((root / agent.MANIFEST_PATH).read_bytes(), prior_manifest)
        self.assertEqual(target_reads, 2)
        self.assert_failure_code(raised, "conflicting_output")

    def test_target_change_during_temp_preparation_is_preserved(self):
        with agent_adapter_repository() as root:
            self.initialize_owned(root)
            (root / agent.KERNEL_PATH).write_text(
                "## Purpose and Scope\n\nChanged canonical policy.\n",
                encoding="utf-8",
            )
            desired = build_adapter_plan(root)
            before = tree_snapshot(root)
            manifest = root / agent.MANIFEST_PATH
            prior_manifest = manifest.read_bytes()
            target = root / "AGENTS.md"
            external = b"edit during output temp preparation\n"
            real_fsync = os.fsync
            mutated = False

            def mutate_target_during_fsync(file_descriptor):
                nonlocal mutated
                if not mutated:
                    target.write_bytes(external)
                    mutated = True
                return real_fsync(file_descriptor)

            with mock.patch.object(os, "fsync", mutate_target_during_fsync):
                with self.assertRaises(AdapterFailure) as raised:
                    agent.write_agent_adapters(root, desired)

            expected = dict(before)
            expected["AGENTS.md"] = (external, 0)
            self.assertEqual(tree_snapshot(root), expected)
            self.assertEqual(target.read_bytes(), external)
            self.assertEqual(manifest.read_bytes(), prior_manifest)
        self.assertTrue(mutated)
        self.assert_failure_code(raised, "conflicting_output")

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable")
    def test_manifest_change_after_preflight_is_preserved(self):
        with self.subTest(case="unsafe at preflight"), agent_adapter_repository() as root:
            self.initialize_owned(root)
            manifest = root / agent.MANIFEST_PATH
            alternate = manifest.with_name("prior-agent-adapters.json")
            manifest.rename(alternate)
            manifest.symlink_to(alternate.name)
            before = tree_snapshot(root)

            with self.assertRaises(AdapterFailure) as unsafe_raised:
                agent.write_agent_adapters(root, build_adapter_plan(root))

            self.assertEqual(tree_snapshot(root), before)
            self.assertTrue(manifest.is_symlink())
            self.assertEqual(manifest.read_bytes(), alternate.read_bytes())
        self.assert_failure_code(unsafe_raised, "invalid_manifest")

        with self.subTest(case="changed after preflight"), agent_adapter_repository() as root:
            self.initialize_owned(root)
            (root / agent.KERNEL_PATH).write_text(
                "## Purpose and Scope\n\nChanged canonical policy.\n",
                encoding="utf-8",
            )
            desired = build_adapter_plan(root)
            before = tree_snapshot(root)
            manifest = root / agent.MANIFEST_PATH
            external = b'{"external":true}\n'
            real_read = agent._read_regular_file_state
            manifest_reads = 0

            def change_manifest_on_boundary(repository, relative, **kwargs):
                nonlocal manifest_reads
                if relative == agent.MANIFEST_PATH:
                    manifest_reads += 1
                    if manifest_reads == 2:
                        manifest.write_bytes(external)
                return real_read(repository, relative, **kwargs)

            with mock.patch.object(
                agent, "_read_regular_file_state", change_manifest_on_boundary
            ):
                with self.assertRaises(AdapterFailure) as changed_raised:
                    agent.write_agent_adapters(root, desired)

            after = tree_snapshot(root)
            expected = dict(before)
            for output in desired.outputs:
                expected[output.target.as_posix()] = (output.payload, 0)
            expected[agent.MANIFEST_PATH.as_posix()] = (external, 0)
            self.assertEqual(after, expected)
            self.assertEqual(manifest.read_bytes(), external)
        self.assertGreaterEqual(manifest_reads, 2)
        self.assert_failure_code(changed_raised, "invalid_manifest")

    def test_manifest_change_during_temp_preparation_is_preserved(self):
        with agent_adapter_repository() as root:
            plan = build_adapter_plan(root)
            for output in plan.outputs:
                target = root / output.target
                target.write_bytes(output.payload)
                target.chmod(0o644)
            before = tree_snapshot(root)
            manifest = root / agent.MANIFEST_PATH
            external = b'{"external":"during preparation"}\n'
            real_fchmod = os.fchmod
            mutated = False

            def mutate_manifest_during_fchmod(file_descriptor, mode):
                nonlocal mutated
                if not mutated:
                    manifest.write_bytes(external)
                    mutated = True
                return real_fchmod(file_descriptor, mode)

            with mock.patch.object(os, "fchmod", mutate_manifest_during_fchmod):
                with self.assertRaises(AdapterFailure) as raised:
                    agent.write_agent_adapters(root, plan)

            expected = dict(before)
            expected[agent.MANIFEST_PATH.as_posix()] = (external, 0)
            self.assertEqual(tree_snapshot(root), expected)
            self.assertEqual(manifest.read_bytes(), external)
        self.assertTrue(mutated)
        self.assert_failure_code(raised, "invalid_manifest")

    def test_manifest_deletion_or_change_before_owned_replacement_preserves_output(self):
        for case in ("deleted", "changed"):
            with self.subTest(case=case), agent_adapter_repository() as root:
                prior = self.initialize_owned(root)
                (root / agent.KERNEL_PATH).write_text(
                    "## Purpose and Scope\n\nChanged canonical policy.\n",
                    encoding="utf-8",
                )
                desired = build_adapter_plan(root)
                manifest = root / agent.MANIFEST_PATH
                external = b'{"external":"ownership changed"}\n'
                prior_outputs = {
                    output.target: (root / output.target).read_bytes()
                    for output in prior.outputs
                }
                real_prepare = agent._prepare_adapter_file
                mutated = False

                def mutate_manifest_before_preparation(*args, **kwargs):
                    nonlocal mutated
                    if not mutated:
                        if case == "deleted":
                            manifest.unlink()
                        else:
                            manifest.write_bytes(external)
                        mutated = True
                    return real_prepare(*args, **kwargs)

                with mock.patch.object(
                    agent,
                    "_prepare_adapter_file",
                    mutate_manifest_before_preparation,
                ):
                    with self.assertRaises(AdapterFailure) as raised:
                        agent.write_agent_adapters(root, desired)

                for target, payload in prior_outputs.items():
                    self.assertEqual((root / target).read_bytes(), payload)
                if case == "deleted":
                    self.assertFalse(manifest.exists())
                else:
                    self.assertEqual(manifest.read_bytes(), external)
                self.assertEqual(list(root.glob(".AGENTS.md.*")), [])
                self.assertEqual(list(root.glob(".CLAUDE.md.*")), [])
                self.assertTrue(mutated)
                self.assert_failure_code(raised, "invalid_manifest")

    def test_output_drift_during_manifest_preparation_blocks_manifest_commit(self):
        with agent_adapter_repository() as root:
            plan = build_adapter_plan(root)
            for output in plan.outputs:
                target = root / output.target
                target.write_bytes(output.payload)
                target.chmod(0o644)
            before = tree_snapshot(root)
            target = root / "AGENTS.md"
            external = b"edit during manifest preparation\n"
            real_fchmod = os.fchmod
            mutated = False

            def mutate_output_during_fchmod(file_descriptor, mode):
                nonlocal mutated
                if not mutated:
                    target.write_bytes(external)
                    mutated = True
                return real_fchmod(file_descriptor, mode)

            with mock.patch.object(os, "fchmod", mutate_output_during_fchmod):
                with self.assertRaises(AdapterFailure) as raised:
                    agent.write_agent_adapters(root, plan)

            expected = dict(before)
            expected["AGENTS.md"] = (external, 0)
            self.assertEqual(tree_snapshot(root), expected)
            self.assertEqual(target.read_bytes(), external)
            self.assertFalse((root / agent.MANIFEST_PATH).exists())
        self.assertTrue(mutated)
        self.assert_failure_code(raised, "conflicting_output")

    def test_live_source_change_at_manifest_commit_boundary_blocks_stale_manifest(self):
        with agent_adapter_repository() as root:
            plan = build_adapter_plan(root)
            kernel = root / agent.KERNEL_PATH
            before = tree_snapshot(root)
            changed_kernel = b"## Purpose and Scope\n\nChanged before manifest commit.\n"
            real_read_manifest_state = agent._read_manifest_state_at
            mutated = False

            def mutate_source_before_manifest_commit(sdd_fd, **kwargs):
                nonlocal mutated
                if not mutated:
                    kernel.write_bytes(changed_kernel)
                    mutated = True
                return real_read_manifest_state(sdd_fd, **kwargs)

            with mock.patch.object(
                agent,
                "_read_manifest_state_at",
                mutate_source_before_manifest_commit,
            ):
                with self.assertRaises(AdapterFailure) as raised:
                    agent.write_agent_adapters(root, plan)

            expected = dict(before)
            expected[agent.KERNEL_PATH.as_posix()] = (changed_kernel, 0)
            for output in plan.outputs:
                expected[output.target.as_posix()] = (output.payload, 0)
            self.assertEqual(tree_snapshot(root), expected)
            self.assertFalse((root / agent.MANIFEST_PATH).exists())
        self.assertTrue(mutated)
        self.assert_failure_code(raised, "invalid_source")

    def test_output_or_manifest_change_during_live_source_recheck_blocks_manifest_commit(self):
        for boundary in ("output", "manifest"):
            with self.subTest(boundary=boundary), agent_adapter_repository() as root:
                plan = build_adapter_plan(root)
                for output in plan.outputs:
                    target = root / output.target
                    target.write_bytes(output.payload)
                    target.chmod(0o644)
                before = tree_snapshot(root)
                external = f"external {boundary} change\n".encode("utf-8")
                real_require_live_plan = agent._require_live_plan
                rechecks = 0

                def mutate_during_commit_source_recheck(repository, supplied):
                    nonlocal rechecks
                    real_require_live_plan(repository, supplied)
                    rechecks += 1
                    if rechecks == 2:
                        target = (
                            root / "AGENTS.md"
                            if boundary == "output"
                            else root / agent.MANIFEST_PATH
                        )
                        target.write_bytes(external)

                with mock.patch.object(
                    agent,
                    "_require_live_plan",
                    mutate_during_commit_source_recheck,
                ):
                    with self.assertRaises(AdapterFailure) as raised:
                        agent.write_agent_adapters(root, plan)

                expected = dict(before)
                changed_path = (
                    "AGENTS.md"
                    if boundary == "output"
                    else agent.MANIFEST_PATH.as_posix()
                )
                expected[changed_path] = (external, 0)
                self.assertEqual(tree_snapshot(root), expected)
                self.assertEqual(rechecks, 2)
                self.assert_failure_code(
                    raised,
                    "conflicting_output" if boundary == "output" else "invalid_manifest",
                )

    def test_cleanup_preserves_replacement_entry_at_prepared_temp_name(self):
        with agent_adapter_repository() as root:
            plan = build_adapter_plan(root)
            foreign = b"foreign replacement entry\n"
            replaced_name: str | None = None

            def replace_temp_then_fail(source, destination, **kwargs):
                nonlocal replaced_name
                source_directory = kwargs.get("src_dir_fd")
                if source_directory is None:
                    source_path = Path(source)
                    replaced_name = source_path.name
                    source_path.unlink()
                    source_path.write_bytes(foreign)
                else:
                    replaced_name = os.fsdecode(source)
                    os.unlink(source, dir_fd=source_directory)
                    descriptor = os.open(
                        source,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                        0o644,
                        dir_fd=source_directory,
                    )
                    try:
                        os.write(descriptor, foreign)
                    finally:
                        os.close(descriptor)
                raise OSError(errno.EIO, "simulated replace failure")

            with mock.patch.object(os, "replace", replace_temp_then_fail):
                with self.assertRaises(AdapterFailure) as raised:
                    agent.write_agent_adapters(root, plan)

            self.assertIsNotNone(replaced_name)
            replacement = root / str(replaced_name)
            self.assertEqual(replacement.read_bytes(), foreign)
            self.assertFalse((root / "AGENTS.md").exists())
            self.assertFalse((root / agent.MANIFEST_PATH).exists())
        self.assert_failure_code(raised, "technical_block")

    def test_preparation_failure_removes_owned_unused_temp(self):
        with agent_adapter_repository() as root:
            plan = build_adapter_plan(root)
            before = tree_snapshot(root)

            with mock.patch.object(
                os,
                "fsync",
                side_effect=OSError(errno.EIO, "simulated temp durability failure"),
            ):
                with self.assertRaises(AdapterFailure) as raised:
                    agent.write_agent_adapters(root, plan)

            self.assertEqual(tree_snapshot(root), before)
            self.assertEqual(list(root.glob(".AGENTS.md.*")), [])
            self.assertFalse((root / agent.MANIFEST_PATH).exists())
        self.assert_failure_code(raised, "technical_block")

    def test_temp_close_error_is_not_retried_and_owned_path_is_cleaned(self):
        with agent_adapter_repository() as root:
            identity = agent._capture_directory_identity(root, None)
            real_close = os.close
            close_calls: list[int] = []
            failed_descriptor: int | None = None

            def fail_first_regular_close(file_descriptor):
                nonlocal failed_descriptor
                close_calls.append(file_descriptor)
                info = os.fstat(file_descriptor)
                if failed_descriptor is None and stat.S_ISREG(info.st_mode):
                    failed_descriptor = file_descriptor
                    raise OSError(errno.EIO, "simulated uncertain close failure")
                return real_close(file_descriptor)

            try:
                with mock.patch.object(os, "close", fail_first_regular_close):
                    with self.assertRaises(OSError):
                        agent._prepare_adapter_file(
                            root / "AGENTS.md",
                            b"prepared payload\n",
                            identity,
                            None,
                        )
            finally:
                if failed_descriptor is not None:
                    try:
                        real_close(failed_descriptor)
                    except OSError:
                        pass

            self.assertIsNotNone(failed_descriptor)
            self.assertEqual(close_calls.count(failed_descriptor), 1)
            self.assertEqual(list(root.glob(".AGENTS.md.*")), [])
            self.assertFalse((root / "AGENTS.md").exists())

    def test_repository_path_replacement_before_temp_creation_creates_no_foreign_artifact(self):
        with agent_adapter_repository() as root:
            plan = build_adapter_plan(root)
            before = tree_snapshot(root)
            displaced = root.with_name("pinned-repository")
            real_open_pinned = agent._open_pinned_directory
            replaced = False

            def replace_repository_after_pin(path, expected, relative):
                nonlocal replaced
                directory_fd = real_open_pinned(path, expected, relative)
                if relative is None and not replaced:
                    root.rename(displaced)
                    root.mkdir()
                    replaced = True
                return directory_fd

            with mock.patch.object(
                agent,
                "_open_pinned_directory",
                replace_repository_after_pin,
            ):
                with self.assertRaises(AdapterFailure) as raised:
                    agent.write_agent_adapters(root, plan)

            self.assertTrue(replaced)
            self.assertEqual(tree_snapshot(displaced), before)
            self.assertEqual(list(root.glob(".AGENTS.md.*")), [])
            self.assertEqual(list(root.glob(".CLAUDE.md.*")), [])
            self.assertFalse((displaced / "AGENTS.md").exists())
            self.assertFalse((displaced / "CLAUDE.md").exists())
            self.assertFalse((displaced / agent.MANIFEST_PATH).exists())
        self.assert_failure_code(raised, "unsafe_path")

    def test_interruption_after_first_output_converges_on_rerun(self):
        with agent_adapter_repository() as root:
            plan = build_adapter_plan(root)
            real_commit = agent._commit_prepared_file
            replacements = 0

            def interrupt_after_first(prepared, destination_name):
                nonlocal replacements
                real_commit(prepared, destination_name)
                replacements += 1
                if replacements == 1:
                    raise OSError(errno.EIO, "simulated interruption")

            with mock.patch.object(
                agent, "_commit_prepared_file", interrupt_after_first
            ):
                with self.assertRaises(AdapterFailure) as raised:
                    agent.write_agent_adapters(root, plan)

            self.assertEqual((root / "AGENTS.md").read_bytes(), plan.outputs[0].payload)
            self.assertFalse((root / "CLAUDE.md").exists())
            self.assertFalse((root / agent.MANIFEST_PATH).exists())

            agent.write_agent_adapters(root, plan)
            self.assertEqual(agent.check_agent_adapters(root, plan), ())
        self.assertEqual(replacements, 1)
        self.assert_failure_code(raised, "technical_block")

    def test_directory_sync_failures_preserve_manifest_last_and_rerun_converges(self):
        for boundary in ("repository", ".sdd"):
            with self.subTest(boundary=boundary), agent_adapter_repository() as root:
                plan = build_adapter_plan(root)
                boundary_path = root if boundary == "repository" else root / ".sdd"
                boundary_info = boundary_path.stat()
                real_fsync = os.fsync
                failed = False

                def fail_boundary_sync(file_descriptor):
                    nonlocal failed
                    info = os.fstat(file_descriptor)
                    if (
                        not failed
                        and stat.S_ISDIR(info.st_mode)
                        and info.st_dev == boundary_info.st_dev
                        and info.st_ino == boundary_info.st_ino
                    ):
                        failed = True
                        raise OSError(errno.EIO, "simulated directory sync failure")
                    return real_fsync(file_descriptor)

                with mock.patch.object(os, "fsync", fail_boundary_sync):
                    with self.assertRaises(AdapterFailure) as raised:
                        agent.write_agent_adapters(root, plan)

                self.assertTrue(failed)
                self.assert_failure_code(raised, "technical_block")
                if boundary == "repository":
                    self.assertEqual(
                        (root / "AGENTS.md").read_bytes(),
                        plan.outputs[0].payload,
                    )
                    self.assertFalse((root / "CLAUDE.md").exists())
                    self.assertFalse((root / agent.MANIFEST_PATH).exists())
                else:
                    for output in plan.outputs:
                        self.assertEqual((root / output.target).read_bytes(), output.payload)
                    self.assertEqual(
                        (root / agent.MANIFEST_PATH).read_bytes(),
                        agent.serialize_adapter_manifest(plan),
                    )
                self.assertEqual(list(root.glob(".AGENTS.md.*")), [])
                self.assertEqual(list(root.glob(".CLAUDE.md.*")), [])
                self.assertEqual(list((root / ".sdd").glob(".agent-adapters.generated.json.*")), [])

                agent.write_agent_adapters(root, plan)
                self.assertEqual(agent.check_agent_adapters(root, plan), ())

    def test_retry_after_final_root_sync_failure_reestablishes_both_barriers(self):
        with agent_adapter_repository() as root:
            plan = build_adapter_plan(root)
            root_info = root.stat()
            sdd_info = (root / ".sdd").stat()
            real_fsync = os.fsync
            root_syncs = 0

            def fail_last_root_sync(file_descriptor):
                nonlocal root_syncs
                info = os.fstat(file_descriptor)
                if (
                    stat.S_ISDIR(info.st_mode)
                    and info.st_dev == root_info.st_dev
                    and info.st_ino == root_info.st_ino
                ):
                    root_syncs += 1
                    if root_syncs == 3:
                        raise OSError(errno.EIO, "simulated final root sync failure")
                return real_fsync(file_descriptor)

            with mock.patch.object(os, "fsync", fail_last_root_sync):
                with self.assertRaises(AdapterFailure) as raised:
                    agent.write_agent_adapters(root, plan)

            self.assertEqual(root_syncs, 3)
            self.assert_failure_code(raised, "technical_block")
            for output in plan.outputs:
                self.assertEqual((root / output.target).read_bytes(), output.payload)
            self.assertFalse((root / agent.MANIFEST_PATH).exists())

            barriers: list[str] = []

            def record_retry_barriers(file_descriptor):
                info = os.fstat(file_descriptor)
                if stat.S_ISDIR(info.st_mode):
                    if (
                        info.st_dev == root_info.st_dev
                        and info.st_ino == root_info.st_ino
                    ):
                        barriers.append("repository")
                    elif (
                        info.st_dev == sdd_info.st_dev
                        and info.st_ino == sdd_info.st_ino
                    ):
                        barriers.append(".sdd")
                return real_fsync(file_descriptor)

            with mock.patch.object(os, "fsync", record_retry_barriers):
                agent.write_agent_adapters(root, plan)

            self.assertEqual(barriers, ["repository", ".sdd"])
            self.assertEqual(agent.check_agent_adapters(root, plan), ())

    def test_retry_after_sdd_sync_failure_reestablishes_both_barriers(self):
        with agent_adapter_repository() as root:
            plan = build_adapter_plan(root)
            root_info = root.stat()
            sdd_info = (root / ".sdd").stat()
            real_fsync = os.fsync
            failed = False

            def fail_sdd_sync(file_descriptor):
                nonlocal failed
                info = os.fstat(file_descriptor)
                if (
                    not failed
                    and stat.S_ISDIR(info.st_mode)
                    and info.st_dev == sdd_info.st_dev
                    and info.st_ino == sdd_info.st_ino
                ):
                    failed = True
                    raise OSError(errno.EIO, "simulated .sdd sync failure")
                return real_fsync(file_descriptor)

            with mock.patch.object(os, "fsync", fail_sdd_sync):
                with self.assertRaises(AdapterFailure) as raised:
                    agent.write_agent_adapters(root, plan)

            self.assertTrue(failed)
            self.assert_failure_code(raised, "technical_block")
            self.assertEqual(
                (root / agent.MANIFEST_PATH).read_bytes(),
                agent.serialize_adapter_manifest(plan),
            )

            barriers: list[str] = []

            def record_retry_barriers(file_descriptor):
                info = os.fstat(file_descriptor)
                if stat.S_ISDIR(info.st_mode):
                    if (
                        info.st_dev == root_info.st_dev
                        and info.st_ino == root_info.st_ino
                    ):
                        barriers.append("repository")
                    elif (
                        info.st_dev == sdd_info.st_dev
                        and info.st_ino == sdd_info.st_ino
                    ):
                        barriers.append(".sdd")
                return real_fsync(file_descriptor)

            with mock.patch.object(os, "fsync", record_retry_barriers):
                agent.write_agent_adapters(root, plan)

            self.assertEqual(barriers, ["repository", ".sdd"])
            self.assertEqual(agent.check_agent_adapters(root, plan), ())

    def test_final_output_verification_blocks_manifest_commit(self):
        with agent_adapter_repository() as root:
            plan = build_adapter_plan(root)
            before = tree_snapshot(root)
            external = b"edit during final verification\n"
            real_read = agent._read_regular_file_state
            target_reads = 0

            def change_output_during_verification(repository, relative, **kwargs):
                nonlocal target_reads
                if relative == PurePosixPath("AGENTS.md"):
                    target_reads += 1
                    if target_reads == 3:
                        (root / relative).write_bytes(external)
                return real_read(repository, relative, **kwargs)

            with mock.patch.object(
                agent, "_read_regular_file_state", change_output_during_verification
            ):
                with self.assertRaises(AdapterFailure) as raised:
                    agent.write_agent_adapters(root, plan)

            after = tree_snapshot(root)
            expected = dict(before)
            expected["AGENTS.md"] = (external, 0)
            expected["CLAUDE.md"] = (plan.outputs[1].payload, 0)
            self.assertEqual(after, expected)
            self.assertEqual((root / "AGENTS.md").read_bytes(), external)
            self.assertFalse((root / agent.MANIFEST_PATH).exists())
        self.assertEqual(target_reads, 3)
        self.assert_failure_code(raised, "conflicting_output")

    def test_replaced_repository_or_sdd_directory_blocks(self):
        for boundary in ("repository", ".sdd"):
            with self.subTest(boundary=boundary), agent_adapter_repository() as root:
                plan = build_adapter_plan(root)
                before = tree_snapshot(root)
                displaced = (
                    root.with_name("displaced-repository")
                    if boundary == "repository"
                    else root / ".sdd-displaced"
                )
                real_commit = agent._commit_prepared_file
                replacements = 0

                def replace_boundary_after_first(prepared, destination_name):
                    nonlocal replacements
                    real_commit(prepared, destination_name)
                    replacements += 1
                    if replacements != 1:
                        return
                    if boundary == "repository":
                        root.rename(displaced)
                        root.mkdir()
                    else:
                        (root / ".sdd").rename(displaced)
                        (root / ".sdd").mkdir()

                with mock.patch.object(
                    agent, "_commit_prepared_file", replace_boundary_after_first
                ):
                    with self.assertRaises(AdapterFailure) as raised:
                        agent.write_agent_adapters(root, plan)

                preserved_root = displaced if boundary == "repository" else root
                preserved = tree_snapshot(preserved_root)
                expected = dict(before)
                expected["AGENTS.md"] = (plan.outputs[0].payload, 0)
                if boundary == ".sdd":
                    expected = {
                        (
                            path.replace(".sdd/", ".sdd-displaced/", 1)
                            if path.startswith(".sdd/")
                            else path
                        ): value
                        for path, value in expected.items()
                    }
                self.assertEqual(preserved, expected)
                self.assertFalse((root / agent.MANIFEST_PATH).exists())
                self.assertEqual(replacements, 1)
                self.assert_failure_code(raised, "unsafe_path")

    def test_parent_resource_failure_is_technical_and_non_mutating(self):
        with agent_adapter_repository() as root:
            plan = build_adapter_plan(root)
            before = tree_snapshot(root)
            real_lstat = Path.lstat
            root_inspections = 0

            def fail_identity_inspection(path):
                nonlocal root_inspections
                if path == root:
                    root_inspections += 1
                    if root_inspections == 2:
                        raise OSError(errno.EIO, "simulated parent I/O failure")
                return real_lstat(path)

            with mock.patch.object(Path, "lstat", fail_identity_inspection):
                with self.assertRaises(AdapterFailure) as raised:
                    agent.write_agent_adapters(root, plan)

            self.assertEqual(tree_snapshot(root), before)
            self.assertFalse((root / agent.MANIFEST_PATH).exists())
        self.assertEqual(root_inspections, 2)
        self.assertEqual(
            {finding.code for finding in raised.exception.findings},
            {"technical_block"},
        )


if __name__ == "__main__":
    unittest.main()
