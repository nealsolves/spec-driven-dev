import dataclasses
import hashlib
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


if __name__ == "__main__":
    unittest.main()
