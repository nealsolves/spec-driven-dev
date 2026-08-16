import copy
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from unittest import mock

from sdd.adapters import compatibility
from sdd.adapters.compatibility import (
    ProjectionFailure,
    build_projection,
    check_projection,
    load_manifest,
    write_projection,
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

    def test_canonical_only_agent_adapter_artifacts_are_not_projected(self):
        with projection_repository() as root:
            (root / ".sdd/adapters").mkdir()
            (root / ".sdd/adapters/root-kernel.md").write_text(
                "## Kernel\n", encoding="utf-8"
            )
            (root / ".sdd/controls/adapters.yaml").write_text(
                "format: 1\n", encoding="utf-8"
            )
            (root / ".sdd/agent-adapters.generated.json").write_text(
                "{}\n", encoding="utf-8"
            )

            plan = build_projection(root)

        self.assertEqual(len(plan.entries), 45)
        self.assertNotIn(
            ".claude/adapters.yaml",
            {entry.target.as_posix() for entry in plan.entries},
        )

    def test_unexpected_file_in_canonical_adapter_directory_fails_closed(self):
        with projection_repository() as root:
            (root / ".sdd/adapters").mkdir()
            (root / ".sdd/adapters/unexpected.md").write_text("x\n")
            with self.assertRaises(ProjectionFailure) as raised:
                build_projection(root)

        self.assertIn("invalid_source", {item.code for item in raised.exception.findings})

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

    def test_desired_output_with_stale_manifest_metadata_is_invalid(self):
        with projection_repository() as root:
            self.initialize_manifest(root)
            source = root / ".sdd/modules/rules/security.md"
            target = root / ".claude/rules/security.md"
            source.write_text("# Revised\n", encoding="utf-8")
            target.write_bytes(source.read_bytes())
            findings = check_projection(root, build_projection(root))

        self.assertEqual({finding.code for finding in findings}, {"invalid_manifest"})
        self.assertEqual(
            {finding.path for finding in findings},
            {PurePosixPath(".sdd/generated-files.json")},
        )

    def test_manifest_mismatch_does_not_hide_independent_output_findings(self):
        with projection_repository() as root:
            self.initialize_manifest(root)
            source = root / ".sdd/modules/rules/security.md"
            target = root / ".claude/rules/security.md"
            source.write_text("# Revised\n", encoding="utf-8")
            target.write_bytes(source.read_bytes())
            (root / ".claude/rules/testing.md").unlink()
            codes = self.finding_codes(root, build_projection(root))

        self.assertEqual(codes, {"invalid_manifest", "missing_output"})

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

    def test_case_colliding_output_directory_is_unsafe(self):
        with projection_repository() as root:
            plan = self.initialize_manifest(root)
            collision = root / ".claude/Rules"
            try:
                collision.mkdir()
            except FileExistsError:
                self.skipTest("filesystem collapses case-only names")
            codes = self.finding_codes(root, plan)
        self.assertIn("unsafe_path", codes)

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

    def test_manifest_paths_reject_nul_and_unrepresentable_unicode(self):
        invalid_components = {
            "nul": "context\x00.schema.json",
            "unpaired_surrogate": "context\ud800.schema.json",
        }
        with projection_repository() as root:
            original = json.loads(build_projection(root).manifest_bytes)
            manifest = root / ".sdd/generated-files.json"
            for name, component in invalid_components.items():
                with self.subTest(name=name):
                    candidate = copy.deepcopy(original)
                    entry = next(
                        item
                        for item in candidate["files"]
                        if item["target"] == ".claude/schemas/context.schema.json"
                    )
                    entry["source"] = f".sdd/schemas/{component}"
                    entry["target"] = f".claude/schemas/{component}"
                    manifest.write_text(
                        json.dumps(candidate, sort_keys=True, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    self.assert_invalid_manifest(root)

    def test_unrepresentable_repository_path_is_a_structured_technical_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repository\ud800"
            with self.assertRaises(ProjectionFailure) as raised:
                load_manifest(root)

        self.assertEqual(
            {finding.code for finding in raised.exception.findings},
            {"technical_block"},
        )


class ProjectionWritingTest(unittest.TestCase):
    def test_write_creates_a_missing_output_tree(self):
        with projection_repository(include_outputs=False) as root:
            plan = build_projection(root)
            write_projection(root, plan)
            self.assertEqual(check_projection(root, plan), ())

    def test_bootstrap_registers_equal_outputs_without_rewriting_them(self):
        with projection_repository() as root:
            output = root / ".claude/rules/security.md"
            before_mtime = output.stat().st_mtime_ns
            plan = build_projection(root)
            write_projection(root, plan)

            self.assertEqual(output.stat().st_mtime_ns, before_mtime)
            self.assertEqual(
                (root / ".sdd/generated-files.json").read_bytes(),
                plan.manifest_bytes,
            )

    def test_canonical_change_updates_only_target_and_manifest(self):
        with projection_repository() as root:
            first = build_projection(root)
            write_projection(root, first)
            before = tree_snapshot(root)
            source = root / ".sdd/modules/rules/security.md"
            source.write_text("# Desired security rule\n", encoding="utf-8")
            desired = build_projection(root)
            write_projection(root, desired)
            after = tree_snapshot(root)

        changed = {path for path in after if after[path] != before.get(path)}
        self.assertEqual(
            changed,
            {
                ".sdd/modules/rules/security.md",
                ".sdd/generated-files.json",
                ".claude/rules/security.md",
            },
        )

    def test_one_conflict_blocks_every_planned_change(self):
        with projection_repository() as root:
            write_projection(root, build_projection(root))
            (root / ".sdd/modules/rules/testing.md").write_text("# Desired\n")
            (root / ".claude/rules/security.md").write_text("# Manual\n")
            before = tree_snapshot(root)
            with self.assertRaises(ProjectionFailure):
                write_projection(root, build_projection(root))
            after = tree_snapshot(root)
        self.assertEqual(after, before)

    def test_owned_removed_output_is_deleted(self):
        with projection_repository() as root:
            write_projection(root, build_projection(root))
            source = root / ".sdd/modules/templates/maintenance-record-template.md"
            target = root / ".claude/templates/maintenance-record-template.md"
            source.unlink()
            write_projection(root, build_projection(root))
        self.assertFalse(target.exists())

    def test_divergent_removed_output_is_preserved_and_blocks(self):
        with projection_repository() as root:
            write_projection(root, build_projection(root))
            (root / ".sdd/modules/rules/security.md").unlink()
            target = root / ".claude/rules/security.md"
            target.write_text("# Manual\n")
            before = tree_snapshot(root)
            with self.assertRaises(ProjectionFailure):
                write_projection(root, build_projection(root))
            after = tree_snapshot(root)
        self.assertEqual(after, before)

    def test_interrupted_replacement_converges_on_rerun(self):
        with projection_repository() as root:
            write_projection(root, build_projection(root))
            (root / ".sdd/modules/rules/security.md").write_text("# Security v2\n")
            (root / ".sdd/modules/rules/testing.md").write_text("# Testing v2\n")
            desired = build_projection(root)
            real_replace = compatibility._replace_file
            replacements = 0

            def interrupt_after_first(*args, **kwargs):
                nonlocal replacements
                real_replace(*args, **kwargs)
                replacements += 1
                if replacements == 1:
                    raise OSError("simulated interruption")

            with mock.patch.object(compatibility, "_replace_file", interrupt_after_first):
                with self.assertRaises(ProjectionFailure):
                    write_projection(root, desired)

            write_projection(root, desired)
            self.assertEqual(check_projection(root, desired), ())

    def test_replaced_created_output_root_blocks_manifest_commit(self):
        with projection_repository(include_outputs=False) as root:
            desired = build_projection(root)
            manifest = root / ".sdd/generated-files.json"
            output_root = root / ".claude"
            real_replace = compatibility._replace_file
            replaced = False

            def replace_created_root_after_direct_outputs(path, payload, executable):
                nonlocal replaced
                real_replace(path, payload, executable)
                if path == root / ".claude/routing.yaml":
                    shutil.rmtree(output_root)
                    output_root.mkdir()
                    replaced = True

            with mock.patch.object(
                compatibility,
                "_replace_file",
                replace_created_root_after_direct_outputs,
            ):
                with self.assertRaises(ProjectionFailure) as raised:
                    write_projection(root, desired)

            self.assertTrue(replaced)
            self.assertFalse(manifest.exists())

        self.assertIn("unsafe_path", {item.code for item in raised.exception.findings})

    def test_final_live_inventory_blocks_manifest_when_output_disappears(self):
        with projection_repository() as root:
            write_projection(root, build_projection(root))
            manifest = root / ".sdd/generated-files.json"
            prior_manifest = manifest.read_bytes()
            source = root / ".sdd/modules/workflows/release.md"
            source.write_text("# Desired release workflow\n", encoding="utf-8")
            desired = build_projection(root)
            removed = root / ".claude/README.md"
            real_replace = compatibility._replace_file

            def remove_output_after_last_replacement(path, payload, executable):
                real_replace(path, payload, executable)
                if path == root / ".claude/workflows/release.md":
                    removed.unlink()

            with mock.patch.object(
                compatibility,
                "_replace_file",
                remove_output_after_last_replacement,
            ):
                with self.assertRaises(ProjectionFailure) as raised:
                    write_projection(root, desired)

            self.assertFalse(removed.exists())
            self.assertEqual(manifest.read_bytes(), prior_manifest)

        self.assertIn("missing_output", {item.code for item in raised.exception.findings})

    def test_manifest_change_during_final_inventory_is_preserved_and_blocks_commit(self):
        with projection_repository() as root:
            write_projection(root, build_projection(root))
            manifest = root / ".sdd/generated-files.json"
            external_manifest = b'{"external": true}\n'
            source = root / ".sdd/modules/workflows/release.md"
            source.write_text("# Desired release workflow\n", encoding="utf-8")
            desired = build_projection(root)
            real_verify = compatibility._verify_live_outputs

            def change_manifest_after_final_inventory(*args, **kwargs):
                findings = real_verify(*args, **kwargs)
                manifest.write_bytes(external_manifest)
                return findings

            with mock.patch.object(
                compatibility,
                "_verify_live_outputs",
                change_manifest_after_final_inventory,
            ):
                with self.assertRaises(ProjectionFailure) as raised:
                    write_projection(root, desired)

            self.assertEqual(manifest.read_bytes(), external_manifest)

        self.assertIn("invalid_manifest", {item.code for item in raised.exception.findings})

    def test_replaced_created_output_root_after_final_inventory_blocks_manifest_commit(self):
        with projection_repository(include_outputs=False) as root:
            desired = build_projection(root)
            manifest = root / ".sdd/generated-files.json"
            output_root = root / ".claude"
            real_verify = compatibility._verify_live_outputs
            replaced = False

            def replace_created_root_after_final_inventory(*args, **kwargs):
                nonlocal replaced
                findings = real_verify(*args, **kwargs)
                shutil.rmtree(output_root)
                output_root.mkdir()
                replaced = True
                return findings

            with mock.patch.object(
                compatibility,
                "_verify_live_outputs",
                replace_created_root_after_final_inventory,
            ):
                with self.assertRaises(ProjectionFailure) as raised:
                    write_projection(root, desired)

            self.assertTrue(replaced)
            self.assertFalse(manifest.exists())

        self.assertIn("unsafe_path", {item.code for item in raised.exception.findings})

    def test_target_edit_during_staged_payload_read_blocks_replacement(self):
        with projection_repository() as root:
            write_projection(root, build_projection(root))
            source = root / ".sdd/modules/rules/security.md"
            target = root / ".claude/rules/security.md"
            manifest = root / ".sdd/generated-files.json"
            prior_manifest = manifest.read_bytes()
            source.write_text("# Desired\n", encoding="utf-8")
            desired = build_projection(root)
            real_read_bytes = Path.read_bytes
            staged_reads = 0

            def edit_target_during_payload_read(path):
                nonlocal staged_reads
                if path != target and path.as_posix().endswith(
                    "/.claude/rules/security.md"
                ):
                    staged_reads += 1
                    if staged_reads == 2:
                        target.write_text("# Manual\n", encoding="utf-8")
                return real_read_bytes(path)

            with mock.patch.object(Path, "read_bytes", edit_target_during_payload_read):
                with self.assertRaises(ProjectionFailure) as raised:
                    write_projection(root, desired)

            self.assertEqual(target.read_text(encoding="utf-8"), "# Manual\n")
            self.assertEqual(manifest.read_bytes(), prior_manifest)
        self.assertIn(
            "conflicting_output", {item.code for item in raised.exception.findings}
        )

    def test_unmanaged_extra_output_is_preserved_and_blocks(self):
        with projection_repository() as root:
            write_projection(root, build_projection(root))
            extra = root / ".claude/rules/extra.md"
            extra.write_text("# Extra\n")
            before = tree_snapshot(root)
            with self.assertRaises(ProjectionFailure):
                write_projection(root, build_projection(root))
            after = tree_snapshot(root)
        self.assertEqual(after, before)

    def test_unmanaged_equal_target_is_registered_during_bootstrap(self):
        with projection_repository() as root:
            plan = build_projection(root)
            self.assertFalse((root / ".sdd/generated-files.json").exists())
            write_projection(root, plan)
            self.assertEqual(check_projection(root, plan), ())

    def test_invalid_staged_policy_bundle_changes_nothing(self):
        with projection_repository() as root:
            write_projection(root, build_projection(root))
            (root / ".sdd/controls/project.yaml").write_text("project: [\n")
            before = tree_snapshot(root)
            with self.assertRaises(ProjectionFailure) as raised:
                write_projection(root, build_projection(root))
            after = tree_snapshot(root)
        self.assertEqual(after, before)
        self.assertIn("invalid_source", {item.code for item in raised.exception.findings})

    def test_malformed_staged_validator_contract_changes_nothing(self):
        with projection_repository() as root:
            before = tree_snapshot(root)
            completed = mock.Mock(returncode=0, stdout="{}\n", stderr="")
            with mock.patch.object(compatibility.subprocess, "run", return_value=completed):
                with self.assertRaises(ProjectionFailure) as raised:
                    write_projection(root, build_projection(root))
            after = tree_snapshot(root)
        self.assertEqual(after, before)
        self.assertIn("technical_block", {item.code for item in raised.exception.findings})

    def test_undecodable_staged_validator_stdout_is_technical_block(self):
        with projection_repository() as root:
            before = tree_snapshot(root)
            decoding_failure = UnicodeDecodeError(
                "utf-8", b"\xff", 0, 1, "invalid start byte"
            )
            with mock.patch.object(
                compatibility.subprocess, "run", side_effect=decoding_failure
            ):
                with self.assertRaises(ProjectionFailure) as raised:
                    write_projection(root, build_projection(root))
            after = tree_snapshot(root)
        self.assertEqual(after, before)
        self.assertIn("technical_block", {item.code for item in raised.exception.findings})

    def test_nonzero_staged_validator_success_json_is_technical_block(self):
        with projection_repository() as root:
            before = tree_snapshot(root)
            completed = mock.Mock(
                returncode=3,
                stdout='{"valid": true, "errors": []}\n',
                stderr="",
            )
            with mock.patch.object(compatibility.subprocess, "run", return_value=completed):
                with self.assertRaises(ProjectionFailure) as raised:
                    write_projection(root, build_projection(root))
            after = tree_snapshot(root)
        self.assertEqual(after, before)
        self.assertIn("technical_block", {item.code for item in raised.exception.findings})

    def test_already_deleted_removed_target_converges(self):
        with projection_repository() as root:
            write_projection(root, build_projection(root))
            (root / ".sdd/modules/templates/maintenance-record-template.md").unlink()
            (root / ".claude/templates/maintenance-record-template.md").unlink()
            desired = build_projection(root)
            write_projection(root, desired)
            self.assertEqual(check_projection(root, desired), ())

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable")
    def test_target_parent_symlink_blocks_without_mutation(self):
        with projection_repository() as root:
            write_projection(root, build_projection(root))
            rules = root / ".claude/rules"
            shutil.rmtree(rules)
            rules.symlink_to(root / ".claude/profiles", target_is_directory=True)
            before = tree_snapshot(root)
            with self.assertRaises(ProjectionFailure) as raised:
                write_projection(root, build_projection(root))
            after = tree_snapshot(root)
        self.assertEqual(after, before)
        self.assertIn("unsafe_path", {item.code for item in raised.exception.findings})

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable")
    def test_source_parent_symlink_after_planning_is_unsafe(self):
        with projection_repository() as root:
            plan = build_projection(root)
            rules = root / ".sdd/modules/rules"
            shutil.rmtree(rules)
            rules.symlink_to(root / ".sdd/modules/profiles", target_is_directory=True)
            before = tree_snapshot(root)
            with self.assertRaises(ProjectionFailure) as raised:
                write_projection(root, plan)
            after = tree_snapshot(root)
        self.assertEqual(after, before)
        self.assertIn("unsafe_path", {item.code for item in raised.exception.findings})

    def test_repeated_write_is_byte_and_mtime_idempotent(self):
        with projection_repository() as root:
            plan = build_projection(root)
            write_projection(root, plan)
            before = {
                path: path.stat().st_mtime_ns
                for path in (root / ".claude").rglob("*")
                if path.is_file()
            }
            manifest_mtime = (root / ".sdd/generated-files.json").stat().st_mtime_ns
            write_projection(root, plan)
            after = {path: path.stat().st_mtime_ns for path in before}
            self.assertEqual(after, before)
            self.assertEqual(
                (root / ".sdd/generated-files.json").stat().st_mtime_ns,
                manifest_mtime,
            )

    def test_manifest_replacement_is_last(self):
        with projection_repository() as root:
            write_projection(root, build_projection(root))
            (root / ".sdd/modules/rules/security.md").write_text("# Desired\n")
            calls = []
            real_replace = compatibility._replace_file

            def record(path, payload, executable):
                calls.append(path.relative_to(root).as_posix())
                return real_replace(path, payload, executable)

            with mock.patch.object(compatibility, "_replace_file", record):
                write_projection(root, build_projection(root))

        self.assertEqual(calls[-1], ".sdd/generated-files.json")
