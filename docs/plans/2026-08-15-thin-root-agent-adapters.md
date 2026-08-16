# Thin Root Agent Adapters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate managed `CLAUDE.md` and `AGENTS.md` entry adapters from one
canonical Markdown kernel with deterministic parity checks, bounded size, and
safe manifest-last writes.

**Architecture:** A single canonical Markdown body and a compact format-1
control feed a focused `sdd.adapters.agent` module. The module renders two fixed
informational preambles plus identical body bytes, checks a dedicated ownership
manifest, and safely converges only the two root outputs; a thin script and the
primary validator expose the behavior.

**Tech Stack:** Python 3.11+, standard-library dataclasses/pathlib/hashlib/json/
tempfile/stat/os, existing PyYAML 6.x, Bash, and `unittest`.

**Spec:** `docs/design/2026-08-15-thin-root-agent-adapters.md`

## Global Constraints

- `.sdd/adapters/root-kernel.md` is the only authored normative root body.
- `.sdd/controls/adapters.yaml` contains only format, kernel path, budgets, and
  the two fixed output paths.
- Both generated adapters contain fixed informational preambles followed by
  byte-identical kernel bytes; format 1 has no rule IDs, audiences, plugins,
  unmanaged regions, or semantic inference.
- Output encoding is UTF-8 with LF endings and exactly one trailing newline.
- Initial outputs are at most 180 physical lines; hard limits are 280 physical
  lines and 16384 bytes.
- The shared kernel uses repository-root paths as inline code, never relative
  Markdown links whose meaning changes when copied.
- Check mode performs no mutation, including bytecode or temporary files.
- Write mode owns only `CLAUDE.md`, `AGENTS.md`, and
  `.sdd/agent-adapters.generated.json`; it never overwrites divergent or
  unmanaged files and writes the manifest last.
- The existing `.claude/` compatibility bundle remains exactly unchanged;
  canonical-only adapter artifacts are accepted but not projected.
- Expected findings exit 1, invalid invocation exits 2, technical blocks exit
  3, and success exits 0.
- Use TDD for every behavior change and keep the complete existing suite green
  at every committed task boundary.
- After implementation, perform independent review, repair all Critical and
  Important findings, rerun the complete verification matrix, push, and open a
  pull request.

## File Structure

- `.sdd/adapters/root-kernel.md` — the one authored normative root body.
- `.sdd/controls/adapters.yaml` — strict format-1 renderer paths and budgets.
- `.sdd/agent-adapters.generated.json` — generated ownership/digest manifest.
- `.sdd/migrations/0002-root-agent-adapters.json` — immutable repository
  migration evidence.
- `src/sdd/adapters/agent.py` — config loading, rendering, manifest parsing,
  checking, and safe writes for the two fixed outputs.
- `scripts/render-agent-adapters.py` — thin check/write command.
- `tests/agent_adapter_helpers.py` — isolated adapter fixture and tree snapshot.
- `tests/test_agent_adapters.py` — pure planning, checking, and writing tests.
- `tests/test_agent_adapter_cli.py` — subprocess CLI contracts.
- `tests/test_root_agent_adapters.py` — exact repository parity, limits, body
  identity, and migration digests.
- `src/sdd/adapters/compatibility.py` — recognize canonical-only adapter
  artifacts without adding legacy outputs.
- `tests/test_compatibility_projection.py` — compatibility exclusion contracts.
- `scripts/validate-instructions.sh` — invoke root-adapter parity before the
  unchanged legacy engine succeeds.
- `tests/test_validator_cli.py` — adapter drift/status propagation.
- `tests/test_instruction_structure.py` — assert canonical kernel semantics and
  generated parity instead of treating `CLAUDE.md` as authored.
- `README.md`, `.sdd/README.md`, `implementation_status.md` — document the
  canonical source, generated outputs, commands, and current P0 boundary.

---

### Task 1: Permit Canonical-Only Adapter Sources Without Legacy Projection

**Files:**

- Modify: `src/sdd/adapters/compatibility.py`
- Modify: `tests/test_compatibility_projection.py`

**Interfaces:**

