# Thin Root Agent Adapters Design

Status: Proposed Slice Design  
Date: 2026-08-15  
Roadmap: [Issue #2 P0-P8 design](issue-2-p0-p8-roadmap.md)  
Phase: [P0 — Trustworthy and adoptable baseline](https://github.com/nealsolves/spec-driven-dev/issues/3), Slice 3

## Purpose

Generate small, deterministic `CLAUDE.md` and `AGENTS.md` root adapters from
one canonical `.sdd/` model. The adapters expose only the stable operating
kernel needed to enter the instruction system; detailed doctrine remains in
canonical routed modules.

This slice advances the P0 exit criterion that generated Claude and Codex
adapters are reproducible, semantically conformant, ownership-tracked, and
within hard size limits. It does not implement P6's extensible adapter packages
or P7's general semantic instruction comparison.

## Scope

The slice will:

- add a versioned canonical adapter control at `.sdd/controls/adapters.yaml`;
- validate that control against `.sdd/schemas/adapters.schema.json`;
- build a small normalized `AdapterModel` from structured sections and rules;
- render managed `CLAUDE.md` and `AGENTS.md` outputs deterministically;
- track their source and output digests in a dedicated generated manifest;
- teach the compatibility projector to recognize, but not project, the new
  canonical-only adapter control, schema, manifest, and migration metadata;
- provide non-mutating check mode and safe, manifest-last write mode;
- enforce physical-line and byte budgets before any write;
- check essential cross-adapter rule coverage and normative strength;
- integrate adapter parity into the primary repository validator; and
- update current guidance to state that both root files are generated entry
  adapters and `.sdd/` remains authoritative.

The slice will not:

- create a plugin or third-party renderer interface;
- support unmanaged regions inside generated root adapters;
- claim semantic equivalence for arbitrary prose;
- add general policy-version semantic diffs;
- render vendor-specific deep modules;
- mutate remote state; or
- merge the compatibility and root-adapter manifests into a new global
  manifest format.

Those capabilities remain assigned to P6 and P7.

## Canonical model

`.sdd/controls/adapters.yaml` is the only authored source for root-adapter
content and limits. Format version `1` contains:

- `adapter_format_version`;
- global budgets: hard maximum `280` physical lines, recommended target `180`
  physical lines, and hard maximum `16384` UTF-8 bytes per output;
- ordered kernel sections;
- stable rule IDs;
- a normative strength for each rule (`must`, `must_not`, or `informational`);
- portable rule text;
- source references into canonical controls, modules, the operating guide, or
  constitution;
- declared audience (`all`, `claude`, or `codex`); and
- narrowly scoped platform invocation notes where Claude and Codex genuinely
  differ.

The control rejects unknown fields, duplicate IDs, empty rules, nonexistent or
unsafe source references, unsupported audiences/strengths, and a platform-only
normative rule without an explicit justification.

The initial model contains only the roadmap-approved stable kernel:

1. canonical source location and authority precedence;
2. current-change discovery from explicit intent and approved artifacts;
3. task-based module routing and mandatory loading;
4. deterministic policy evaluation and technical-failure behavior;
5. stop, prohibition, and human-authorization boundaries;
6. test-first implementation, validation, independent review, and repair;
7. documentation and generated-output parity obligations; and
8. supported local CLI entrypoints.

Status, history, volatile evidence, full schemas, remote orchestration, and deep
framework guidance are linked rather than copied into root adapters.

## Package boundaries

`src/sdd/adapters/agent.py` owns the pure root-adapter domain:

- strict control loading and validation;
- immutable model types;
- deterministic rendering;
- size and essential-conformance findings;
- strict ownership-manifest loading;
- non-mutating repository checks; and
- safe local convergence.

`scripts/render-agent-adapters.py` is a thin executable boundary with:

```text
render-agent-adapters.py --root PATH --check
render-agent-adapters.py --root PATH --write
```

Expected parity findings exit `1`; technical inability to inspect or apply the
projection exits `3`; success exits `0`. Human output is concise and stable.
The package API returns structured findings so tests and future CLI commands do
not parse prose.

The existing compatibility projector remains responsible only for `.claude/`.
The root-adapter renderer neither reads nor writes compatibility targets.
Its canonical-source inventory is extended explicitly so
`.sdd/controls/adapters.yaml`, `.sdd/schemas/adapters.schema.json`,
`.sdd/agent-adapters.generated.json`, and the adapter migration record are
accepted as canonical-only artifacts. They are excluded from the legacy
`.claude/` projection, whose exact four controls, four policy schemas, and
module inventory remain unchanged. Any other new control, schema, or root
artifact still fails closed.

## Deterministic rendering

Both renderers consume the same normalized rule list. Each output has:

- a generated-file warning;
- canonical authority and source links;
- the same ordered section and rule IDs;
- mechanically rendered normative strength;
- a compact platform invocation note; and
- a final pointer to deeper routed guidance.

Line endings are LF, encoding is UTF-8, files end with one newline, section and
rule ordering comes from the canonical model, and serialization contains no
timestamps, host paths, branch names, test counts, or other volatile values.

Generation fails rather than truncating when either output exceeds 280
physical lines or 16384 bytes. Repository tests also enforce the design target
of at most 180 physical lines for the initial generated outputs; the control's
hard limit remains 280 for compatible future evolution.

## Essential conformance

P0 conformance is deliberately structural, not an arbitrary natural-language
equivalence claim. A rendered adapter conforms when:

- every canonical rule applicable to its audience is represented exactly once;
- no undeclared rule ID is present;
- the rendered normative strength matches the model;
- portable rules render from the same canonical text;
- every platform-only variation is declared and justified; and
- required canonical sources and routed modules exist.

The renderer emits stable, unobtrusive rule identity markers that the checker
can inventory. Tests independently compare the model and both rendered
outputs. P7 may later replace this bounded check with richer rule fingerprints
and semantic-diff classifications.

## Ownership and migration

`.sdd/agent-adapters.generated.json` is a canonical JSON ownership manifest
for `CLAUDE.md` and `AGENTS.md`. It records:

- manifest format and renderer identity;
- canonical control path and digest;
- each output path, digest, executable state, line count, and byte count; and
- adapter format version.

The manifest is separate from `.sdd/generated-files.json` because that existing
format is intentionally strict and owned by the temporary `.claude/`
compatibility renderer. The manifests own disjoint targets and do not create a
dual-write path. Compatibility planning treats the adapter manifest as
canonical-only metadata and never copies it into `.claude/`.

The repository migration is explicit. The approved Slice 3 commit introduces
the canonical control, newly rendered root adapters, manifest, and a durable
`.sdd/migrations/0002-root-agent-adapters.json` record together. The migration
record binds the prior `CLAUDE.md` digest, the absent prior `AGENTS.md` state,
the new canonical control digest, renderer identity, and resulting output
digests. Runtime write mode does not silently adopt or overwrite an unmanaged
preexisting root file.

After migration, write mode may replace an output only when it is missing,
already desired, or matches its prior owned digest and file mode. Divergent,
symlinked, special, case-colliding, or otherwise unsafe targets block without
being changed. The manifest is written last. Interrupted writes are rerunnable
and converge from prior-or-desired owned states.

## Validation flow

The primary validator runs adapter check mode after canonical compatibility
parity and before success output. It also enforces:

- the renderer script is present and executable;
- the adapter control and schema are in the exact inventory;
- both root outputs are regular non-symlink files;
- manifest ownership covers exactly `CLAUDE.md` and `AGENTS.md`;
- the hard limits and initial 180-line target pass; and
- essential conformance has no missing, conflicting, extra, or unknown result.

Instruction changes update `.sdd/` first, regenerate both root adapters and
their manifest, regenerate affected `.claude/` compatibility outputs when
applicable, and run the complete validator.

## Safety and error handling

Planning and check mode perform no filesystem mutation, including bytecode,
temporary files, or metadata changes. Write mode:

1. validates the root and canonical model;
2. renders both outputs completely in memory;
3. validates limits and conformance;
4. validates the prior manifest and all target states;
5. stages the complete candidate in a temporary directory;
6. checks candidate output and manifest bytes;
7. rechecks parent identities and target ownership immediately before each
   same-directory atomic replacement;
8. verifies final live outputs; and
9. replaces the ownership manifest last.

Expected drift produces structured findings and exit `1`. Unsafe paths,
unrepresentable data, I/O failures, or contradictory runtime state produce a
structured technical block and exit `3`; public commands do not leak a
traceback for expected repository failures.

The writer provides idempotent convergence, not whole-directory atomicity.
Concurrent mutation after the final point-in-time checks is outside that
claim, but the writer must never knowingly return success with a manifest that
does not describe the final verified outputs.

## Testing

Test-first coverage includes:

- strict schema/control parsing and duplicate/unknown-field rejection;
- deterministic model and byte rendering;
- Claude/Codex audience filtering and declared platform variations;
- hard line/byte failures and the repository's 180-line target;
- essential rule identity and normative-strength conformance;
- strict manifest parsing and canonical serialization;
- missing, stale, conflicting, unexpected, unsafe, and case-colliding outputs;
- no-mutation check mode;
- safe initial creation in a new fixture;
- refusal to overwrite unmanaged or divergent legacy root files;
- manifest-last interruption and rerun convergence;
- source, parent, target, and manifest race injection;
- CLI exit/status behavior without tracebacks;
- validator propagation and output suppression;
- compatibility-projector allowlisting that excludes canonical-only adapter
  artifacts from the unchanged legacy output bundle;
- exact repository generation parity;
- executable bits and script inventory; and
- the complete existing policy, compatibility, package, and validator suites.

## Documentation

The root README and canonical `.sdd/README.md` will explain:

- `.sdd/controls/adapters.yaml` is authoritative for root adapter content;
- `CLAUDE.md` and `AGENTS.md` are generated, managed entry adapters;
- direct edits are rejected and must be made canonically;
- check and write commands;
- the hard and target size budgets; and
- the bounded nature of P0 conformance versus P6/P7 maturity.

The approved roadmap design is tracked in this slice so future phase plans can
cite the same architecture rather than task transcripts.

## Acceptance criteria

The slice is complete when:

1. `CLAUDE.md` and `AGENTS.md` reproduce byte-for-byte from the canonical
   adapter control.
2. Each output is at most 180 physical lines in the initial repository, never
   exceeds the 280-line/16384-byte hard limits, and ends with one LF newline.
3. Essential conformance proves all applicable canonical rule IDs and
   normative strengths are represented exactly once without undeclared policy.
4. Check mode detects any canonical, manifest, output, mode, ownership, or
   conformance drift without mutation.
5. Write mode preserves unmanaged/divergent files, converges owned states
   safely, and commits the manifest last.
6. The primary validator fails closed on adapter drift or technical blocks and
   remains quiet on success except for its existing final status.
7. The migration record binds the legacy and generated states reproducibly.
8. Existing policy behavior, compatibility projection, packaging, and all
   prior P0 tests remain green.
9. An independent implementation review reports no unresolved Critical or
   Important finding.
