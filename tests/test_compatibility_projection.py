import copy
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path, PurePosixPath

from sdd.adapters.compatibility import (
    ProjectionFailure,
    build_projection,
    check_projection,
    load_manifest,
)
from tests.projection_helpers import projection_repository, tree_snapshot


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


class ProjectionCheckingTest(unittest.TestCase):
    def initialize_manifest(self, root: Path):
        plan = build_projection(root)
        (root / ".sdd/generated-files.json").write_bytes(plan.manifest_bytes)
        return plan

    def finding_codes(self, root: Path, plan):
        return {finding.code for finding in check_projection(root, plan)}

    def test_matching_manifest_and_outputs_have_no_findings(self):
        with projection_repository() as root:
            plan = self.initialize_manifest(root)
            findings = check_projection(root, plan)
        self.assertEqual(findings, ())

    def test_old_owned_output_after_canonical_change_is_stale(self):
        with projection_repository() as root:
            self.initialize_manifest(root)
            (root / ".sdd/modules/rules/security.md").write_text("# Revised\n")
            plan = build_projection(root)
            codes = self.finding_codes(root, plan)
        self.assertIn("stale_output", codes)

    def test_third_state_output_is_conflicting(self):
        with projection_repository() as root:
            self.initialize_manifest(root)
            (root / ".sdd/modules/rules/security.md").write_text("# Desired\n")
            (root / ".claude/rules/security.md").write_text("# Manual\n")
            plan = build_projection(root)
            codes = self.finding_codes(root, plan)
        self.assertIn("conflicting_output", codes)

    def test_missing_expected_output_is_reported(self):
        with projection_repository() as root:
            plan = self.initialize_manifest(root)
            (root / ".claude/rules/security.md").unlink()
            codes = self.finding_codes(root, plan)
        self.assertIn("missing_output", codes)

    def test_unmanaged_extra_output_is_reported(self):
        with projection_repository() as root:
            plan = self.initialize_manifest(root)
            (root / ".claude/rules/extra.md").write_text("# Extra\n")
            codes = self.finding_codes(root, plan)
        self.assertIn("unexpected_output", codes)

    def test_removed_canonical_source_is_extra_managed(self):
        with projection_repository() as root:
            self.initialize_manifest(root)
            (root / ".sdd/modules/rules/security.md").unlink()
            plan = build_projection(root)
            codes = self.finding_codes(root, plan)
        self.assertIn("extra_managed_output", codes)

    def test_check_does_not_mutate_files(self):
        with projection_repository() as root:
            plan = self.initialize_manifest(root)
            before = tree_snapshot(root)
            check_projection(root, plan)
            after = tree_snapshot(root)
        self.assertEqual(after, before)

    def assert_invalid_manifest(self, root: Path) -> None:
        with self.assertRaises(ProjectionFailure) as raised:
            load_manifest(root)
        self.assertIn("invalid_manifest", {item.code for item in raised.exception.findings})

    def test_invalid_json_and_non_object_manifest_fail_closed(self):
        with projection_repository() as root:
            manifest = root / ".sdd/generated-files.json"
            for payload in (b"{", b"[]\n"):
                with self.subTest(payload=payload):
                    manifest.write_bytes(payload)
                    self.assert_invalid_manifest(root)

    def test_manifest_field_and_path_variants_fail_closed(self):
        def mutate_missing_key(value):
            value.pop("renderer")

        def mutate_unknown_key(value):
            value["host"] = "local"

        def mutate_version(value):
            value["format_version"] = 2

        def mutate_renderer(value):
            value["renderer"] = "other:v1"

        def mutate_executable(value):
            value["files"][0]["executable"] = 0

        def mutate_digest(value):
            value["files"][0]["output_sha256"] = "ABC"

        def mutate_absolute_source(value):
            value["files"][0]["source"] = "/tmp/source"

        def mutate_traversing_target(value):
            value["files"][0]["target"] = ".claude/../outside.md"

        def mutate_unknown_entry_key(value):
            value["files"][0]["mtime"] = 1

        def mutate_duplicate_target(value):
            duplicate = copy.deepcopy(value["files"][0])
            duplicate["source"] = ".sdd/modules/rules/duplicate.md"
            value["files"].append(duplicate)

        def mutate_case_collision(value):
            duplicate = copy.deepcopy(value["files"][0])
            duplicate["source"] = ".sdd/modules/rules/duplicate.md"
            duplicate["target"] = value["files"][0]["target"].upper()
            value["files"].append(duplicate)

        def mutate_outside_source(value):
            value["files"][0]["source"] = ".sdd/migrations/source.md"

        def mutate_outside_target(value):
            value["files"][0]["target"] = ".other/output.md"

        def mutate_order(value):
            value["files"].reverse()

        mutations = (
            mutate_missing_key,
            mutate_unknown_key,
            mutate_version,
            mutate_renderer,
            mutate_executable,
            mutate_digest,
            mutate_absolute_source,
            mutate_traversing_target,
            mutate_unknown_entry_key,
            mutate_duplicate_target,
            mutate_case_collision,
            mutate_outside_source,
            mutate_outside_target,
            mutate_order,
        )
        with projection_repository() as root:
            original = json.loads(build_projection(root).manifest_bytes)
            manifest = root / ".sdd/generated-files.json"
            for mutation in mutations:
                with self.subTest(mutation=mutation.__name__):
                    candidate = copy.deepcopy(original)
                    mutation(candidate)
                    manifest.write_text(
                        json.dumps(candidate, sort_keys=True, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    self.assert_invalid_manifest(root)

    def test_noncanonical_json_bytes_fail_closed(self):
        with projection_repository() as root:
            payload = json.loads(build_projection(root).manifest_bytes)
            (root / ".sdd/generated-files.json").write_text(
                json.dumps(payload, separators=(",", ":")), encoding="utf-8"
            )
            self.assert_invalid_manifest(root)