- Consumes: the existing 45-entry compatibility source discovery.
- Produces: explicit recognition of `.sdd/controls/adapters.yaml`,
  `.sdd/adapters/root-kernel.md`, and
  `.sdd/agent-adapters.generated.json` as safe canonical-only artifacts.

- [ ] **Step 1: Write failing compatibility exclusion tests**

Add tests that create all three future adapter artifacts in a projection
fixture and assert the plan remains exactly 45 entries:

```python
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
```

- [ ] **Step 2: Run the focused tests and record RED**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m unittest \
  tests.test_compatibility_projection.ProjectionPlanningTest.test_canonical_only_agent_adapter_artifacts_are_not_projected \
  tests.test_compatibility_projection.ProjectionPlanningTest.test_unexpected_file_in_canonical_adapter_directory_fails_closed -v
```

Expected: the first test fails because the current strict inventory rejects the
new control/root artifacts.

- [ ] **Step 3: Add narrow canonical-only discovery**

Keep the legacy projected allowlists unchanged and add separate constants:

```python
CANONICAL_ONLY_CONTROL_NAMES = ("adapters.yaml",)
CANONICAL_ONLY_ROOT_FILES = ("agent-adapters.generated.json",)
CANONICAL_ONLY_DIRECTORIES = {"adapters": ("root-kernel.md",)}
```

Permit these names during `.sdd` discovery, inspect them with the same
non-symlink/regular-file rules as projected sources, and never call
`add_entry()` for them. Reject any other child in `.sdd/adapters/`.

- [ ] **Step 4: Run focused and compatibility regression tests**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m unittest \
  tests.test_compatibility_projection tests.test_compatibility_cli \
  tests.test_canonical_projection -v
```

Expected: all pass with the existing platform skip only.

- [ ] **Step 5: Commit**

```bash
git add src/sdd/adapters/compatibility.py tests/test_compatibility_projection.py
git commit -m "feat: reserve canonical root adapter sources"
```

---

### Task 2: Strict Config and Deterministic Shared-Kernel Rendering

**Files:**

- Create: `.sdd/controls/adapters.yaml`
- Create: `.sdd/adapters/root-kernel.md`
- Create: `src/sdd/adapters/agent.py`
- Create: `tests/agent_adapter_helpers.py`
- Create: `tests/test_agent_adapters.py`

**Interfaces:**

- Consumes: repository `Path`, raw format-1 YAML, and raw kernel bytes.
- Produces: `AdapterFinding`, `AdapterFailure`, `AdapterLimits`,
  `AdapterConfig`, `AdapterOutput`, `AdapterPlan`, and
  `build_adapter_plan(root: Path) -> AdapterPlan`.

- [ ] **Step 1: Add an isolated adapter fixture**

Create `tests/agent_adapter_helpers.py` with explicit fixture content rather
than production constants:

```python
import tempfile
from contextlib import contextmanager
from pathlib import Path


CONFIG = """format: 1
kernel: .sdd/adapters/root-kernel.md
limits:
  max_lines: 280
  target_lines: 180
  max_bytes: 16384
outputs:
  claude: CLAUDE.md
  codex: AGENTS.md
"""


@contextmanager
def agent_adapter_repository(*, include_outputs: bool = False):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "repository"
        (root / ".sdd/controls").mkdir(parents=True)
        (root / ".sdd/adapters").mkdir()
        (root / ".sdd/controls/adapters.yaml").write_text(CONFIG, encoding="utf-8")
        (root / ".sdd/adapters/root-kernel.md").write_text(
            "## Purpose and Scope\n\nCanonical policy lives in `.sdd/`.\n",
            encoding="utf-8",
        )
        yield root
```

Add a snapshot helper that records relative file bytes and executable bits
without following symlinks.

- [ ] **Step 2: Write failing config/render tests**

Cover deterministic output order, exact body suffix identity, preamble
difference only, canonical JSON bytes, LF/trailing-newline rules, unknown
config keys, unsafe paths, invalid UTF-8, CRLF kernel input, and line/byte
limits. The core success assertion is:

