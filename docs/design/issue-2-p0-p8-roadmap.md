# Issue #2 P0-P8 Roadmap Design

Status: Approved
Date: 2026-08-13
Parent epic: [#2 — Reduce operational friction identified by the AEGIS dogfood run](https://github.com/nealsolves/spec-driven-dev/issues/2)

## Purpose

This document is the canonical roadmap-level design for issue #2. It records
the approved architecture, invariants, phase boundaries, and acceptance
criteria for P0 through P8. The roadmap sub-issues summarize delivery scope;
this document preserves the complete design rationale and cross-cutting
contracts.

Roadmap sub-issues:

- [#3 — P0: Trustworthy and adoptable baseline](https://github.com/nealsolves/spec-driven-dev/issues/3)
- [#4 — P1: Transactional orchestration CLI](https://github.com/nealsolves/spec-driven-dev/issues/4)
- [#5 — P2: Hashing, durable records, and compact evidence](https://github.com/nealsolves/spec-driven-dev/issues/5)
- [#6 — P3: Automatic facts and evidence](https://github.com/nealsolves/spec-driven-dev/issues/6)
- [#7 — P4: Separate lifecycle aggregates](https://github.com/nealsolves/spec-driven-dev/issues/7)
- [#8 — P5: Repository doctor and safe finishing](https://github.com/nealsolves/spec-driven-dev/issues/8)
- [#9 — P6: Agent-neutral adapters](https://github.com/nealsolves/spec-driven-dev/issues/9)
- [#10 — P7: Semantic instruction comparison](https://github.com/nealsolves/spec-driven-dev/issues/10)
- [#11 — P8: Remote execution and reconciliation](https://github.com/nealsolves/spec-driven-dev/issues/11)

## Design inputs

The design incorporates lessons from:

- The current `spec-driven-dev` implementation and test suite.
- [AEGIS PR #18](https://github.com/nealsolves/aegis/pull/18), including its
  governance-artifact volume and documentation-parity implementation.
- The linked
  [Claude Code workflow discussion](https://www.reddit.com/r/ClaudeCode/comments/1vmey7d/my_claude_code_workflow_after_months_of_daily_use/),
  especially isolated work, persistent artifacts, independent review,
  measurement, and end-to-end verification.
- [GitHub Spec Kit](https://github.com/github/spec-kit), especially its
  staged workflow, installable CLI, agent-neutral integrations, packaged local
  assets, and generated-file ownership.
- The legacy Claude and Codex instruction files supplied during the design
  review. Their useful durability, precedence, review, rollback, and stop
  practices were retained; their duplication and observed drift were not.

Model-specific multi-chat choreography and universal multi-agent orchestration
are not core requirements. The framework standardizes durable workflow and
authority boundaries, not one agent vendor's conversation pattern.

## Current baseline

The current implementation already has a strong deterministic core:

- Deny-overrides policy evaluation.
- Schema-validated inputs and outputs.
- Exact-hash freshness checks.
- Pure, non-mutating policy operations.
- Explicit human authorization boundaries.
- A substantial unit-test suite around the policy engine.

The reviewed implementation also exposes the friction described by issue #2:

- The repository is Claude-first and has no first-class generated Codex
  adapter.
- Lifecycle orchestration, hashes, facts, and state are manually connected.
- Intermediate lifecycle artifacts create excessive committed volume.
- A universal completion state conflates local work with delivery and release.
- CI semantics do not distinguish absence, unavailability, and success.
- Repository hygiene and worktree recovery sit outside the workflow.
- Documentation status is manually maintained and has already drifted.
- There is no tracked CI workflow or installable CLI package baseline.

## Recommended approach

Use an **invariant-first incremental migration around the tested core**.

Do not perform a clean rewrite. Preserve the current pure policy behavior as a
characterization baseline, extract it incrementally into a package, and place
transactional orchestration above it. Each migration PR must leave a working,
tested vertical slice.

There is no general backward-compatibility or deprecation guarantee before the
first stable release. Instead:

- Provide one explicit `sdd adopt` path for the current Claude-first layout and
  dogfood repositories such as AEGIS.
- Preserve custom legacy content and surface conflicts.
- Generate temporary compatibility projections when the tested core still
  consumes the old layout.
- Do not create a permanent dual-write path or legacy policy loader.

## Approved invariants

1. `.sdd/` becomes the canonical policy and workflow source early in the
   roadmap.
2. The existing pure policy decisions remain the tested migration core until
   intentionally replaced by an approved design change.
3. Normal workflows contain no manually edited hashes or lifecycle state.
4. One compact append-only event log is the authoritative record for a change.
5. Local completion, delivery, release, and deployment are distinct concepts.
6. Remote observation does not imply remote mutation authority.
7. Unknown, unavailable, and contradictory evidence never silently becomes a
   pass.
8. Every PR must maintain documentation parity against its exact merge
   candidate.
9. `CLAUDE.md` and `AGENTS.md` must each remain at or below 280 physical lines
   and within a byte-size budget. The recommended target is at most 180 lines.
10. Cleanup never touches unrelated or ambiguously owned work.
11. Generated files are reproducible and ownership-tracked.
12. The installed CLI remains locally usable without network access or remote
    provider configuration.

## Canonical repository structure

```text
.sdd/
  controls/
    project.yaml
    routing.yaml
    policy.yaml
    lifecycle.yaml
    docs.yaml
    hashes.yaml
    adapters.yaml
  schemas/
  modules/
    rules/
    workflows/
    profiles/
    templates/
  records/
  migrations/
  state/                 # ignored local runtime state
```

Responsibilities:

- `controls/` contains authoritative machine-readable policy and routing.
- `schemas/` validates controls, events, evidence, and command results.
- `modules/` contains deeper task-routed guidance rather than duplicating it in
  root agent files.
- `records/` contains compact committed audit history.
- `migrations/` contains durable migration identities and source mappings.
- `state/` contains ignored locks, transaction journals, caches, raw logs, and
  generated local views.

The installable Python package is divided by trust boundary:

```text
sdd/
  core/       # pure schemas, routing, policy, lifecycle, hashes
  runtime/    # transactions, locks, recovery, hashing, events
  providers/  # observations and evidence normalization
  adapters/   # AdapterModel and deterministic renderers
  remote/     # explicitly authorized external actions
  cli/        # commands and result presentation
```

The supported runtime is Python 3.11 or newer. The package exposes a stable
`sdd` entrypoint and ships the assets needed for local/offline operation after
installation.

## Documentation parity

Documentation parity is a merge invariant, not a final cleanup activity.

Every tracked document has exactly one classification:

- Maintained current documentation.
- Target-state documentation.
- Historical documentation.
- Generated documentation.
- Instruction-system documentation.
- Agent adapter.

Each current or generated document declares source-to-consumer contracts. A
candidate check must verify:

- Every tracked document is classified exactly once.
- Every declared source and consumer exists.
- Generated documentation reproduces exactly.
- Examples, commands, schemas, links, and public claims agree with the
  implementation and controls.
- Historical and target-state material is not presented as current behavior.
- Instruction and adapter changes satisfy their review and conformance rules.
- A supposed no-document-impact change is derived from path and contract
  analysis, not a manual checkbox.

The check runs locally against the candidate tree and remotely against the
exact protected merge candidate. A stable required GitHub check plus branch
protection or a ruleset is necessary to prevent manual bypass. `sdd doctor
--remote` reports missing enforcement.

There is no extra documentation hash. Documentation is represented through
the maintained-docs, generated-docs, and agent-adapter components of
`implementation_hash`.

## Transactional change model

The authoritative record for a change is:

```text
.sdd/records/changes/<change-id>.jsonl
```

`ChangeState` is derived by replay. Specifications, plans, and maintained
project documents remain source artifacts; lifecycle context is not manually
edited.

Durable events include only material facts:

- Intent and classification.
- Accepted observations and evidence digests.
- Lifecycle transitions and holds.
- Human authority decisions.
- Documentation-parity outcomes.
- External action intent and outcome.
- Hash changes, invalidation, and recovery.

Raw command logs, repeated evaluations, secrets, caches, and generated views
remain ignored local state.

### Local transaction protocol

1. Acquire a scoped SDD lock.
2. Verify the existing event hash chain.
3. Recover or reconcile any transaction journal.
4. Replay the current state.
5. Collect and normalize required evidence.
6. Run the pure policy engine.
7. Stage durable events.
8. Verify the old log remains an exact prefix.
9. Atomically replace and synchronize the event log.
10. Regenerate derived views.

`sdd advance` performs all immediately satisfiable deterministic transitions in
one bounded invocation. It stops for work, evidence, authorization, resources,
or an external target and never skips gates.

### Authorization

The system constructs a fresh, pre-bound authorization packet. A human supplies
only the decision option, identity, authority basis, and optional conditions.

Authorization modes are:

- `authorize_once`, consumed by one action.
- `authorize_until_changed`, scoped to the relevant hashes.
- `deny`, scoped to the decision and retained as a durable event.

Interactive mode records the human decision time. Non-interactive mode may
accept an explicit decision time. Receipt time is recorded independently.
Stale packets are superseded with an explanation and a fresh packet.

Status distinguishes recorded evidence, live but unrecorded observations,
stale or invalidated evidence, and pending reconciliation.

## Hash model

There are exactly four top-level hashes:

### `policy_hash`

Hashes canonical `.sdd` controls, schemas, modules, and scope definitions. It
does not hash generated projections.

### `context_hash`

Hashes semantic intent, facts, source identities and digests, clarifications,
and constraints. It excludes timestamps, local cache paths, output locations,
and embedded hashes.

### `implementation_hash`

A composite root containing component digests for:

- Runtime.
- Configuration.
- Dependencies.
- Tests.
- Maintained documentation.
- Generated documentation.
- Agent adapters.

Evidence declares the component digests it depends on. A documentation edit
does not invalidate unrelated unit-test evidence.

### `record_hash`

Hashes the canonical event chain and is excluded from
`implementation_hash`.

Decisions bind to a `record_anchor`, the event-log prefix hash at the decision
boundary, instead of attempting to bind to a record that contains the decision
itself.

### Snapshot canonicalization

Supported snapshot types are workspace, Git index, and commit. Hashing includes
canonical repository paths, file type, Git executable bit, symlink target text,
and file bytes. It does not follow symlinks or include OS ownership and
incidental permission metadata.

A local parity event binds to policy, context, and relevant component digests.
Committing that event changes the commit SHA but not the implementation hash.
CI reruns against the exact candidate SHA and stores the authoritative remote
check outside the candidate, avoiding self-reference.

## Lifecycle model

The lifecycle is a state vector rather than a universal `COMPLETE` value:

```text
ChangeAggregate
DeliveryAttempt[]
ReleaseAttempt[]
DeploymentAttempt[]
Hold[]
```

### Change workflows

Full feature workflow:

```text
UNCLASSIFIED
  -> CLASSIFIED
  -> SPECIFIED
  -> CLARIFIED
  -> PLANNED
  -> TASKED
  -> ANALYZED
  -> IMPLEMENTING
  -> VALIDATING
  -> REVIEWING
  <-> CONVERGING
  -> LOCAL_COMPLETE
```

Short maintenance workflow:

```text
UNCLASSIFIED
  -> CLASSIFIED
  -> VALIDATING
  -> REVIEWING
  -> LOCAL_COMPLETE
```

Policy may define other explicit workflows. Holds are orthogonal and scoped to
requirements, policy, technical conditions, human decisions, resource limits,
or incidents. A hold does not erase the last valid phase. Rollback is a release
or deployment action, not a generic change state.

### Delivery

Each delivery attempt is keyed by provider, repository, and pull request:

```text
NO_PR -> PR_OPEN -> MERGED
                  -> PR_CLOSED
```

Candidate readiness is derived, not manually set:

```text
UNASSESSED | CHECKING | READY | STALE | BLOCKED
```

It considers the exact SHA, checks, documentation parity, review freshness,
approvals, merge authorization, base freshness, and repository rules. A PR may
open before local completion but cannot become merge-ready prematurely.

CI outcomes distinguish `not_configured`, `queued`, `running`, `passed`,
`failed`, `cancelled`, `skipped`, `not_run`, and `unavailable`. Non-run and
unavailable outcomes retain reasons such as infrastructure, billing, quota,
configuration, permissions, or unknown. Policy decides whether a declared
substitute is permitted; no outcome silently becomes passed.

### Release and deployment

Release attempts are per artifact and version:

```text
NOT_READY -> READY -> PUBLISHED -> VERIFIED
```

Deployment attempts are per environment:

```text
NOT_READY -> READY -> DEPLOYING -> DEPLOYED -> VERIFIED
```

Authority is a gate before readiness and may be autonomous, enhanced, human,
or prohibited. Failure, rollback, revocation, and yank remain explicit.
Documentation parity runs at local completion, exact-candidate readiness,
release claims, and deployment/runbook boundaries triggered by policy.

## Evidence providers and command execution

Evidence follows:

```text
Observation -> EvidenceRecord -> DerivedFact
```

An observation is untrusted. An `EvidenceRecord` is schema-valid, redacted,
and provenance-bound. A `DerivedFact` is produced by deterministic routing.
Malformed, unavailable, or unauthorized observations produce `unknown`, never
`false`.

Providers declare capabilities such as filesystem, Git, process, network,
credentials, and API read access. A read-only provider cannot silently fetch,
execute, use the network, or mutate repository caches. The GitHub evidence
provider observes only; GitHub mutations belong to the remote layer.

Configured command execution uses a separate authorized runner with:

- An argv array; shell execution is prohibited by default.
- Explicit working directory and environment allowlist.
- Network policy, timeout, and bounded retry behavior.
- Expected artifacts, exit semantics, and retention class.
- Declared implementation components invalidated by the result.
- Dry-run preview.

Evidence identity includes argv, working directory, snapshot, components, tool
versions, environment fingerprint, start/end time, exit status, structured
result, redacted summary and digest, and durable output when policy requires
it. Cache reuse requires an exact match of configuration, environment,
provider, components, and freshness.

Path classifications are additive but exclusive at the final artifact class.
A Markdown file under an instruction path is an instruction-system change, not
a documentation-only change. Unknown or multiply classified paths block.
Material or contradictory facts require scoped review. An override retains the
original evidence plus stronger evidence, rationale, reviewer, and expiry.

## Repository hygiene and safe finishing

Inspection, local completion, remote continuation, and cleanup are separate
trust boundaries.

### `sdd doctor`

Plain `sdd doctor` is local, deterministic, read-only, offline, and
reproducible. It checks controls, migrations, placeholders, owners, commands,
permissions, adapters, documentation, Git state, worktrees, dependencies, CI
configuration, and CLI/control versions.

Findings use:

```text
pass | fail | unknown | blocked | not_applicable
```

Each includes evidence, consequence, severity, affected control, and
remediation. JSON output and stable exit codes are required.

Remote enforcement inspection requires `sdd doctor --remote`. Remote
unavailability produces `unknown`.

`sdd doctor --fix-safe` first produces a repair plan. It may regenerate managed
projections, repair a managed executable bit, rebuild ignored views, or recover
an SDD transaction. It does not discard user work, remove Git index locks,
rewrite branches, fetch, push, merge, or weaken policy.

An SDD lock may be cleared only when it belongs to the current host, its owner
process is definitively gone, and its journal is reconciled.

### `sdd change start`

Projects select `worktree_preferred`, `worktree_required`, or
`current_worktree_allowed`. Starting records the explicit base ref and commit,
initial policy/context hashes, worktree and branch identity, pre-existing
changes, and scoped path classification. It never silently fetches or changes
the base.

Pre-existing dirty work is excluded from a new change. Overlap or ambiguous
ownership blocks completion for reconciliation.

### `sdd finish`

Plain `sdd finish` reaches or verifies local completion:

1. Recover and replay the change record.
2. Verify holds are resolved.
3. Compare the workspace with its recorded baseline.
4. Identify candidate files and unrelated/overlapping edits.
5. Regenerate managed projections.
6. Run applicable validation and documentation parity.
7. Verify adapters and limits.
8. Recompute hashes from the selected snapshot.
9. Confirm the candidate is reproducible.
10. Record `LOCAL_COMPLETE` or return exact blockers.

It does not stage, commit, merge, or delete by default.

Delivery introduces explicit snapshots:

```text
workspace -> index candidate -> committed candidate -> remote candidate
```

Parity and validation run against the exact index tree before commit. The tree
is recomputed after commit because hooks may alter it. Any later mutation makes
affected evidence stale.

Remote continuation is explicit, for example `sdd finish --through delivery`,
and requires an action plan plus the applicable authorization.

### Cleanup

Cleanup is a separate dry-run-first command. A worktree or branch may be
removed only when it is owned by the change, clean, inactive, fully merged into
the observed target, and backed by a valid durable record. The coordinator
must first move outside a worktree it intends to remove.

Remote branch deletion is separately configured and authorized. Dirty,
divergent, unmerged, shared, current, or ambiguous worktrees are never removed
automatically. Base synchronization is explicit and fast-forward-only; SDD
does not silently stash, rebase, reset, or update a dirty/divergent base.

## Remote execution and reconciliation

Remote support is optional. Local policy, hashing, replay, documentation
parity, and completion continue to work offline.

Remote integrations implement two separate interfaces:

```text
RemoteObserver
  discover capabilities
  read immutable repository identity
  observe PRs, checks, reviews, rules, releases, and deployments

RemoteExecutor
  preview an action
  validate authorization
  execute idempotently
  reconcile uncertain outcomes
```

Capabilities are narrow, such as repository read, PR create/update, branch
push, merge execute, release publish, deployment start, rules read, and checks
read. Missing capability blocks; it never causes a weaker substitute.

Every action plan binds to provider/host, immutable account and repository
identifiers, action type, exact candidate or artifact digest, base and target,
policy/context/component hashes, required capability and authority,
idempotency key, and redacted payload summary. Repository names and URLs alone
are insufficient because they can change.

Remote mutations require an explicit boundary such as delivery, release, or a
named deployment environment. Status, doctor, evidence collection, and local
finish cannot unexpectedly mutate remote state. Non-interactive execution
requires both an explicit flag and a pre-existing scoped authorization receipt.

The protocol is:

```text
observe
  -> validate policy and authority
  -> record durable intent
  -> execute with idempotency key
  -> observe the resulting state
  -> record outcome or reconciliation requirement
```

If a response is lost, the outcome becomes uncertain. Retry observes first and
does not blindly repeat the action. Webhooks may accelerate observation but are
not the sole truth source.

Unexpected remote drift invalidates the plan. SDD does not force-push, replace
releases, dismiss reviews, or override protection unless a separately defined
and authorized workflow explicitly permits it.

Credentials remain outside `.sdd`, events, previews, caches, and reports.
Redaction occurs before persistence. P8 introduces a typed remote-action
registry, not a general remote shell. Repository-configured text cannot become
an arbitrary API request or command.

Remote outcomes distinguish not configured, unavailable, unauthorized, rate
limited, queued, running, succeeded, failed, cancelled, and uncertain. None of
the non-success states counts as success. Local completion remains valid during
a remote outage unless local evidence itself becomes invalid.

## Agent-neutral adapters

Canonical instructions compile into a normalized `AdapterModel` containing
rule identity, source, normative strength, scope, conditions, audience,
lifecycle phases, precedence, required/prohibited actions, routed modules, and
justified agent-specific rendering hints.

Initial renderers produce `CLAUDE.md`, `AGENTS.md`, managed `.claude/`
compatibility files, and Codex-compatible projections where needed. The
generated-file manifest records renderer, canonical sources, digest, and format
version.

Root adapters contain only the stable operating kernel:

- Canonical source location and precedence.
- Current-change discovery.
- Task-based module routing.
- Stop and authorization behavior.
- Documentation-parity obligation.
- CLI invocation.

Status, history, evidence, full schemas, and deep framework guidance do not
belong in root adapters. If canonical content does not fit the line/byte budget,
generation fails rather than truncating or weakening it.

Agent-specific content may describe genuine platform invocation differences,
but the requirement remains canonical. An adapter cannot introduce, remove,
weaken, or strengthen policy unless the canonical model explicitly declares
the variation.

New installations use fully managed adapters. Explicit unmanaged regions are a
bounded exception: they count toward limits, cannot override canonical policy,
are checked for undeclared normative language, and produce `unknown` when
safety cannot be determined.

## Semantic instruction comparison

P7 compares structured meaning rather than pretending to understand arbitrary
prose.

Each canonical rule has a stable identifier and fingerprint. Renderers emit a
rule-to-output map. Conformance classifies each rule as:

```text
equivalent | lossy | missing | conflicting | extra | not_applicable | unknown
```

`unknown` requires review and never counts as parity. Checks verify normative
strength, conditions, scope, precedence, prohibitions, declared additions, and
routed module existence.

Version-to-version canonical diffs classify:

```text
rule_added
rule_removed
strengthened
weakened
scope_expanded
scope_narrowed
condition_changed
precedence_changed
rendering_only
unknown
```

Removals, weakening, precedence changes, expanded autonomous authority, and
unknown results trigger configured policy review. Narrative text without a
structured representation is compared by digest and reported as changed prose,
not automatically declared equivalent.

For each candidate, CI rebuilds the `AdapterModel`, regenerates adapters in a
temporary location, compares tracked outputs byte-for-byte, runs rule-level
conformance, enforces size limits, validates ownership, and rejects unmanaged
edits inside generated regions.

## Adoption and upgrades

`sdd adopt --plan` is analytical and non-mutating. It inventories existing
governance and classifies content as a canonical candidate, duplicate,
agent-specific capability guidance, project workflow, status/history,
conflict, or unknown.

The plan includes proposed controls/modules, generated adapters, rule-source
mappings, conflicts, managed-file changes, untouched legacy files, and a
rollback/recovery plan.

`sdd adopt --apply` requires a fresh approved plan and a clean isolated
candidate or an explicitly accepted baseline. It writes canonical sources,
generates adapters/manifests, imports accepted guidance, preserves unresolved
legacy content, validates parity and limits, records the migration, and
activates atomically.

Existing files are not silently overwritten or deleted. Managed-target
originals that cannot be imported are archived only with explicit approval.
Other custom legacy files remain but are marked non-authoritative. There is no
permanent dual-write path.

An upgrade may replace a managed file only when its digest matches the prior
manifest. Divergence produces a conflict and preserves the user version.

## Verification and CI

Before restructuring, preserve the current test suite and add
characterization tests for externally visible policy behavior. Move pure
behavior into `sdd.core` incrementally; do not reimplement it behind the CLI.

Test layers are:

- Core schemas, routing, policy, lifecycle, and hashes.
- Runtime locking, transactions, replay, recovery, and invalidation.
- Provider observation, normalization, provenance, and unknown handling.
- Adapter rendering, semantic conformance, ownership, and limits.
- CLI commands, exit codes, JSON, dry runs, and recovery.
- Git/index/worktree, adoption, documentation parity, and finishing scenarios.
- Remote idempotency, drift, outages, uncertain outcomes, and reconciliation.

Failure-injection tests interrupt every durable transaction boundary, including
event staging/replacement, filesystem synchronization, remote intent,
submission, response, and outcome recording. Restart must restore the prior
valid state or complete exactly once.

The stable required CI surface is:

```text
sdd / core
sdd / integration
sdd / docs-parity
sdd / dogfood
sdd / package
```

Validation workflows use minimum permissions and do not expose write
credentials to untrusted PR code. Stable aggregated checks prevent policy from
depending on internal job-name churn.

Dogfood operates at three levels:

1. A synthetic minimal repository.
2. A legacy Claude-first adoption repository.
3. `spec-driven-dev` itself.

AEGIS remains the high-complexity external dogfood target. Its useful recurring
shapes become minimized fixtures rather than live test dependencies.

The representative scenario must demonstrate no manual hash/state edits, fewer
than ten change-specific governance artifacts, one event log, automatic
evidence, recovery, clean finishing, and Claude/Codex parity.

Generated implementation status is derived from package/control/schema
versions, roadmap capabilities, the command registry, CI/parity configuration,
and durable milestone metadata. It excludes volatile test counts, branch names,
and open-PR claims.

Versions are independent:

```text
cli_version
control_schema_version
event_schema_version
adapter_format_version
```

The CLI refuses newer unknown formats, migrates declared older formats
explicitly, and never rewrites controls during ordinary commands. Expected
errors return stable codes, evidence, remediation, and recovery identity in
human and JSON forms. Diagnostic output remains explicitly requested and
redacted.

## P0-P8 delivery roadmap

The architectural dependency order is:

```text
P0 Safety rails
 -> P1 Usable CLI
 -> P2 Durable records and hashes
 -> P3 Automatic evidence
 -> P4 Lifecycle separation
 -> P5 Operational reliability
 -> P6 Agent-neutral maturity
 -> P7 Semantic governance
 -> P8 Authorized remote execution
```

P0-P5 form the first operational milestone. P6-P8 extend portability,
governance analysis, and remote automation.

Every roadmap PR must keep completed phases green, include behavior tests,
update canonical sources before projections, regenerate affected docs/adapters,
pass exact-candidate documentation parity, include migration/recovery when
persisted data changes, avoid manual hashes/status/state, remain independently
reviewable/revertible, name the acceptance criterion it advances, and leave no
undocumented temporary dual-write path.

A normal phase is sliced into contract/schema/characterization, pure core,
runtime/provider integration, CLI/migration, and dogfood/documentation PRs.

### P0 — Trustworthy and adoptable baseline

Keep the current engine as the execution core while adding the package skeleton,
canonical `.sdd` controls, generated compatibility projections, thin adapters,
line/byte gates, documentation inventory and parity, stable CI, generated
status, fixtures, file ownership, template configuration, and version/migration
metadata.

Exit when managed files reproduce, current behavior remains green, parity and
adapter conformance pass, required-check enforcement is verified, status has no
volatile claims, and self-dogfood/package installation succeed.

### P1 — Transactional orchestration CLI

Introduce stable initial forms of `init`, `adopt`, `doctor`, `change start`,
`evidence collect`, `advance`, `authorize`, `status`, and `finish`, with shared
result models, JSON, stable errors, dry runs, capabilities, idempotent offline
initialization, and atomic adoption. Initially shallow commands delegate to the
tested core.

Exit when new and legacy fixtures initialize/adopt safely, structured output is
stable, mutations are previewable/recoverable, remote state is never silently
mutated, and parity remains green.

### P2 — Explicit hashing and compact evidence

Introduce the event log, replay-derived state, four-hash model, component
digests, snapshot canonicalization, transactions, crash recovery, targeted
invalidation, generated views, and legacy-record migration.

Exit when workflows contain no manual hash/state edits, recovery is
deterministic, hashes are portable, invalidation is scoped, and representative
artifact volume is below ten.

### P3 — Automatic facts and evidence

Introduce provider capabilities, observation/evidence/fact normalization,
filesystem/Git/docs/manifest/test/build providers, the controlled runner,
read-only remote observation, provenance, redaction, exact caching, review of
material inferences, and unknown handling.

Exit when routine facts are automatic, provider failure never becomes false,
command authority is constrained, secrets remain out of records, caches are
dependency-exact, and contradictions receive review.

### P4 — Separate lifecycles

Introduce change workflows, holds, bounded advancement, delivery attempts,
exact-candidate readiness, explicit CI outcomes/reasons, release/deployment
attempts, rollback/revocation semantics, lifecycle migration, and parity at
claim boundaries.

Exit when local completion is distinct from delivery/release/deployment, CI
absence cannot masquerade as success, holds preserve state, authority is
separate, and no universal completion value remains.

### P5 — Operational reliability

Harden deterministic doctor, remote enforcement inspection, safe repair,
worktree-preferred start, baseline tracking, scoped local finish, candidate
snapshots, restartable completion, separate cleanup, ownership proof,
conservative synchronization, recovery diagnostics, and AEGIS exercise.

Exit when the first operational milestone acceptance criteria pass.

### P6 — Agent-neutral maturity

Mature the renderer registry, normalized model, capability variations, module
routing, ownership/upgrades, Claude/Codex production renderers, future adapter
packages, unmanaged-region checks, conformance kit, and adoption conflict
handling.

Exit when policy has no agent-specific truth, all rules map to adapters,
upgrades preserve divergence, renderers are extensible, and adapters stay
within budgets.

### P7 — Semantic governance

Add stable rule fingerprints, rule-to-render mapping, structural conformance,
version policy diffs, strength/scope/condition/precedence analysis,
rendering-only classification, conservative unknown handling, policy-review
routing, and PR summaries.

Exit when weakening/removal is detected, formatting creates no false policy
change, undeclared rules fail parity, unknown requires review, and results bind
to the exact candidate.

### P8 — Authorized remote execution

Add observer/executor interfaces, typed actions, capability/credential
validation, immutable target binding, planned authority, durable intent,
idempotency, reconciliation, drift detection, GitHub delivery execution, typed
CI dispatch, delivery continuation, release/deployment foundations, live
conformance, redaction, and minimum permissions.

Exit when uncertain retries cannot duplicate actions, drift blocks, merge
authority is exact, outcomes are observed, credentials remain out of records,
local work stays offline-capable, delivery reaches observed merge, and no
general remote shell exists.

## First operational milestone acceptance

Re-run the representative AEGIS truth-audit scenario and demonstrate:

- Zero manually edited hash fields.
- Zero manually edited lifecycle-state fields.
- Fewer than ten committed governance artifacts for the change.
- Automatic fact extraction with scoped human review.
- Automatic escalation packet and response handling.
- Explicit local completion versus remote delivery.
- Safe recovery from stale authorization and interrupted transactions.
- Supported clean worktree setup and post-merge cleanup.
- Equivalent mandatory behavior from Claude and Codex entrypoints.
- Complete exact-candidate validation through required repository CI.
- Documentation parity enforced during every merge.

## Deferred and non-goals

Do not prioritize these before the local operational milestone:

- Dimensional or weighted risk scoring.
- Universal multi-agent orchestration.
- Broad deployment-provider coverage.
- A hosted governance service.
- A general remote execution shell.
- Permanent compatibility with the pre-adoption layout.
- Weakening exact-hash binding, deny-overrides, or explicit authority.

## Principal risks and mitigations

### Migration rewrites tested behavior

Mitigation: characterize the current engine, extract it incrementally, and
change behavior only through explicit design/test updates.

### Canonical sources and projections become dual truth

Mitigation: projections are generated, ownership-manifest tracked, and checked
byte-for-byte in every PR. Compatibility projections have no write path.

### Event logs recreate artifact bloat

Mitigation: persist only durable decisions and digests; keep observations,
polling, logs, evaluations, caches, and views local or external.

### Hashes become self-referential

Mitigation: keep the event record outside implementation hashing, bind
decisions to a prior record anchor, and store remote check outcomes externally.

### `finish` becomes an unsafe automation macro

Mitigation: separate inspect, local complete, remote continuation, and cleanup;
require explicit action plans and authority at each boundary.

### Agent files drift or exceed usable size

Mitigation: one AdapterModel, deterministic generation, semantic conformance,
hard line/byte limits, and routed deeper modules.

### Remote retries duplicate actions

Mitigation: durable intent, idempotency keys, observe-before-act, and explicit
uncertain-state reconciliation.

### Documentation enforcement is configured but bypassable

Mitigation: use a stable exact-candidate check plus verified branch protection
or repository rules; report absent enforcement through remote doctor.

## Decision summary

- Architecture: invariant-first incremental migration around the tested core.
- Compatibility: one-way adoption, no general pre-stable compatibility promise.
- Canonical source: `.sdd/` controls, schemas, and routed modules.
- Runtime: installable Python 3.11+ CLI, locally usable after installation.
- Records: one committed append-only event log per change.
- Hashes: policy, context, composite implementation, and record.
- Lifecycles: separate change, delivery, release, deployment, and holds.
- Evidence: capability-scoped providers plus an authorized command runner.
- Documentation: exact-candidate parity required for every merge.
- Agents: generated Claude/Codex adapters, each no more than 280 lines.
- Finishing: local completion by default; remote continuation and cleanup are
  explicit boundaries.
- Remote: typed, idempotent, authorized actions; no general shell.
