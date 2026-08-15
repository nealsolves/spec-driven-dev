import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path, PurePosixPath

from sdd.adapters.compatibility import ProjectionFailure, build_projection
from tests.projection_helpers import projection_repository


class ProjectionPlanningTest(unittest.TestCase):
    def test_current_tree_maps_exactly_45_outputs_in_source_order(self):
        with projection_repository() as root:
            plan = build_projection(root)

        self.assertEqual(len(plan.entries), 45)
        self.assertEqual(
            [entry.source.as_posix() for entry in plan.entries],
            sorted(entry.source.as_posix() for entry in plan.entries),
        )
        self.assertEqual(plan.entries[0].source, PurePosixPath(".sdd/README.md"))
        self.assertEqual(plan.entries[0].target, PurePosixPath(".claude/README.md"))
        self.assertTrue(
            all(entry.source_sha256 == entry.output_sha256 for entry in plan.entries)
        )

    def test_planning_is_byte_deterministic(self):
        with projection_repository() as root:
            first = build_projection(root)
            second = build_projection(root)

        self.assertEqual(first, second)
        self.assertEqual(first.manifest_bytes, second.manifest_bytes)
        parsed = json.loads(first.manifest_bytes)
        self.assertEqual(parsed["format_version"], 1)
        self.assertEqual(parsed["renderer"], "sdd.adapters.compatibility:v1")
        self.assertTrue(first.manifest_bytes.endswith(b"\n"))

    def test_nested_schema_keeps_its_relative_path(self):
        with projection_repository() as root:
            nested = root / ".sdd/schemas/extensions/example.json"
            nested.parent.mkdir()
            nested.write_text("{}\n", encoding="utf-8")
            plan = build_projection(root)

        entry = next(
            item
            for item in plan.entries
            if item.source == PurePosixPath(".sdd/schemas/extensions/example.json")
        )
        self.assertEqual(
            entry.target, PurePosixPath(".claude/schemas/extensions/example.json")
        )

    def test_unsupported_canonical_file_fails_closed(self):
        with projection_repository() as root:
            (root / ".sdd/modules/rules/security.txt").write_text("wrong suffix\n")
            with self.assertRaises(ProjectionFailure) as raised:
                build_projection(root)

        self.assertIn("invalid_source", {finding.code for finding in raised.exception.findings})

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable")
    def test_source_symlink_fails_before_plan_creation(self):
        with projection_repository() as root:
            source = root / ".sdd/modules/rules/security.md"
            source.unlink()
            source.symlink_to(root / ".sdd/modules/rules/testing.md")
            with self.assertRaises(ProjectionFailure) as raised:
                build_projection(root)

        self.assertIn("unsafe_path", {finding.code for finding in raised.exception.findings})

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable")
    def test_symlinked_schema_directory_fails_closed(self):
        with projection_repository() as root:
            extensions = root / ".sdd/schemas/extensions"
            extensions.symlink_to(root / ".sdd/schemas", target_is_directory=True)
            self.assert_plan_code(root, "unsafe_path")

    def assert_plan_code(self, root: Path, expected_code: str) -> None:
        with self.assertRaises(ProjectionFailure) as raised:
            build_projection(root)
        self.assertIn(expected_code, {item.code for item in raised.exception.findings})
        for finding in raised.exception.findings:
            if finding.path is not None:
                self.assertFalse(finding.path.is_absolute())

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable")
    def test_symlinked_source_parent_fails_closed(self):
        with projection_repository() as root:
            rules = root / ".sdd/modules/rules"
            shutil.rmtree(rules)
            rules.symlink_to(root / ".sdd/modules/profiles", target_is_directory=True)
            self.assert_plan_code(root, "unsafe_path")

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFOs are unavailable")
    def test_special_source_file_fails_closed(self):
        with projection_repository() as root:
            os.mkfifo(root / ".sdd/modules/rules/special.md")
            self.assert_plan_code(root, "unsafe_path")

    def test_unknown_root_artifact_fails_closed(self):
        with projection_repository() as root:
            (root / ".sdd/rogue.md").write_text("rogue\n")
            self.assert_plan_code(root, "invalid_source")

    def test_non_json_schema_fails_closed(self):
        with projection_repository() as root:
            (root / ".sdd/schemas/notes.txt").write_text("not a schema\n")
            self.assert_plan_code(root, "invalid_source")

    def test_nested_module_file_fails_closed(self):
        with projection_repository() as root:
            nested = root / ".sdd/modules/rules/nested/security.md"
            nested.parent.mkdir()
            nested.write_text("# Nested\n")
            self.assert_plan_code(root, "invalid_source")

    def test_case_colliding_sources_fail_closed(self):
        with projection_repository() as root:
            original = root / ".sdd/modules/rules/security.md"
            collision = original.parent / "SECURITY.md"
            collision.write_bytes(original.read_bytes())
            if collision.samefile(original):
                self.skipTest("filesystem collapses case-only names")
            with self.assertRaises(ProjectionFailure) as raised:
                build_projection(root)

        self.assertIn("unsafe_path", {finding.code for finding in raised.exception.findings})

    def test_repository_root_must_be_a_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "not-a-directory"
            root.write_text("file\n")
            self.assert_plan_code(root, "technical_block")
