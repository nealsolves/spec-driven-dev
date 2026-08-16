# Canonical `.sdd` Compatibility Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `.sdd/` the authoritative source for all 45 instruction
artifacts while safely maintaining the tracked `.claude/` compatibility tree.

**Architecture:** A focused `sdd.adapters.compatibility` module discovers an
allowlisted canonical tree, builds a deterministic manifest, checks parity,
and applies fully preflighted writes. A thin transitional script exposes check
and write modes; the existing policy engine continues to read `.claude/`, and
the primary validator rejects projection drift before invoking that engine.

**Tech Stack:** Python 3.11+, standard library dataclasses/pathlib/hashlib/json/
tempfile/subprocess, Bash, `unittest`, the existing PyYAML 6.x and jsonschema
4.x policy runtime.

**Spec:** `docs/design/2026-08-15-sdd-compatibility-projection.md`

## Global Constraints

- Migrate the complete current 45-file `.claude/` tree in one authority
  transition; do not create split authority.
- Preserve every current file byte-for-byte and preserve executable state
  during bootstrap.
- Keep `scripts/policy-engine.py` reading `.claude/` in this phase.
- Treat `.claude/` as tracked generated output after migration.
- Never overwrite or delete an unexpectedly modified generated file.
- Validate the complete candidate projection before changing managed outputs.
- Keep projection generation deterministic, offline, and based only on local
  repository content.
- Reject symlinks, special files, path traversal, duplicate targets, and
  case-colliding paths before mutation.
- Serialize manifests as sorted-key, two-space-indented UTF-8 JSON with one
  trailing newline and no volatile values.
- Check exits are `0` for parity, `1` for expected findings, `2` for invalid
  invocation, and `3` for a technical inability to inspect safely.
- Root `CLAUDE.md`, root `AGENTS.md`, the public `sdd` CLI, and semantic adapter
  conformance are outside this slice.
- Use TDD for every behavioral change and commit after each reviewable task.
- After implementation, perform an independent review, fix all critical and
  important findings, rerun the full verification matrix, push, and open a PR.

## File Structure

- `src/sdd/adapters/__init__.py` — package boundary for adapter-owned tooling.
- `src/sdd/adapters/compatibility.py` — projection types, discovery, manifest
  parsing/serialization, parity findings, staged validation, and safe writes.
- `scripts/render-compatibility.py` — thin `--check` / `--write` transitional
  command that loads `src/` without requiring an editable install.
- `tests/projection_helpers.py` — isolated repository builders and filesystem
  snapshots shared only by projection tests.
- `tests/test_compatibility_projection.py` — unit contracts for planning,
  checking, conflict handling, writes, and recovery.
- `tests/test_compatibility_cli.py` — subprocess-level CLI and exit-code tests.
- `tests/test_canonical_projection.py` — repository-level 45-file parity,
  migration provenance, and deterministic-manifest tests.
- `.sdd/README.md`, `.sdd/controls/`, `.sdd/schemas/`, and
  `.sdd/modules/` — canonical copies of the current instruction artifacts.
- `.sdd/generated-files.json` — generated ownership and digest manifest.
- `.sdd/migrations/0001-claude-to-sdd.json` — immutable bootstrap provenance.
- `scripts/validate-instructions.sh` — run projection check after the runtime
  probe and before the unchanged legacy engine.
- `tests/helpers.py` and `tests/test_validator_cli.py` — copy both authority and
  compatibility trees into isolated legacy-engine and validator fixtures.
- `README.md`, `.sdd/README.md`, and `implementation_status.md` — state the
  canonical authority, generated boundary, commands, and P0 legacy behavior.
- `.gitignore` — reserve ignored `.sdd/state/` runtime state.

---

### Task 1: Deterministic Projection Planning

**Files:**

- Create: `src/sdd/adapters/__init__.py`
- Create: `src/sdd/adapters/compatibility.py`
- Create: `tests/projection_helpers.py`
- Create: `tests/test_compatibility_projection.py`

**Interfaces:**

- Consumes: canonical files below an absolute repository `Path`.
- Produces: `Finding`, `ProjectionEntry`, `ProjectionPlan`,
  `ProjectionFailure`, and `build_projection(root: Path) -> ProjectionPlan`.

- [ ] **Step 1: Add a reusable isolated projection fixture**

Create `tests/projection_helpers.py` with an explicit legacy-to-canonical copy;
the helper must not call production mapping code:

