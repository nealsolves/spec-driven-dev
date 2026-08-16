# Thin Root Agent Adapters Design

Status: Approved

Date: 2026-08-15

Roadmap: [Issue #2 P0-P8 design](issue-2-p0-p8-roadmap.md)

Phase: [P0 — Trustworthy and adoptable baseline](https://github.com/nealsolves/spec-driven-dev/issues/3), Slice 3

## Purpose

Generate small, deterministic `CLAUDE.md` and `AGENTS.md` root adapters from
one canonical Markdown kernel. Both agents receive the same normative body;
only a short, fixed, informational preamble identifies the host adapter.

This slice advances the P0 exit criterion that Claude and Codex entry adapters
are reproducible, conformant, ownership-tracked, and within hard size limits.
It deliberately leaves structured rule models, renderer plugins, unmanaged
regions, and semantic policy comparison to P6 and P7.

## Design principles

- One authored normative body; never maintain parallel Claude and Codex prose.
- Generate simple files rather than interpret arbitrary prose.
- Prove P0 conformance by byte identity, not by claiming semantic inference.
- Keep the public check/write boundary stable so later phases can replace the
  internal model without changing repository workflows.
- Refuse unsafe or divergent writes; never add a convenience overwrite flag.
- Fail generation when content exceeds its budget; never truncate policy.

## Canonical artifacts

### Shared kernel

`.sdd/adapters/root-kernel.md` contains the complete authored root kernel. It
contains only the stable entry guidance approved by the roadmap:

1. canonical `.sdd/` authority and precedence;
2. current-change discovery from explicit intent and approved artifacts;
3. task-based module routing and mandatory loading;
4. deterministic policy evaluation and technical-failure behavior;
5. stop, prohibition, and human-authorization boundaries;
6. test-first implementation, validation, independent review, and repair;
7. documentation and generated-output parity; and
8. supported local command entrypoints.

Status, history, volatile evidence, full schemas, remote orchestration, and deep
framework guidance remain in canonical controls and routed modules. The kernel
names their repository-root paths as inline code instead of copying them.
Clickable relative links remain in maintained guides because one identical
Markdown body cannot resolve the same relative link from both
`.sdd/adapters/` and the repository root.

### Small renderer control

`.sdd/controls/adapters.yaml` contains only:

```yaml
format: 1
kernel: .sdd/adapters/root-kernel.md
limits:
  max_lines: 280
  target_lines: 180
  max_bytes: 16384
outputs:
  claude: CLAUDE.md
  codex: AGENTS.md
```

The loader accepts exactly these keys and values. It rejects unknown or missing
fields, unsafe paths, duplicate output paths, non-integer limits, unsupported
formats, a hard line limit above `280`, and output paths other than the two
declared root files.

P0 validates this compact contract directly in Python rather than introducing
a new JSON Schema. A future format `2` may add the normalized rule model and
renderer registry planned for P6; format `1` remains readable for explicit
migration.

## Deterministic outputs

Each generated file is:

```text
fixed informational preamble for the target
+ exact root-kernel bytes
```

The preamble states that the file is generated, names the canonical sources,
identifies Claude or Codex, and says not to edit the output directly. It cannot
add normative requirements or vary policy between agents. Source paths in the
shared body are inline code, not location-dependent Markdown links.

The shared body in both outputs must be byte-identical to
`.sdd/adapters/root-kernel.md`. The renderer uses UTF-8, LF line endings, and
exactly one trailing newline. It emits no timestamps, host paths, branch names,
test counts, or other volatile values.

Generation fails before mutation if an output exceeds `280` physical lines or
`16384` bytes. Repository acceptance tests additionally require the initial
outputs to meet the `180`-line target. The target is a design pressure; the hard
limits remain the compatibility contract.

## Package and command boundaries

`src/sdd/adapters/agent.py` contains the complete P0 domain:

- immutable config, output, plan, and finding types;
- strict config and manifest loading;
- deterministic in-memory rendering;
- line/byte and shared-body checks;
- non-mutating repository parity checks; and
- safe convergence of the two fixed root outputs.

The implementation stays in one focused module until a second materially
different adapter strategy justifies extraction. It does not refactor or depend
on private compatibility-projector internals.

`scripts/render-agent-adapters.py` is a thin executable wrapper:

```text
render-agent-adapters.py --root PATH --check
render-agent-adapters.py --root PATH --write
```

Success exits `0`; ordinary parity or ownership findings exit `1`; technical
inability to inspect or apply the plan exits `3`. Public failures are concise
and structured without expected tracebacks. Check mode is the default used by
the primary validator.

## Bounded P0 conformance

P0 does not parse or compare arbitrary policy meaning. An adapter conforms when:

- its fixed preamble is exactly the renderer-owned preamble for that target;
- the remainder is byte-identical to the canonical shared kernel;
- both outputs therefore contain the same normative bytes in the same order;
- the canonical control and kernel paths are safe and present.

This proves that the renderer did not add, remove, weaken, strengthen, or reorder
normative content between agents. P6 may replace the shared body with a richer
normalized model; P7 may add rule fingerprints and semantic-diff classes. Those
enhancements do not belong in format `1`.

## Ownership manifest

`.sdd/agent-adapters.generated.json` is canonical JSON containing only:

- manifest format and renderer identity;
- adapter-control path and digest;
- shared-kernel path and digest;
- adapter format version; and
- each output path, SHA-256 digest, line count, byte count, and non-executable
  mode.

It is separate from `.sdd/generated-files.json`, whose strict format and targets
belong to the temporary `.claude/` compatibility renderer. The two manifests own
disjoint outputs and do not create a dual-write path.

The compatibility projector is changed only enough to recognize
`.sdd/controls/adapters.yaml`, `.sdd/adapters/`, and
`.sdd/agent-adapters.generated.json` as canonical-only artifacts. It never
copies them into `.claude/`, and its existing four controls, four schemas, and
module output inventory remain unchanged. Any other new canonical artifact
still fails closed.

## Safe write behavior

Check mode performs no filesystem mutation, including bytecode, temporary
files, or metadata changes.

Write mode handles only two fixed files in the already validated repository
root. It:

1. loads and validates the config, kernel, prior manifest, root, and targets;
2. renders both outputs and the desired manifest completely in memory;
3. verifies byte identity and limits;
4. accepts each target only when missing, already desired, or equal to its
   prior owned digest and mode;
5. writes changed outputs through same-directory temporary files and
   `os.replace` after immediate target rechecks;
6. verifies the final live output bytes and modes, then rechecks the repository
   root and `.sdd/` directory identities;
7. rechecks the prior-or-desired manifest state; and
8. replaces the ownership manifest last.

Symlinked, special, divergent, case-conflicting, unrepresentable, or otherwise
unsafe targets block without being changed. A missing manifest never grants
permission to overwrite an existing divergent root file. Interrupted writes are
rerunnable because prior-or-desired owned states are accepted.

There is no staging tree or directory-creation protocol: both targets live in
the existing repository root and the complete candidate bytes already exist in
memory. The writer provides point-in-time safe, idempotent convergence, not
whole-directory atomicity.

## Repository migration

The Slice 3 commit introduces the config, shared kernel, both generated files,
ownership manifest, and `.sdd/migrations/0002-root-agent-adapters.json`
together. The migration record binds the previous `CLAUDE.md` digest, records
that `AGENTS.md` was absent, and records the new canonical and output digests.

This is repository migration evidence, not a runtime adoption feature. Runtime
write mode does not silently adopt or overwrite unmanaged legacy files; general
legacy adoption remains assigned to P1.

## Primary validation

The primary validator invokes adapter check mode after compatibility parity and
before its existing success message. It also registers the renderer script as
an executable repository artifact and requires both root files to be regular,
non-symlink files. Its existing Markdown-link validation expands to include
`AGENTS.md`; the shared kernel intentionally uses location-independent inline
paths.

Adapter check mode owns config strictness, manifest integrity, byte generation,
shared-body identity, file modes, and budgets. The shell validator does not
duplicate those checks.

Instruction changes update canonical `.sdd/` sources first, regenerate affected
compatibility outputs when needed, regenerate both root adapters, and run the
complete primary validator.

## Testing

Test-first coverage includes:

- strict format-1 config parsing and safe fixed paths;
- deterministic preambles, shared-body bytes, LF endings, and serialization;
- 280-line/16384-byte hard failures and the repository's 180-line target;
- manifest strictness and canonical JSON;
- missing, stale, conflicting, unsafe, and mode-drift output findings;
- no-mutation check mode;
- safe creation in a new fixture and refusal of unmanaged divergence;
- interrupted output replacement, manifest-last behavior, and rerun convergence;
- target and manifest changes at mutation boundaries;
- CLI exit codes and concise failure output;
- compatibility exclusion of canonical-only adapter artifacts;
- primary-validator propagation and success-output suppression;
- exact repository regeneration and migration digests; and
- the complete existing policy, compatibility, package, and validator suites.

Broad rule-level semantic fixtures, renderer plugins, arbitrary unmanaged
regions, and generalized adapter migrations are explicitly deferred.

## Documentation

The root README and canonical `.sdd/README.md` explain that:

- `.sdd/adapters/root-kernel.md` is the normative shared root source;
- `.sdd/controls/adapters.yaml` defines only rendering and budgets;
- `CLAUDE.md` and `AGENTS.md` are generated managed entry adapters;
- direct output edits are rejected;
- check and write commands are available; and
- P0 byte identity is intentionally narrower than P6/P7 conformance.

The approved roadmap design is tracked in this slice so later phase plans cite
the same architecture rather than a task transcript.

## Acceptance criteria

1. `CLAUDE.md` and `AGENTS.md` reproduce byte-for-byte from one canonical
   kernel plus their fixed informational preambles.
2. The normative body of both outputs is byte-identical to the shared kernel.
3. Each initial output is at most 180 physical lines and remains within the
   280-line/16384-byte hard limits.
4. Check mode detects config, source, manifest, output, mode, ownership, or
   budget drift without mutation.
5. Write mode preserves unmanaged or divergent files, converges owned states,
   and commits the manifest last.
6. Compatibility outputs remain exactly the legacy bundle; canonical-only
   adapter artifacts are accepted but never projected into `.claude/`.
7. The primary validator fails closed on adapter drift or technical blocks.
8. The migration record binds old and new repository states reproducibly.
9. Existing policy behavior, compatibility projection, packaging, and all prior
   P0 tests remain green.
10. Independent review reports no unresolved Critical or Important finding.
