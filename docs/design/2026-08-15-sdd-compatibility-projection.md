# Canonical `.sdd` Compatibility Projection Design

Status: Approved for implementation planning

Date: 2026-08-15

Roadmap issue: [#3 — P0: Trustworthy and adoptable baseline](https://github.com/nealsolves/spec-driven-dev/issues/3)

Baseline: merge commit `43839f372501de7453beef9e3df7f35f03f9b251`

## Purpose

Establish `.sdd/` as the repository's single authoritative instruction and
control source while preserving the current policy engine unchanged behind a
generated `.claude/` compatibility tree.

This is the second independently reviewable P0 slice. The first slice created
the installable package baseline and characterized the legacy CLI. This slice
changes source ownership and projection verification, not policy decisions.

## Approved constraints

- Migrate the complete current 45-file `.claude/` tree in one authority
  transition. Do not create a controls-only split authority.
- Preserve every current file byte-for-byte during bootstrap.
- Keep `scripts/policy-engine.py` reading `.claude/` in this phase.
- Treat `.claude/` as tracked generated output after migration.
- Never overwrite or delete an unexpectedly modified generated file.
- Validate the complete projection before changing managed outputs.
- Keep projection generation deterministic, offline, and based only on local
  repository content.
- Keep root `CLAUDE.md` and the future `AGENTS.md` outside this slice. They
  require the normalized adapter model and semantic-conformance work that
  follows.

## Non-goals

- Moving or restructuring the legacy policy engine.
- Introducing the public `sdd` CLI planned for P1.
- Generating thin root Claude and Codex adapters.
- Implementing semantic comparison of arbitrary prose.
- Implementing general `sdd adopt` for external repositories.
- Adding documentation inventory, component hashing, or CI enforcement beyond
  the projection parity needed by this slice.

## Canonical and generated layouts

The authority mapping is:

```text
.sdd/README.md                         -> .claude/README.md
.sdd/controls/project.yaml            -> .claude/project.yaml
.sdd/controls/routing.yaml            -> .claude/routing.yaml
.sdd/controls/policy.yaml             -> .claude/policy.yaml
.sdd/controls/lifecycle.yaml          -> .claude/lifecycle.yaml
.sdd/schemas/*                        -> .claude/schemas/*
.sdd/modules/rules/*                  -> .claude/rules/*
.sdd/modules/workflows/*              -> .claude/workflows/*
.sdd/modules/profiles/*               -> .claude/profiles/*
.sdd/modules/templates/*              -> .claude/templates/*
```

The canonical tree added by this slice is:

```text
.sdd/
  README.md
  controls/
    project.yaml
    routing.yaml
    policy.yaml
    lifecycle.yaml
  schemas/
  modules/
    rules/
    workflows/
    profiles/
    templates/
  migrations/
    0001-claude-to-sdd.json
  generated-files.json
```

`.sdd/state/` is reserved for ignored runtime state and is added to
`.gitignore`; it is not required to exist in a clean checkout.

Future controls such as `docs.yaml`, `hashes.yaml`, and `adapters.yaml` are not
invented in this slice. They will be added with their owning capabilities and
schemas.

## Package boundaries

Projection behavior lives under the package's adapter trust boundary:

```text
src/sdd/adapters/__init__.py
src/sdd/adapters/compatibility.py
scripts/render-compatibility.py
```

`compatibility.py` owns pure discovery, mapping, hashing, planning, checking,
and conflict detection. Filesystem mutation is isolated in the plan applier.
The script is a thin transitional entry point until P1 exposes the public CLI.

The primary interfaces are:

```python
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


def build_projection(root: Path) -> ProjectionPlan: ...
def check_projection(root: Path, plan: ProjectionPlan) -> tuple[Finding, ...]: ...
def write_projection(root: Path, plan: ProjectionPlan) -> None: ...
```

The concrete implementation may use smaller private helpers, but consumers
must not combine discovery, validation, and mutation into one opaque function.

## Deterministic discovery and mapping

Discovery uses an allowlisted layout rather than arbitrary output paths:

- Exactly the four existing YAML controls are accepted.
- Schema entries must be regular `.json` files below `.sdd/schemas/`.
- Module entries must be regular `.md` files directly below one of the four
  declared module namespaces.
- `.sdd/README.md` is the only guide projected to `.claude/README.md`.
- `.sdd/migrations/`, `.sdd/generated-files.json`, and `.sdd/state/` are
  management metadata, not projection sources.
- Symlinks, special files, path traversal, duplicate targets, case-colliding
  paths, and files outside the declared roots fail before a plan is produced.

Files are ordered by canonical POSIX source path. Projection copies raw bytes;
it does not normalize newlines, encoding, whitespace, or Markdown. SHA-256 is
computed over exact bytes. The executable bit is recorded and reproduced,
while incidental operating-system permission bits are ignored.

## Generated-file manifest

`.sdd/generated-files.json` is committed generated metadata. It contains:

```json
{
  "format_version": 1,
  "renderer": "sdd.adapters.compatibility:v1",
  "files": [
    {
      "source": ".sdd/controls/project.yaml",
      "target": ".claude/project.yaml",
      "source_sha256": "<64 lowercase hexadecimal characters>",
      "output_sha256": "<64 lowercase hexadecimal characters>",
      "executable": false
    }
  ]
}
```

The complete manifest is serialized as UTF-8 JSON with sorted keys,
deterministic entry ordering, two-space indentation, and one trailing newline.
Timestamps, host paths, user identities, and other volatile values are
prohibited.

The tracked manifest is both an ownership declaration and the record of the
last generated output. Its previous `output_sha256` values protect local
divergence during later writes.

## Initial authority migration

The bootstrap is deliberately different from an ordinary regeneration:

1. Copy every existing `.claude/` source into its canonical `.sdd/` location
   without changing bytes or executable state.
2. Build the expected projection from `.sdd/`.
3. Require every existing `.claude/` target to equal the expected bytes and
   mode. Any mismatch aborts the migration.
4. Create the first generated-file manifest without rewriting `.claude/`.
5. Record the authority transfer in
   `.sdd/migrations/0001-claude-to-sdd.json`.
6. Run projection parity, the primary validator, and the full characterization
   suite.

The migration record contains a stable migration ID, source and target layout
identities, baseline commit, manifest format version, renderer identity, and
the manifest digest. It contains no timestamps or machine-specific paths. Git
history is the rollback mechanism for this repository migration.

## Check flow

The supported read-only command is:

```bash
python scripts/render-compatibility.py --root . --check
```

Check mode:

1. Resolves and validates the repository root.
2. Loads and validates the previous manifest.
3. Builds the expected projection from canonical sources.
4. Compares expected entries with the tracked manifest.
5. Compares every expected output's bytes and executable state.
6. Enumerates the compatibility namespaces and reports missing, stale,
   conflicting, unexpected, extra-managed, malformed, or unsafe artifacts in
   deterministic path order.
7. Writes nothing, including caches.

Expected failures return exit code `1`; invalid invocation returns `2`; a
technical inability to inspect safely returns `3`. Human output is concise and
stable enough for shell use. The internal API returns structured findings so
later CLI JSON does not need to parse prose.

`scripts/validate-instructions.sh` invokes check mode after its Python runtime
probe and before the legacy engine. The script wrapper loads `src/` explicitly,
so the repository can validate itself without an editable package install.

## Write flow and conflict protection

The explicit mutation command is:

```bash
python scripts/render-compatibility.py --root . --write
```

Before any mutation, write mode performs a complete preflight:

- Build and validate the new plan.
- Load the prior manifest and validate every owned path.
- Reject unsafe paths, symlinks, special files, and ambiguous ownership.
- For each existing target, require its current state to match either the
  prior manifest or the newly desired output.
- For a new unmanaged target, allow registration only when it already equals
  the desired output; otherwise report a conflict.
- Preserve and reject any output artifact that is neither expected by the new
  plan nor owned by the prior manifest.
- For an output removed from canonical sources, permit deletion only when the
  current target still matches its prior manifest entry.
- Materialize the complete candidate `.claude/` tree in a temporary staging
  root, then validate its inventory, projection digests, executable states,
  and legacy policy bundle before replacing targets.
- Serialize and validate the candidate manifest against that staged tree.

If any preflight finding exists, no file changes.

Staging validates the complete desired projection, not only the entries that
changed. The legacy validator is pointed at the temporary root, so an invalid
canonical edit cannot partly update the live compatibility tree. The staging
directory is never treated as an ownership source and may be discarded after
validation or interruption.

Each changed output is written through a same-directory temporary file,
flushed, and atomically replaced. Safe removals occur only after the full
preflight. The new manifest is replaced last.

There is no cross-platform atomic operation for an entire directory tree. The
recovery contract is therefore idempotent convergence: after interruption,
each target may match either the prior manifest or the new desired output. A
rerun accepts those two proven states, completes the remaining replacements,
and writes the new manifest last. Any third state is a conflict.

## Error model

Projection failures are explicit and fail closed:

- `invalid_source`: malformed or unsupported canonical artifact.
- `unsafe_path`: escape, symlink, special file, or case collision.
- `invalid_manifest`: malformed, unsupported, or internally inconsistent
  ownership data.
- `missing_output`: managed target does not exist.
- `stale_output`: target differs from the expected canonical output but still
  matches the prior managed digest.
- `conflicting_output`: target matches neither prior ownership nor desired
  output.
- `unexpected_output`: artifact exists in a managed compatibility namespace
  but is neither expected nor declared by the prior manifest.
- `extra_managed_output`: prior manifest owns an output whose canonical source
  was removed.
- `technical_block`: the filesystem cannot be inspected or replaced safely.

Check mode may report all independently observable findings. Write mode must
complete the full preflight and report all conflicts before returning without
mutation.

## Legacy-engine compatibility

The legacy engine constants and file resolution remain unchanged:

```text
scripts/policy-engine.py -> .claude/{controls,schemas,modules}
```

Compatibility is established by projection parity, not by a second loader or
fallback search order. Ordinary policy operations never write either tree.
Canonical edits occur under `.sdd/`, then the explicit projector updates
`.claude/`.

Tests that create temporary repositories copy both `.sdd/` and `.claude/`.
Tests that intentionally mutate compatibility files may call the legacy engine
directly. Repository-level validation must reject such divergence through the
projection check.

## Verification strategy

Implementation follows test-driven development. Required tests include:

### Discovery and rendering

- The complete current canonical tree produces exactly 45 mapped outputs.
- Every bootstrapped output matches the pre-migration `.claude/` bytes and
  executable state.
- Ordering and manifest serialization are deterministic.
- Repeated planning produces identical bytes.
- Unsupported files, symlinks, path escapes, duplicate targets, and case
  collisions fail safely.

### Checking

- A fresh checkout passes parity.
- Missing, stale, conflicting, unexpected, and extra-managed outputs are
  distinguished.
- Manifest corruption and unknown format versions fail closed.
- Check mode makes no filesystem changes.

### Writing and recovery

- A canonical change updates only its mapped output and the manifest.
- An unchanged write is idempotent.
- Unexpected manual output edits block the complete write.
- Unmanaged extra outputs are preserved and block the complete write.
- A safely owned removed output is deleted; a divergent one is preserved and
  blocks.
- Failure during preflight changes nothing.
- Simulated interruption between replacements converges on rerun.
- Manifest replacement occurs last.

### Integration and regression

- `scripts/validate-instructions.sh` rejects projection drift.
- All existing validator, schema, policy, lifecycle, README, and CLI tests
  remain green.
- Existing successful CLI payloads and exit codes remain unchanged.
- Package wheel build and installation checks remain green.
- Validation works offline with the bounded local runtime.

## Documentation changes

This slice updates current documentation to state:

- `.sdd/` is authoritative.
- `.claude/` is generated compatibility output and must not be edited.
- The exact local check and regeneration commands.
- The legacy policy engine still executes against `.claude/` during P0.

Documentation must not claim that thin root adapters, the public `sdd` CLI,
general adoption, documentation inventory, or remote CI enforcement already
exist.

## Acceptance criteria

The slice is complete when:

1. All 45 existing `.claude/` artifacts have canonical `.sdd/` sources.
2. Bootstrap preserves their bytes and executable state exactly.
3. The committed manifest reproducibly describes every generated output.
4. Repository validation fails on any managed-output drift.
5. Regeneration refuses to overwrite unexpected manual changes.
6. Interrupted regeneration can converge safely on rerun.
7. The legacy engine and all characterized behavior remain unchanged.
8. Documentation identifies the correct authority and transitional execution
   boundary.
9. The implementation receives an independent post-implementation review and
   all critical and important findings are resolved before publication.

## Follow-on slice

The next P0 slice introduces the normalized adapter model, thin generated
`CLAUDE.md` and `AGENTS.md`, semantic-conformance checks appropriate to the
structured model, and the hard 280-line plus byte-size limits. It consumes the
canonical `.sdd/` tree and ownership mechanisms established here.