```python
import hashlib
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

from tests.helpers import ROOT


CONTROL_NAMES = ("project.yaml", "routing.yaml", "policy.yaml", "lifecycle.yaml")
MODULE_NAMESPACES = ("rules", "workflows", "profiles", "templates")


def copy_legacy_as_canonical(destination: Path) -> None:
    canonical = destination / ".sdd"
    (canonical / "controls").mkdir(parents=True)
    shutil.copy2(ROOT / ".claude/README.md", canonical / "README.md")
    for name in CONTROL_NAMES:
        shutil.copy2(ROOT / ".claude" / name, canonical / "controls" / name)
    shutil.copytree(ROOT / ".claude/schemas", canonical / "schemas")
    for namespace in MODULE_NAMESPACES:
        shutil.copytree(
            ROOT / ".claude" / namespace,
            canonical / "modules" / namespace,
        )


@contextmanager
def projection_repository(*, include_outputs: bool = True):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "repository"
        root.mkdir()
        copy_legacy_as_canonical(root)
        if include_outputs:
            shutil.copytree(ROOT / ".claude", root / ".claude")
        (root / "scripts").mkdir()
        shutil.copy2(ROOT / "scripts/policy-engine.py", root / "scripts/policy-engine.py")
        yield root


def tree_snapshot(root: Path) -> dict[str, tuple[bytes, int]]:
    return {
        path.relative_to(root).as_posix(): (
            path.read_bytes(),
            path.stat().st_mode & 0o111,
        )
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
```

- [ ] **Step 2: Write failing planning tests**

Create `ProjectionPlanningTest` in `tests/test_compatibility_projection.py`:

```python
import copy
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
        self.assertTrue(all(entry.source_sha256 == entry.output_sha256 for entry in plan.entries))

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

        entry = next(item for item in plan.entries if item.source == PurePosixPath(".sdd/schemas/extensions/example.json"))
        self.assertEqual(entry.target, PurePosixPath(".claude/schemas/extensions/example.json"))

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
```

Add these safety cases to the same class:

```python
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

    def test_repository_root_must_be_a_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "not-a-directory"
            root.write_text("file\n")
            self.assert_plan_code(root, "technical_block")
```

- [ ] **Step 3: Run the focused tests and confirm the missing API failure**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m unittest \
  tests.test_compatibility_projection.ProjectionPlanningTest -v
```

Expected: FAIL because `sdd.adapters.compatibility` does not exist.

- [ ] **Step 4: Implement immutable types, allowlisted discovery, and manifest serialization**

Create `src/sdd/adapters/__init__.py` with only a package docstring. In
`compatibility.py`, define these public types and constants exactly:

```python
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

FORMAT_VERSION = 1
RENDERER = "sdd.adapters.compatibility:v1"
MANIFEST_PATH = PurePosixPath(".sdd/generated-files.json")
CONTROL_NAMES = ("project.yaml", "routing.yaml", "policy.yaml", "lifecycle.yaml")
MODULE_NAMESPACES = ("rules", "workflows", "profiles", "templates")


@dataclass(frozen=True)
class Finding:
    code: str
    path: PurePosixPath | None
    message: str


@dataclass(frozen=True)
class ProjectionEntry:
    source: PurePosixPath
    target: PurePosixPath
    source_sha256: str
    output_sha256: str
    executable: bool


@dataclass(frozen=True)
class ProjectionPlan:
    format_version: int
    renderer: str
    entries: tuple[ProjectionEntry, ...]
    manifest_bytes: bytes


class ProjectionFailure(Exception):
    def __init__(self, findings: tuple[Finding, ...]):
        super().__init__("compatibility projection failed")
        self.findings = findings


def build_projection(root: Path) -> ProjectionPlan:
    repository = _validated_repository_root(root)
    entries = _discover_projection_entries(repository)
    return _projection_plan(entries)