```python
plan = build_adapter_plan(root)
self.assertEqual([item.target.as_posix() for item in plan.outputs], ["AGENTS.md", "CLAUDE.md"])
kernel = (root / ".sdd/adapters/root-kernel.md").read_bytes()
for output in plan.outputs:
    self.assertTrue(output.payload.endswith(kernel))
    self.assertEqual(output.byte_count, len(output.payload))
    self.assertEqual(output.line_count, output.payload.count(b"\n"))
self.assertNotEqual(plan.outputs[0].preamble, plan.outputs[1].preamble)
```

- [ ] **Step 3: Run the planning tests and record RED**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m unittest \
  tests.test_agent_adapters.AdapterPlanningTest -v
```

Expected: import failure because `sdd.adapters.agent` does not exist.

- [ ] **Step 4: Create the canonical config and compact kernel**

Create `.sdd/controls/adapters.yaml` exactly as shown in the spec. Create
`.sdd/adapters/root-kernel.md` with these exact section headings:

```text
## Purpose and Scope
## Authority and Canonical Sources
## Startup and Change Discovery
## Routing and Deterministic Decisions
## Implementation, Validation, and Review
## Lifecycle and Stop Conditions
## Git, CI, and Documentation Parity
## Completion and Escalation
```

Retain the current kernel's authority ordering, four outcomes, full lifecycle
and exceptional-state vocabulary, exact sentence
`Required CI on the exact merge candidate is authoritative for merge.`,
test-first rule, policy-gated publication, instruction-change human gate, and
bounded escalation fields. Name `.sdd/README.md`, all four `.sdd/controls/*`
files, `.specify/memory/constitution.md`, and `implementation_status.md` as
inline repository-root paths. Do not include status claims, histories,
Markdown links, or `.claude/` as an authority source. Keep the authored kernel
at most 165 lines so each fixed preamble fits the 180-line target.

- [ ] **Step 5: Implement the minimal types and renderer**

Use immutable dataclasses and fixed constants:

```python
CONTROL_PATH = PurePosixPath(".sdd/controls/adapters.yaml")
KERNEL_PATH = PurePosixPath(".sdd/adapters/root-kernel.md")
MANIFEST_PATH = PurePosixPath(".sdd/agent-adapters.generated.json")
RENDERER = "sdd.adapters.agent:v1"

@dataclass(frozen=True)
class AdapterLimits:
    max_lines: int
    target_lines: int
    max_bytes: int

@dataclass(frozen=True)
class AdapterConfig:
    format: int
    kernel: PurePosixPath
    limits: AdapterLimits
    outputs: tuple[tuple[str, PurePosixPath], ...]

@dataclass(frozen=True)
class AdapterOutput:
    name: str
    target: PurePosixPath
    preamble: bytes
    payload: bytes
    sha256: str
    line_count: int
    byte_count: int

@dataclass(frozen=True)
class AdapterPlan:
    format: int
    renderer: str
    config_sha256: str
    kernel_sha256: str
    outputs: tuple[AdapterOutput, ...]

@dataclass(frozen=True)
class AdapterFinding:
    code: str
    path: PurePosixPath | None
    message: str

class AdapterFailure(Exception):
    def __init__(self, findings: tuple[AdapterFinding, ...]):
        self.findings = findings
```

Load YAML with `yaml.safe_load`, require plain dictionaries with exact key
sets, reject `bool` where an integer is required, validate fixed paths, and
render outputs sorted by target path. Preambles are hardcoded informational
bytes; concatenate them directly with the validated kernel bytes.

- [ ] **Step 6: Run planning tests and the full suite**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m unittest tests.test_agent_adapters.AdapterPlanningTest -v
PYTHONPATH=src ../../.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

Expected: all pass; the full suite retains only the two expected filesystem
skips.

- [ ] **Step 7: Commit**

```bash
git add .sdd/controls/adapters.yaml .sdd/adapters/root-kernel.md \
  src/sdd/adapters/agent.py tests/agent_adapter_helpers.py tests/test_agent_adapters.py
git commit -m "feat: render shared root agent kernel"
```

---

### Task 3: Strict Manifest and Non-Mutating Parity Checks

**Files:**

- Modify: `src/sdd/adapters/agent.py`
- Modify: `tests/test_agent_adapters.py`

**Interfaces:**

- Consumes: `AdapterPlan` and optional prior manifest bytes.
- Produces: `AdapterManifest`,
  `load_adapter_manifest(root: Path) -> AdapterManifest`, and
  `serialize_adapter_manifest(plan: AdapterPlan) -> bytes`, and
  `check_agent_adapters(root: Path, plan: AdapterPlan) -> tuple[AdapterFinding, ...]`.

- [ ] **Step 1: Write failing manifest/check tests**

Add tests for a missing manifest, exact parity, stale canonical digest, missing
output, stale prior-owned output, divergent output, executable-bit drift,
symlink/special target, malformed/noncanonical JSON, duplicate outputs,
unrepresentable paths, and no mutation. Use stable finding codes:

```text
invalid_source
invalid_manifest
missing_output
stale_output
conflicting_output
unsafe_path
limit_exceeded
technical_block
```

The parity test writes `plan.outputs[*].payload` and
`serialize_adapter_manifest(plan)`, then asserts
`check_agent_adapters(root, plan) == ()`.

- [ ] **Step 2: Run focused tests and record RED**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m unittest \
  tests.test_agent_adapters.AdapterCheckingTest -v
```

Expected: failures because manifest loading and checking are absent.

- [ ] **Step 3: Implement canonical manifest serialization**

Serialize sorted-key, two-space-indented JSON with one trailing newline:

```json
{
  "adapter_format": 1,
  "config": {"path": ".sdd/controls/adapters.yaml", "sha256": "..."},
  "files": [
    {
      "bytes": 0,
      "executable": false,
      "lines": 0,
      "path": "AGENTS.md",
      "sha256": "..."
    },
    {
      "bytes": 0,
      "executable": false,
      "lines": 0,
      "path": "CLAUDE.md",
      "sha256": "..."
    }
  ],
  "format": 1,
  "kernel": {"path": ".sdd/adapters/root-kernel.md", "sha256": "..."},
  "renderer": "sdd.adapters.agent:v1"
}
```

Require exact keys, exact fixed paths/order, lowercase 64-character SHA-256
values, nonnegative counts, `executable is False`, canonical bytes, and a
complete match to the desired plan.

Use an immutable parsed type:

```python
@dataclass(frozen=True)
class AdapterManifest:
    format: int
    renderer: str
    adapter_format: int
    config_path: PurePosixPath
    config_sha256: str
    kernel_path: PurePosixPath
    kernel_sha256: str
    files: tuple[tuple[PurePosixPath, str, int, int, bool], ...]
    raw_bytes: bytes
```

- [ ] **Step 4: Implement read-only checking**

Use `lstat()` and `read_bytes()` without following symlinks. Compare the desired
plan, strict manifest, and live target states. Classify a non-desired output as
`stale_output` only when it matches prior ownership; otherwise classify it as
`conflicting_output`. Sort findings by path and code. Translate expected OS and
encoding failures into structured findings.

- [ ] **Step 5: Run focused and full tests**

```bash
PYTHONPATH=src ../../.venv/bin/python -m unittest tests.test_agent_adapters -v
PYTHONPATH=src ../../.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

- [ ] **Step 6: Commit**

```bash
git add src/sdd/adapters/agent.py tests/test_agent_adapters.py
git commit -m "feat: check root agent adapter parity"
```

---

### Task 4: Safe Manifest-Last Convergence

**Files:**

- Modify: `src/sdd/adapters/agent.py`
- Modify: `tests/test_agent_adapters.py`

**Interfaces:**

- Consumes: validated `AdapterPlan`, optional strict prior manifest, and two
  fixed repository-root targets.
- Produces: `write_agent_adapters(root: Path, plan: AdapterPlan) -> None`.

- [ ] **Step 1: Write failing writer tests**

Cover:

```python
test_new_repository_creates_two_outputs_and_manifest
test_repeated_write_is_byte_and_mtime_idempotent
test_unmanaged_divergent_root_file_is_preserved_and_blocks
test_prior_owned_output_can_converge_to_desired
test_missing_owned_output_is_recreated
test_target_change_after_preflight_blocks_replacement
test_manifest_change_after_preflight_is_preserved
test_interruption_after_first_output_converges_on_rerun
test_final_output_verification_blocks_manifest_commit
test_replaced_repository_or_sdd_directory_blocks
```

For every blocked case, snapshot the tree before invocation and assert the
conflicting file and prior/absent manifest are preserved.

- [ ] **Step 2: Run writer tests and record RED**

```bash
PYTHONPATH=src ../../.venv/bin/python -m unittest \
  tests.test_agent_adapters.AdapterWritingTest -v
```

Expected: import or attribute failure for `write_agent_adapters`.

- [ ] **Step 3: Implement fixed-parent identity and atomic replacement helpers**

Capture resolved path, device, and inode for the repository root and `.sdd/`.
Reject symlinks and non-directories. Write a changed file with
`NamedTemporaryFile(dir=path.parent, delete=False)`, flush/fsync, `fchmod(0644)`,
then `os.replace`; unlink an unused temporary in `finally`.

Do not create directories, discover arbitrary targets, remove files, or extract
a generic writer abstraction in P0.

- [ ] **Step 4: Implement preflight and manifest-last write flow**

Preflight every target and the manifest before the first mutation. Accept
target states `{missing, desired, prior-owned}` and manifest states
`{missing, desired, prior}`. Immediately before each replacement, recheck both
parent identities and that target's state. After output replacements, verify
both live outputs, recheck parents and manifest state, then replace the manifest
only if needed.

On an interruption, already-desired outputs remain acceptable on rerun. Never
return success if final verification does not match `plan`.

- [ ] **Step 5: Run writer, adapter, and full tests**

```bash
PYTHONPATH=src ../../.venv/bin/python -m unittest \
  tests.test_agent_adapters.AdapterWritingTest -v
PYTHONPATH=src ../../.venv/bin/python -m unittest tests.test_agent_adapters -v
PYTHONPATH=src ../../.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

- [ ] **Step 6: Commit**

```bash
git add src/sdd/adapters/agent.py tests/test_agent_adapters.py
git commit -m "feat: write root agent adapters safely"
```

---

### Task 5: CLI and Repository Migration

**Files:**

- Create: `scripts/render-agent-adapters.py`
- Create: `tests/test_agent_adapter_cli.py`
- Create: `tests/test_root_agent_adapters.py`
- Create: `.sdd/agent-adapters.generated.json`
- Create: `.sdd/migrations/0002-root-agent-adapters.json`
- Create: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `tests/test_instruction_structure.py`

**Interfaces:**

- Consumes: the Task 2-4 package API.
- Produces: stable subprocess behavior, the tracked generated repository state,
  and immutable migration evidence from legacy CLAUDE digest
  `8f960d35d7ebf31cbd0a80c5f6cdc2a7b63c23a0c869a9e7a97fce5521c0ab70`.

- [ ] **Step 1: Write failing CLI tests**

Mirror the compatibility CLI's subprocess boundary. Test exact success output,
drift exit 1, invalid invocation exit 2, missing/corrupt package exit 3 without
traceback, write convergence, unmanaged divergence preservation, and no
bytecode or mutation in check mode.

Expected success strings:

```text
OK: root agent adapters are current
OK: root agent adapters updated
```

- [ ] **Step 2: Run CLI tests and record RED**

```bash
PYTHONPATH=src ../../.venv/bin/python -m unittest tests.test_agent_adapter_cli -v
```

- [ ] **Step 3: Implement the thin CLI**

Follow `scripts/render-compatibility.py`: set `sys.dont_write_bytecode = True`,
bootstrap `src/`, require exactly one of `--check`/`--write`, resolve `--root`
strictly, render findings as `ERROR: code: path: message`, and map technical
findings to 3. Keep business logic out of the script.

- [ ] **Step 4: Add repository parity and migration tests**

`tests/test_root_agent_adapters.py` must assert:

```python
plan = build_adapter_plan(ROOT)
self.assertEqual(check_agent_adapters(ROOT, plan), ())
outputs = {item.target: item for item in plan.outputs}
self.assertEqual((ROOT / "AGENTS.md").read_bytes(), outputs[PurePosixPath("AGENTS.md")].payload)
self.assertEqual((ROOT / "CLAUDE.md").read_bytes(), outputs[PurePosixPath("CLAUDE.md")].payload)
self.assertLessEqual(max(item.line_count for item in plan.outputs), 180)
self.assertLessEqual(max(item.byte_count for item in plan.outputs), 16384)
```

Also load the migration record and verify its old CLAUDE digest, absent old
AGENTS state, config/kernel digests, renderer, and new output digests.

- [ ] **Step 5: Generate and apply the one-time repository migration**

Use `build_adapter_plan(ROOT)` to obtain desired output bytes and
`serialize_adapter_manifest(plan)` to obtain desired ownership bytes. Apply
those exact bytes to `CLAUDE.md`, new `AGENTS.md`, and
`.sdd/agent-adapters.generated.json`; do not add an adoption flag to the public
writer. Create migration JSON with sorted keys, two-space indentation, one
newline, no timestamp, the fixed old CLAUDE digest above, and `null` for the old
AGENTS digest.

Update instruction-structure tests to read normative assertions from
`.sdd/adapters/root-kernel.md`, assert both generated files share that exact
body, expect the 180/280 budgets, and expect canonical `.sdd/` inline paths
instead of `.claude/` links.

- [ ] **Step 6: Run CLI, structure, repository, and full tests**

```bash
PYTHONPATH=src ../../.venv/bin/python -m unittest \
  tests.test_agent_adapter_cli tests.test_root_agent_adapters \
  tests.test_instruction_structure -v
PYTHONPATH=src ../../.venv/bin/python scripts/render-agent-adapters.py --root . --check
PYTHONPATH=src ../../.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

- [ ] **Step 7: Commit**

```bash
git add scripts/render-agent-adapters.py tests/test_agent_adapter_cli.py \
  tests/test_root_agent_adapters.py tests/test_instruction_structure.py \
  .sdd/agent-adapters.generated.json \
  .sdd/migrations/0002-root-agent-adapters.json CLAUDE.md AGENTS.md
git commit -m "feat: generate thin root agent adapters"
```

---

### Task 6: Primary Validator and Current Documentation

**Files:**

- Modify: `scripts/validate-instructions.sh`
- Modify: `tests/helpers.py`
- Modify: `tests/test_validator_cli.py`
- Modify: `README.md`
- Modify: `.sdd/README.md`
- Modify: `implementation_status.md`
- Regenerate: `.claude/README.md`
- Regenerate: `.sdd/generated-files.json`

**Interfaces:**

- Consumes: `scripts/render-agent-adapters.py --root ROOT --check`.
- Produces: adapter parity as a required local validation gate while retaining
  the validator's single existing success line.

- [ ] **Step 1: Write failing validator integration tests**

Update fixture copying to include `.sdd/adapters/`, the adapter control,
manifest, migration, `AGENTS.md`, renderer script, and `src/sdd/adapters/agent.py`.
Add tests proving:

```text
generated CLAUDE drift -> validator exit 1 with stale/conflicting output
generated AGENTS drift -> validator exit 1
adapter technical block -> validator exit 3
adapter success output -> suppressed by primary validator
missing/non-executable renderer -> inventory failure
broken AGENTS local Markdown link -> validator exit 1
```

Replace the old shell-specific 350-line and missing-lifecycle mutations with
adapter drift tests; the package check owns generated content and budgets.

- [ ] **Step 2: Run validator tests and record RED**

```bash
PYTHONPATH=src ../../.venv/bin/python -m unittest tests.test_validator_cli -v
```

- [ ] **Step 3: Integrate adapter parity once**

Add `render-agent-adapters.py` to the exact script/executable inventory. Add
`AGENTS.md` to required root files and Markdown validation. After compatibility
check succeeds, invoke:

```bash
"$PYTHON_BIN" "$ROOT/scripts/render-agent-adapters.py" --root "$ROOT" --check
```

Suppress its success line, propagate 1 and 3 unchanged, and do not duplicate
config, digest, or size logic in Bash. Remove the old authored-CLAUDE 350-line,
lifecycle-term, and exact-CI-text checks now covered by canonical generation and
instruction-structure tests.

- [ ] **Step 4: Update canonical documentation first**

Update `.sdd/README.md`, root `README.md`, and `implementation_status.md` with:

```text
.sdd/adapters/root-kernel.md is the authored normative root kernel.
.sdd/controls/adapters.yaml owns renderer paths and budgets only.
CLAUDE.md and AGENTS.md are generated; direct edits are rejected.
scripts/render-agent-adapters.py --root . --check
scripts/render-agent-adapters.py --root . --write
P0 proves identical normative bytes; richer semantic comparison remains P6/P7.
```

Change the status line from the obsolete 350-line CLAUDE-only check to both
adapters, 280 hard lines, 16384 bytes, and the initial 180-line target. Do not
add current test counts, branch names, or PR claims.

- [ ] **Step 5: Regenerate compatibility outputs**

```bash
PYTHONPATH=src ../../.venv/bin/python scripts/render-compatibility.py --root . --write
PYTHONPATH=src ../../.venv/bin/python scripts/render-agent-adapters.py --root . --write
```

Confirm `.claude/README.md` matches `.sdd/README.md`, the compatibility manifest
changes only for updated canonical documentation, and root adapters remain
within target budgets.

- [ ] **Step 6: Run integration and full verification**

```bash
bash -n scripts/validate-instructions.sh scripts/validate-feature-context.sh
PYTHONPATH=src ../../.venv/bin/python -m py_compile \
  src/sdd/adapters/agent.py scripts/render-agent-adapters.py
PYTHONPATH=src ../../.venv/bin/python scripts/render-compatibility.py --root . --check
PYTHONPATH=src ../../.venv/bin/python scripts/render-agent-adapters.py --root . --check
POLICY_PYTHON=../../.venv/bin/python bash scripts/validate-instructions.sh
PYTHONPATH=src ../../.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
git diff --check
```

- [ ] **Step 7: Commit**

```bash
git add scripts/validate-instructions.sh tests/helpers.py tests/test_validator_cli.py \
  README.md .sdd/README.md .claude/README.md implementation_status.md \
  .sdd/generated-files.json .sdd/agent-adapters.generated.json \
  CLAUDE.md AGENTS.md
git commit -m "feat: enforce root adapter parity"
```

---

### Task 7: Independent Review, Repair, and Publication Gate

**Files:**

- Review: `origin/main..HEAD`
- Verify: all files changed by Tasks 1-6

**Interfaces:**

- Consumes: the complete reviewed Slice 3 branch.
- Produces: no unresolved Critical/Important findings, fresh verification
  evidence, a pushed branch, and a pull request against `main`.

- [ ] **Step 1: Run the controller verification matrix**

```bash
bash -n scripts/validate-instructions.sh scripts/validate-feature-context.sh
PYTHONPATH=src ../../.venv/bin/python -m py_compile \
  src/sdd/adapters/agent.py scripts/render-agent-adapters.py \
  tests/test_agent_adapters.py tests/test_agent_adapter_cli.py \
  tests/test_root_agent_adapters.py
PYTHONPATH=src ../../.venv/bin/python scripts/render-compatibility.py --root . --check
PYTHONPATH=src ../../.venv/bin/python scripts/render-agent-adapters.py --root . --check
POLICY_PYTHON=../../.venv/bin/python bash scripts/validate-instructions.sh
PYTHONPATH=src ../../.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
git diff --check origin/main...HEAD
git status --short --branch
```

- [ ] **Step 2: Build the wheel from an archived source tree**

Use `python -m build --wheel --no-isolation` in a temporary archived checkout;
do not leave `build/` or egg-info files in the worktree.

- [ ] **Step 3: Request independent whole-branch review**

Review against the design and this plan, emphasizing:

```text
one normative source only
no P6/P7 rule-model features
shared-body byte identity
strict fixed paths and budgets
manifest-last conflict preservation
unchanged 45-file compatibility output
validator status propagation
no volatile documentation claims
```

- [ ] **Step 4: Repair findings and re-review**

Fix every Critical and Important issue using focused RED/GREEN regressions.
Repeat independent scoped review until no such finding remains. Record safe-to-
defer Minor findings explicitly.

- [ ] **Step 5: Rerun fresh final verification**

Repeat Steps 1-2 after the final repair commit. Completion claims must cite the
fresh exit statuses and test counts.

- [ ] **Step 6: Push and open the pull request**

Push `codex/p0-thin-agent-adapters`, open a draft PR against `main`, link issue
#3, list the exact P0 exit criterion advanced, summarize review repairs, and
include the fresh validation matrix. Preserve the worktree for PR feedback.