```

Define `_validated_repository_root`, `_discover_projection_entries`, and
`_projection_plan` in the same module; they are the only private functions
called by this public entry point.

Implement `build_projection` with these exact mapping rules:

```text
.sdd/README.md                       -> .claude/README.md
.sdd/controls/{four exact names}    -> .claude/{same name}
.sdd/schemas/**/*.json              -> .claude/schemas/{same relative path}
.sdd/modules/{namespace}/*.md       -> .claude/{namespace}/{same name}
```

Use `lstat()` while walking every source and parent; reject symlinks and any
non-regular file. Modules are one level deep, schemas may be recursive. Reject
all artifacts outside the allowlist except `.sdd/generated-files.json`,
`.sdd/migrations/`, and absent/ignored `.sdd/state/`. Reject duplicate or
case-folded-colliding source and target paths. Compute SHA-256 over raw bytes,
set `executable = bool(mode & 0o111)`, sort by source POSIX path, and serialize:

```python
payload = {
    "format_version": FORMAT_VERSION,
    "renderer": RENDERER,
    "files": [
        {
            "source": entry.source.as_posix(),
            "target": entry.target.as_posix(),
            "source_sha256": entry.source_sha256,
            "output_sha256": entry.output_sha256,
            "executable": entry.executable,
        }
        for entry in entries
    ],
}
manifest_bytes = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("utf-8")
```

Convert all expected source errors to sorted `Finding` objects. Convert
`OSError`/`RuntimeError` inspection failures to `technical_block`; do not expose
a traceback through the public API.

- [ ] **Step 5: Run planning tests**

Run the focused command from Step 3.

Expected: all `ProjectionPlanningTest` tests PASS.

- [ ] **Step 6: Commit deterministic planning**

```bash
git add src/sdd/adapters/__init__.py src/sdd/adapters/compatibility.py \
  tests/projection_helpers.py tests/test_compatibility_projection.py
git commit -m "feat: plan deterministic compatibility projections"
```

---

### Task 2: Manifest Loading and Read-Only Parity Checking

**Files:**

- Modify: `src/sdd/adapters/compatibility.py`
- Modify: `tests/test_compatibility_projection.py`

**Interfaces:**

- Consumes: `ProjectionPlan` from Task 1 and the tracked
  `.sdd/generated-files.json`.
- Produces: `load_manifest(root: Path) -> ProjectionPlan` and
  `check_projection(root: Path, plan: ProjectionPlan) -> tuple[Finding, ...]`.

- [ ] **Step 1: Write failing manifest and checking tests**

Add `ProjectionCheckingTest`:

```python
from sdd.adapters.compatibility import check_projection, load_manifest


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
```

Add strict schema and canonical-form tests:

```python
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
```

- [ ] **Step 2: Run checking tests and confirm the missing API failure**

```bash
PYTHONPATH=src ../../.venv/bin/python -m unittest \
  tests.test_compatibility_projection.ProjectionCheckingTest -v
```

Expected: FAIL because `load_manifest` and `check_projection` are absent.

- [ ] **Step 3: Implement strict manifest loading**

`load_manifest` must decode UTF-8, parse JSON, require exactly
`format_version`, `renderer`, and `files`, validate every entry field and type,
rebuild the canonical serialized bytes, and reject a tracked manifest whose
bytes are not already in canonical form. Reuse the same source/target
allowlists and collision checks as planning. A missing manifest is
`invalid_manifest` in check mode; write mode handles the bootstrap case in
Task 3.

- [ ] **Step 4: Implement deterministic read-only checking**

Implement `check_projection` using this state table:

```text
expected + prior + target == desired                    -> no finding
expected + prior + target == prior, desired changed     -> stale_output
expected + prior + target matches neither               -> conflicting_output
expected + no prior + target == desired                 -> invalid_manifest ownership gap
expected + target missing                               -> missing_output
no expected + prior                                     -> extra_managed_output
no expected + no prior + compatibility artifact exists -> unexpected_output
```

Compare both byte digest and executable boolean. Enumerate all files, symlinks,
and special entries below `.claude/`; reject symlinked parents and unsafe paths.
Sort findings by `(path or "", code, message)` before returning them.

- [ ] **Step 5: Run planning and checking tests**

```bash
PYTHONPATH=src ../../.venv/bin/python -m unittest \
  tests.test_compatibility_projection.ProjectionPlanningTest \
  tests.test_compatibility_projection.ProjectionCheckingTest -v
```

Expected: PASS.

- [ ] **Step 6: Commit parity checking**

```bash
git add src/sdd/adapters/compatibility.py tests/test_compatibility_projection.py
git commit -m "feat: check compatibility projection parity"
```

---

### Task 3: Conflict-Safe Writes, Staged Validation, and Recovery

**Files:**

- Modify: `src/sdd/adapters/compatibility.py`
- Modify: `tests/test_compatibility_projection.py`

**Interfaces:**

- Consumes: `ProjectionPlan`, an optional prior manifest, and the repository's
  existing `scripts/policy-engine.py`.
- Produces: `write_projection(root: Path, plan: ProjectionPlan) -> None`.
  Success converges targets and writes the manifest last; failure raises
  `ProjectionFailure` and preserves all unproven states.

- [ ] **Step 1: Write failing write and recovery tests**

Add `ProjectionWritingTest` with these exact core cases:

```python
from unittest import mock

from sdd.adapters import compatibility
from sdd.adapters.compatibility import write_projection
from tests.projection_helpers import tree_snapshot


class ProjectionWritingTest(unittest.TestCase):
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
            source = root / ".sdd/modules/rules/security.md"
            target = root / ".claude/rules/security.md"
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
```

Add the remaining preflight, validation, and ordering cases:

```python
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

    def test_already_deleted_removed_target_converges(self):
        with projection_repository() as root:
            write_projection(root, build_projection(root))
            (root / ".sdd/modules/rules/security.md").unlink()
            (root / ".claude/rules/security.md").unlink()
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
```

- [ ] **Step 2: Run write tests and confirm failure**

```bash
PYTHONPATH=src ../../.venv/bin/python -m unittest \
  tests.test_compatibility_projection.ProjectionWritingTest -v
```

Expected: FAIL because `write_projection` is absent.

- [ ] **Step 3: Implement full preflight and staged validation**

Implement these private helpers: `_load_optional_manifest(root)` returns
`None` only when the manifest path is absent and otherwise delegates to
`load_manifest`; `_preflight_write(root, prior, desired)` returns every sorted
ownership or safety finding; `_stage_projection(root, desired)` returns the
temporary staging root; `_validate_staged_bundle(root, staging_root)` returns
sorted findings; `_replace_file(path, payload, executable)` performs one atomic
replacement; and `_remove_owned_file(path)` removes one already-proven target.

Preflight accepts an existing expected target only when it matches either the
prior manifest state or the desired state. With no prior manifest, every
existing expected target must already match desired. Removed prior targets may
be deleted only when they match prior; an already-missing removed target is an
accepted interrupted state. Any unexpected output, unsafe entry, invalid
manifest, or third-state digest blocks all mutation.

Materialize every desired output under `TemporaryDirectory()` as a complete
`staging_root/.claude` tree with mode `0o755` when executable and `0o644`
otherwise. Verify staged digests and modes, then execute:

```python
subprocess.run(
    [
        sys.executable,
        str(root / "scripts/policy-engine.py"),
        "validate",
        "--root",
        str(staging_root),
    ],
    check=False,
    capture_output=True,
    text=True,
    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
)
```

Require exit `0` and a single JSON object containing `valid: true` and an empty
`errors` list. Convert policy validation failure to `invalid_source` and
execution/JSON failures to `technical_block`.

- [ ] **Step 4: Implement atomic application and recovery**

`_replace_file` must create a same-directory temporary file, write and flush
bytes, `os.fsync()`, set the canonical mode, call `os.replace()`, and remove
the temporary name in `finally`. Record each target parent's resolved path,
device, and inode during preflight; immediately before mutation, re-check that
identity and re-check the target's accepted prior-or-desired state. Abort on a
changed parent or third-state target. `write_projection` applies replacements
in target path order, performs safe removals after all staging validation, and
replaces `.sdd/generated-files.json` last. Catch filesystem errors, preserve
the prior manifest, and raise a sorted `technical_block` finding. A rerun must
accept targets already at desired state and complete remaining work.

- [ ] **Step 5: Run all projection unit tests**

```bash
PYTHONPATH=src ../../.venv/bin/python -m unittest \
  tests.test_compatibility_projection -v
```

Expected: PASS.

- [ ] **Step 6: Commit safe writing**

```bash
git add src/sdd/adapters/compatibility.py tests/test_compatibility_projection.py
git commit -m "feat: write compatibility projections safely"
```

---

### Task 4: Transitional Projection CLI

**Files:**

- Create: `scripts/render-compatibility.py`
- Create: `tests/test_compatibility_cli.py`
- Modify: `tests/projection_helpers.py`

**Interfaces:**

- Consumes: public functions from `sdd.adapters.compatibility`.
- Produces: `python scripts/render-compatibility.py --root PATH --check` and
  `--write`, with stable exit codes and no package-install requirement.

- [ ] **Step 1: Write failing subprocess tests**

Create `tests/test_compatibility_cli.py`:

```python
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
```

Add these CLI state and exit-code tests:

```python
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
```

- [ ] **Step 2: Run CLI tests and confirm the missing-script failure**

```bash
PYTHONPATH=src ../../.venv/bin/python -m unittest \
  tests.test_compatibility_cli -v
```

Expected: FAIL because `scripts/render-compatibility.py` does not exist.

- [ ] **Step 3: Implement the thin CLI**

The script must set `sys.dont_write_bytecode = True`, prepend repository
`src/` to `sys.path`, require one mutually exclusive mode, and use this flow:

```python
def main(argv: list[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    try:
        root = arguments.root.resolve(strict=True)
        plan = build_projection(root)
        if arguments.check:
            findings = check_projection(root, plan)
            if findings:
                render_findings(findings)
                return 3 if any(item.code == "technical_block" for item in findings) else 1
            print("OK: compatibility projection is current")
            return 0
        write_projection(root, plan)
        print("OK: compatibility projection updated")
        return 0
    except ProjectionFailure as exc:
        render_findings(exc.findings)
        return 3 if any(item.code == "technical_block" for item in exc.findings) else 1
    except (OSError, RuntimeError) as exc:
        print(f"ERROR: technical_block: {exc}")
        return 3
```

Render findings as `ERROR: CODE: PATH: MESSAGE`, using `-` when `path is None`.
Do not catch `SystemExit` from `argparse`, so usage failures remain exit `2`.
Mark the script executable.

- [ ] **Step 4: Run CLI and projection tests**

```bash
PYTHONPATH=src ../../.venv/bin/python -m unittest \
  tests.test_compatibility_projection tests.test_compatibility_cli -v
```

Expected: PASS.

- [ ] **Step 5: Commit the CLI**

```bash
git add scripts/render-compatibility.py tests/projection_helpers.py \
  tests/test_compatibility_cli.py
git commit -m "feat: expose compatibility projection commands"
```

---

### Task 5: Canonical Authority Bootstrap and Provenance

**Files:**

- Create: `.sdd/README.md`
- Create: `.sdd/controls/{project,routing,policy,lifecycle}.yaml`
- Create: `.sdd/schemas/*.json`
- Create: `.sdd/modules/{rules,workflows,profiles,templates}/*.md`
- Create: `.sdd/generated-files.json`
- Create: `.sdd/migrations/0001-claude-to-sdd.json`
- Create: `tests/test_canonical_projection.py`
- Modify: `.gitignore:1-10`

**Interfaces:**

- Consumes: the pre-migration `.claude/` tree at baseline commit
  `43839f372501de7453beef9e3df7f35f03f9b251`.
- Produces: 45 canonical source files, their initial ownership manifest, and
  immutable migration provenance.

- [ ] **Step 1: Write failing repository-level canonical tests**

Create `tests/test_canonical_projection.py`:

```python
import json
import unittest
from pathlib import Path

from sdd.adapters.compatibility import build_projection, check_projection, load_manifest


ROOT = Path(__file__).resolve().parents[1]


class CanonicalProjectionTest(unittest.TestCase):
    def test_repository_has_exact_45_file_projection(self):
        plan = build_projection(ROOT)
        self.assertEqual(len(plan.entries), 45)
        self.assertEqual(check_projection(ROOT, plan), ())
        self.assertEqual(load_manifest(ROOT), plan)

    def test_every_output_matches_its_canonical_source_and_executable_state(self):
        plan = build_projection(ROOT)
        for entry in plan.entries:
            source = ROOT / entry.source
            target = ROOT / entry.target
            with self.subTest(target=entry.target.as_posix()):
                self.assertEqual(target.read_bytes(), source.read_bytes())
                self.assertEqual(bool(target.stat().st_mode & 0o111), entry.executable)

    def test_migration_record_is_stable_and_machine_independent(self):
        record = json.loads(
            (ROOT / ".sdd/migrations/0001-claude-to-sdd.json").read_text("utf-8")
        )
        self.assertEqual(record["migration_id"], "0001-claude-to-sdd")
        self.assertEqual(
            record["baseline_commit"],
            "43839f372501de7453beef9e3df7f35f03f9b251",
        )
        self.assertEqual(
            record["manifest_sha256"],
            "2d4be624cc96d4852a4ba23fcf4f652cf61e1083ae97a73358d795f81e77e851",
        )
        self.assertNotIn("timestamp", record)
        self.assertNotIn(str(ROOT), json.dumps(record))
```

- [ ] **Step 2: Run the repository-level test and confirm missing `.sdd` failure**

```bash
PYTHONPATH=src ../../.venv/bin/python -m unittest tests.test_canonical_projection -v
```

Expected: FAIL because `.sdd/` does not exist.

- [ ] **Step 3: Copy the legacy tree into the canonical layout mechanically**

```bash
mkdir -p .sdd/controls .sdd/schemas .sdd/modules/rules \
  .sdd/modules/workflows .sdd/modules/profiles .sdd/modules/templates \
  .sdd/migrations
cp -p .claude/README.md .sdd/README.md
cp -p .claude/project.yaml .claude/routing.yaml .claude/policy.yaml \
  .claude/lifecycle.yaml .sdd/controls/
cp -p .claude/schemas/*.json .sdd/schemas/
cp -p .claude/rules/*.md .sdd/modules/rules/
cp -p .claude/workflows/*.md .sdd/modules/workflows/
cp -p .claude/profiles/*.md .sdd/modules/profiles/
cp -p .claude/templates/*.md .sdd/modules/templates/
```

Verify bootstrap bytes before manifest creation:

```bash
cmp .claude/README.md .sdd/README.md
diff -q .claude/project.yaml .sdd/controls/project.yaml
diff -q .claude/routing.yaml .sdd/controls/routing.yaml
diff -q .claude/policy.yaml .sdd/controls/policy.yaml
diff -q .claude/lifecycle.yaml .sdd/controls/lifecycle.yaml
diff -qr .claude/schemas .sdd/schemas
diff -qr .claude/rules .sdd/modules/rules
diff -qr .claude/workflows .sdd/modules/workflows
diff -qr .claude/profiles .sdd/modules/profiles
diff -qr .claude/templates .sdd/modules/templates
```

Expected: every command exits `0` with no differences.

- [ ] **Step 4: Register the existing outputs without rewriting them**

Record target mtimes, run the writer, and confirm only the manifest is new:

```bash
PYTHONPATH=src ../../.venv/bin/python scripts/render-compatibility.py --root . --write
PYTHONPATH=src ../../.venv/bin/python scripts/render-compatibility.py --root . --check
../../.venv/bin/python -c 'from hashlib import sha256; from pathlib import Path; value = sha256(Path(".sdd/generated-files.json").read_bytes()).hexdigest(); assert value == "2d4be624cc96d4852a4ba23fcf4f652cf61e1083ae97a73358d795f81e77e851", value'
```

Expected output:

```text
OK: compatibility projection updated
OK: compatibility projection is current
```

- [ ] **Step 5: Add immutable migration provenance and ignored runtime state**

Create `.sdd/migrations/0001-claude-to-sdd.json` with exactly:

```json
{
  "baseline_commit": "43839f372501de7453beef9e3df7f35f03f9b251",
  "manifest_format_version": 1,
  "manifest_sha256": "2d4be624cc96d4852a4ba23fcf4f652cf61e1083ae97a73358d795f81e77e851",
  "migration_id": "0001-claude-to-sdd",
  "renderer": "sdd.adapters.compatibility:v1",
  "source_layout": ".claude",
  "target_layout": ".sdd"
}
```

Add `.sdd/state/` to `.gitignore`. Do not create or commit the state directory.

- [ ] **Step 6: Run canonical, projection, and legacy regression tests**

```bash
PYTHONPATH=src ../../.venv/bin/python -m unittest \
  tests.test_canonical_projection \
  tests.test_compatibility_projection \
  tests.test_compatibility_cli \
  tests.test_legacy_cli_characterization -v
```

Expected: PASS, with 45 manifest entries and no legacy CLI payload changes.

- [ ] **Step 7: Commit the authority transfer**

```bash
git add .gitignore .sdd .claude tests/test_canonical_projection.py
git commit -m "feat: make sdd sources authoritative"
```

---

### Task 6: Primary Validator Integration

**Files:**

- Modify: `scripts/validate-instructions.sh:51-95,338-354,656-665`
- Modify: `tests/helpers.py:21-27`
- Modify: `tests/test_validator_cli.py:19-42,70-127`

**Interfaces:**

- Consumes: the projection CLI and existing runtime probe.
- Produces: repository validation that checks parity before the legacy engine,
  aggregates ordinary projection findings, and propagates technical exit `3`.

- [ ] **Step 1: Update isolated repository fixtures and add failing validator tests**

Change `tests/helpers.temporary_repository()` to copy both `.sdd` and
`.claude`. Add `.sdd` and `src` to `repository_copy()` in
`tests/test_validator_cli.py`; the existing whole-`scripts` copy includes the
new renderer.

Add these tests:

```python
def test_primary_validator_rejects_stale_generated_output(self):
    with repository_copy() as root:
        canonical = root / ".sdd/modules/rules/security.md"
        canonical.write_text(canonical.read_text("utf-8") + "\nCanonical change.\n")
        result = run_script(root)

    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
    self.assertIn("stale_output", result.stdout)
    self.assertIn(".claude/rules/security.md", result.stdout)


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
```

Retain the existing exact successful stdout contract.

- [ ] **Step 2: Run validator tests and confirm drift is not yet detected by the projector**

```bash
PYTHONPATH=src ../../.venv/bin/python -m unittest tests.test_validator_cli -v
```

Expected: the new projection-specific tests FAIL.

- [ ] **Step 3: Invoke projection check after the runtime probe**

Add this shell flow immediately before `ENGINE_ARGUMENTS`:

```bash
PROJECTION_OUTPUT="$("$PYTHON" -B "$ROOT/scripts/render-compatibility.py" --root "$ROOT" --check 2>&1)"
PROJECTION_STATUS=$?
if [[ $PROJECTION_STATUS -ne 0 ]]; then
  printf '%s\n' "$PROJECTION_OUTPUT"
fi
if [[ $PROJECTION_STATUS -eq 3 ]]; then
  exit 3
fi
```

Add `render-compatibility.py` to the exact scripts inventory and executable checks.
Include `$PROJECTION_STATUS -ne 0` in the final exit-`1` condition alongside
engine and document status. A successful projection check remains silent so
the validator's current success output is unchanged.

- [ ] **Step 4: Run validator and full legacy policy tests**

```bash
PYTHONPATH=src ../../.venv/bin/python -m unittest \
  tests.test_validator_cli \
  tests.test_policy_validate \
  tests.test_policy_evaluate \
  tests.test_policy_lifecycle \
  tests.test_legacy_cli_characterization -v
```

Expected: PASS with unchanged successful engine payloads and exit codes.

- [ ] **Step 5: Commit validator integration**

```bash
git add scripts/validate-instructions.sh tests/helpers.py tests/test_validator_cli.py
git commit -m "feat: enforce compatibility projection parity"
```

---

### Task 7: Canonical-Authority Documentation

**Files:**

- Modify: `tests/test_readme_guidance.py:11-76`
- Modify: `tests/test_instruction_structure.py:861-899,943-949`
- Modify: `README.md:11-24,56-113,115-132,160-199,224-229`
- Modify: `.sdd/README.md`
- Modify through renderer: `.claude/README.md`
- Modify through renderer: `.sdd/generated-files.json`
- Modify: `implementation_status.md:20-24`

**Interfaces:**

- Consumes: the canonical layout and projection commands.
- Produces: onboarding and operating guidance that points authors to `.sdd/`
  while accurately describing `.claude/` as the P0 legacy execution boundary.

- [ ] **Step 1: Write failing documentation authority tests**

Add to `tests/test_readme_guidance.py`:

```python
def test_readme_identifies_canonical_and_generated_boundaries(self):
    for required in (
        "`.sdd/` is the authoritative source",
        "`.claude/` is generated compatibility output; do not edit it directly.",
        "scripts/render-compatibility.py --root . --check",
        "scripts/render-compatibility.py --root . --write",
        "The P0 legacy policy engine still reads `.claude/`.",
    ):
        self.assertIn(required, self.text)


def test_authoring_links_target_canonical_sources(self):
    for required in (
        ".sdd/README.md",
        ".sdd/controls/project.yaml",
        ".sdd/modules/workflows/project-initialization.md",
        ".sdd/modules/templates/feature-instruction-context.md",
    ):
        self.assertIn(required, self.text)
```

Add to `tests/test_instruction_structure.py`:

```python
def test_operating_guide_identifies_canonical_projection_workflow(self):
    canonical = read(".sdd/README.md")
    generated = read(".claude/README.md")
    self.assertEqual(generated, canonical)
    self.assertIn("`.sdd/` is the authoritative source", canonical)
    self.assertIn("do not edit it directly", canonical)
    self.assertIn("render-compatibility.py --root . --check", canonical)
    self.assertIn("render-compatibility.py --root . --write", canonical)
    self.assertIn("legacy policy engine still reads `.claude/`", canonical)
```

In the existing `test_quick_start_uses_supported_commands`, replace the
expected `.claude/project.yaml` authoring path with
`.sdd/controls/project.yaml`. Retain the existing `Claude-first`, safe-default,
and bounded compatibility assertions.

- [ ] **Step 2: Run documentation tests and confirm the old authority wording fails**

```bash
PYTHONPATH=src ../../.venv/bin/python -m unittest \
  tests.test_readme_guidance tests.test_instruction_structure -v
```

Expected: the new authority tests FAIL.

- [ ] **Step 3: Update root onboarding documentation**

In `README.md`:

- point authoring links to `.sdd/README.md`, `.sdd/controls/`, and
  `.sdd/modules/`;
- state the five exact phrases asserted in Step 1;
- add both direct projection commands beside the primary validator;
- show `.sdd/` as canonical and `.claude/` as its generated compatibility tree
  in the repository map;
- keep `CLAUDE.md` as the current Claude entry point and retain the bounded
  Spec Kit claims.

Update the implementation-status sentence about tracked operating requirements
to name `.sdd/` instead of `.claude/`. Leave historical test evidence and
previous feature-branch provenance unchanged.

- [ ] **Step 4: Update the canonical operating guide and render it**

Edit `.sdd/README.md`, never `.claude/README.md`, to state the same authority,
commands, and legacy boundary. Rewrite canonical artifact links so the same raw
bytes resolve from both copies:

```text
project.yaml                  -> ../.sdd/controls/project.yaml
schemas/example.json         -> ../.sdd/schemas/example.json
rules/example.md             -> ../.sdd/modules/rules/example.md
workflows/example.md         -> ../.sdd/modules/workflows/example.md
profiles/example.md          -> ../.sdd/modules/profiles/example.md
templates/example.md         -> ../.sdd/modules/templates/example.md
```

Then regenerate and check:

```bash
PYTHONPATH=src ../../.venv/bin/python scripts/render-compatibility.py --root . --write
PYTHONPATH=src ../../.venv/bin/python scripts/render-compatibility.py --root . --check
```

Expected: both commands exit `0`; `.claude/README.md` exactly equals
`.sdd/README.md`; the manifest changes only for the README entry and manifest
bytes.

- [ ] **Step 5: Run documentation, link, and projection tests**

```bash
PYTHONPATH=src ../../.venv/bin/python -m unittest \
  tests.test_readme_guidance \
  tests.test_instruction_structure \
  tests.test_canonical_projection \
  tests.test_validator_cli -v
```

Expected: PASS.

- [ ] **Step 6: Commit documentation**

```bash
git add README.md implementation_status.md .sdd/README.md \
  .sdd/generated-files.json .claude/README.md \
  tests/test_readme_guidance.py tests/test_instruction_structure.py
git commit -m "docs: document canonical sdd authority"
```

---

### Task 8: Full Verification, Independent Review, Repair, and Publication

**Files:**

- Review: every file changed since `43839f372501de7453beef9e3df7f35f03f9b251`
- Modify: only files required to resolve verified review findings

**Interfaces:**

- Consumes: the complete implementation from Tasks 1-7.
- Produces: verified review evidence, repaired implementation, pushed branch,
  and a pull request targeting `main`.

- [ ] **Step 1: Run the complete local verification matrix**

```bash
bash -n scripts/validate-instructions.sh
bash -n scripts/validate-feature-context.sh
PYTHONPATH=src ../../.venv/bin/python -m py_compile \
  src/sdd/adapters/compatibility.py scripts/render-compatibility.py \
  scripts/policy-engine.py
PYTHONPATH=src ../../.venv/bin/python scripts/render-compatibility.py --root . --check
POLICY_PYTHON=../../.venv/bin/python bash scripts/validate-instructions.sh
PYTHONPATH=src ../../.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
SDD_WHEEL_CHECK_DIR="$(mktemp -d)"
../../.venv/bin/python -m build --wheel --no-isolation \
  --outdir "$SDD_WHEEL_CHECK_DIR" .
find "$SDD_WHEEL_CHECK_DIR" -maxdepth 1 -name '*.whl' -print
git diff --check origin/main...HEAD
git status --short
```

Expected: every command exits `0`; projection and repository validation pass;
all tests pass; one wheel is produced; the diff has no whitespace errors; and
status contains only intentional implementation changes.

- [ ] **Step 2: Perform the required independent review**

Invoke `superpowers:requesting-code-review` and review the full diff from
baseline `43839f372501de7453beef9e3df7f35f03f9b251`. Require the reviewer to check:

- exact spec and acceptance-criteria coverage;
- overwrite/delete safety and preflight completeness;
- symlink, path traversal, case-collision, and special-file handling;
- interruption convergence and manifest-last ordering;
- deterministic serialization and stable exit codes;
- bootstrap provenance and all 45 mappings;
- legacy CLI and validator compatibility;
- documentation authority accuracy and deferred-scope honesty.

- [ ] **Step 3: Reproduce and repair every critical or important finding**

For each reviewer finding, first add or identify a focused failing test, run it
to confirm the defect, implement the smallest correction, and rerun that test.
Record evidence when a finding is rejected because an existing test or the
approved spec proves the reported behavior is intentional. Do not suppress or
weaken safety checks to make a test pass.

- [ ] **Step 4: Rerun verification after review repairs**

Repeat every command from Step 1 after the final repair. Then inspect:

```bash
git diff --stat origin/main...HEAD
git diff --check origin/main...HEAD
git diff --check
git status --short --branch
```

Expected: all verification remains green and no untracked implementation files
or generated drift remain.

- [ ] **Step 5: Commit review repairs when the review changed tracked files**

Stage only reviewed scope and commit:

```bash
git add .gitignore .sdd .claude README.md implementation_status.md \
  scripts src tests
git commit -m "fix: resolve canonical projection review findings"
```

When the independent review requires no tracked repair, preserve the existing
task commits and do not create an empty commit.

- [ ] **Step 6: Push and open the pull request**

Invoke `github:yeet` to confirm the final scope, push
`codex/p0-canonical-projections`, and open a PR targeting `main`. Use this PR
summary:

```markdown
## Summary

- make `.sdd/` authoritative for all 45 instruction artifacts
- generate and verify the tracked `.claude/` compatibility projection
- protect manual divergence with manifest ownership and conflict-safe writes
- enforce projection parity in repository validation

## Verification

- compatibility projection check
- primary instruction validator
- complete unittest suite
- wheel build and installation characterization
- independent post-implementation review with findings resolved
```

Because the project is solo and independent automated review is already
complete, make the PR ready for merge after creation. Do not change
repository-wide review protection as part of this slice.
