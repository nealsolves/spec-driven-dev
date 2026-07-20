# Modular Instruction System Design

## Status

Approved in conversation on 2026-07-20. This design governs the migration of the
repository's existing `CLAUDE.md` into a reusable, manifest-driven instruction
template aligned with GitHub Spec Kit.

## Context

The repository begins with an Apache 2.0 license and a 264-line `CLAUDE.md`.
It has no application source, CI configuration, Spec Kit artifacts, feature
directories, or repository-specific development commands. The result must
therefore remain a reusable template and must not invent project facts.

The source implementation brief is
`Codex_Instructions_Modular_CLAUDE_System.md`, supplied outside this repository.
It requires a compact root contract, deterministic progressive disclosure,
proportional enterprise controls, solo-developer compatibility, complete
templates, and executable validation.

## Goals

- Keep root `CLAUDE.md` at or below 350 physical lines, preferably 250–320.
- Make instruction activation deterministic and auditable.
- Retain strong spec-driven, test-first, security, PR, release, and rollback
  discipline without imposing irrelevant controls on low-risk work.
- Support one person owning the whole lifecycle by default.
- Support optional team and regulated control overlays.
- Keep requirements portable across agents and tool installations.
- Align the lifecycle with Spec Kit v0.13.0 as a design reference without
  claiming that an instantiated repository has tested that version.
- Provide actionable validators for both the reusable system and feature-level
  instruction declarations.

## Non-goals

- Do not create application code, project-specific CI, or deployment systems.
- Do not create a fake feature directory.
- Do not claim that the template is compliant, secure, production-ready,
  merged, or deployed merely because policy files exist.
- Do not require a particular agent, slash command, proprietary review tool,
  or installed Spec Kit version when an equivalent capability can provide the
  required artifact and evidence.

## Selected Approach

Use a manifest-driven modular system. `CLAUDE.md` is the instruction kernel;
`.claude/instructions.yaml` is the router; the project profile selects ownership
and overlays; focused Markdown modules define detailed controls and workflows;
templates capture evidence; portable shell scripts verify the system.

This approach was selected over:

1. A Spec Kit preset-only implementation, which would couple the contract to
   changing Spec Kit internals and would not satisfy the required `.claude`
   routing system.
2. A root contract with unstructured appendices, which would be simpler but
   would leave module activation to nondeterministic agent judgment.

## Architecture

### Root kernel

`CLAUDE.md` contains only durable, universal material:

- purpose and project identity;
- authority and actual-versus-intended behavior;
- startup and feature resolution;
- universal invariants;
- Spec Kit lifecycle and gates;
- change classification and routing summary;
- universal Git, PR, and CI rules;
- exceptions and completion criteria;
- links to the detailed system.

Detailed rules are linked rather than copied. Activated modules are mandatory.

### Routing and profile configuration

`.claude/instructions.yaml` uses the exact required top-level schema. Routes are
additive: a feature may activate `feature`, `security_sensitive`,
`data_sensitive`, and `production_impact` simultaneously. All applicable
workflow and rule files load, with duplicates de-duplicated.

`.claude/project-profile.yaml` defaults to a production-capable solo developer
and uses reusable placeholders for project identity. Its Spec Kit section uses:

```yaml
tested_version: unknown
minimum_version: unknown
allow_equivalent_manual_gates: true
```

The README records v0.13.0 as the lifecycle design reference, not a test claim.
Repository owners replace `unknown` only after validating their instantiated
repository.

### Modules

Rule modules cover engineering, testing, security, architecture, data privacy,
production readiness, observability, release management, compliance,
ownership, AI systems, and documentation. Every rule module provides purpose,
applicability, inputs, mandatory controls, evidence, exceptions, solo
interpretation, relevant overlay notes, and a completion checklist.

Workflow modules cover features, bugs, maintenance, dependencies, brownfield
behavior, releases, and incident hotfixes. Each defines entry criteria,
artifacts, gates, ordered steps, evidence, exit criteria, solo interpretation,
and stop conditions.

Profiles distinguish solo, team, prototype, and regulated-overlay behavior.
One person may hold all solo roles. High-risk solo work requires a temporally
separate self-review and explicit self-approval. AI review is advisory and is
never represented as independent human approval. A regulated overlay may
override solo allowances when an external control requires separation.

### Evidence templates

Templates provide complete, usable records for feature instruction context,
architecture decisions, threat models, privacy, production readiness,
observability, compliance, risk exceptions, release readiness, incidents, and
maintenance. Mandatory fields make decisions and evidence visible without
requiring private model reasoning.

### Status

The root `implementation_status.md` is a reusable repository summary. It uses
distinct not-started, in-progress, in-review, merged, deployed, blocked, and
deferred states. It contains no unsupported current-state claims. Feature-level
status belongs in the active feature directory when one exists.

## Startup and Data Flow

An agent performs these steps in order:

1. Read `CLAUDE.md`, `.claude/project-profile.yaml`, and
   `.claude/instructions.yaml`.
2. Resolve the active feature from explicit user selection,
   `SPECIFY_FEATURE_DIRECTORY`, `.specify/feature.json`, or the branch pattern.
3. Load engineering, testing, and documentation as always-on rules.
4. Classify the change conservatively and activate every matching route.
5. Load the base profile and each configured overlay.
6. Read active feature artifacts when applicable.
7. Record loaded modules, risk, production-readiness level, required evidence,
   and not-applicable rationales in the feature plan or maintenance record.
8. Confirm the relevant lifecycle gate before implementation.

Ambiguous feature resolution, a missing required module, a constitutional
conflict, or an unapproved high-risk exception stops readiness.

## Spec Kit Compatibility

The lifecycle is:

```text
constitution -> specify -> clarify -> plan -> checklist -> tasks
             -> analyze -> implement -> converge
```

Commands and agent skills are preferred interfaces, not dependencies. If an
installed integration lacks `checklist` or `converge`, the agent creates the
equivalent artifact manually, records the fallback in the plan, and preserves
the underlying gate. The same capability-equivalent policy applies to review,
security, testing, and release tools.

## Policy Corrections

- Required CI on the exact reviewed merge candidate is authoritative for merge;
  local checks remain required pre-PR evidence.
- Production is never a test target. Unit, contract, integration, end-to-end,
  sandbox, and production verification have explicit boundaries.
- Behavioral and risk-based coverage replaces a unit-test-per-function rule.
- Percentage coverage is a floor, supplemented by acceptance-criteria,
  changed-code, contract, schema, migration, and risk coverage.
- Security findings may be fixed or governed by an approved, expiring exception
  with compensating controls.
- Direct-to-main remains prohibited by default, with controlled break-glass and
  incident restoration procedures.
- Brownfield specifications govern intended behavior; code, telemetry, data,
  and consumer contracts are evidence of actual behavior that must be
  reconciled before behavior changes.

## Validation and Error Handling

`scripts/validate-instructions.sh` verifies required files, the root line limit,
YAML parsing, manifest references, required lifecycle language, local Markdown
links, profile validity, and mandatory solo/regulated/CI statements. It uses
PyYAML only if already available. Without PyYAML, it performs portable
structural checks and reports a warning rather than installing a dependency.

`scripts/validate-feature-context.sh <feature-directory>` verifies Spec Kit
artifacts, the Instruction Context declaration, classifications, loaded modules,
risk and readiness levels, not-applicable rationales, clarification markers,
and classification-specific module dependencies.

Validators use actionable `ERROR`, `WARNING`, and success messages and return a
non-zero status on failure. They do not modify the repository.

## Verification Strategy

- Run the instruction-system validator on the completed repository.
- Check `CLAUDE.md` with `wc -l`.
- Check both scripts with `bash -n`.
- Exercise feature-context validation against temporary valid and invalid
  fixtures.
- Deliberately test missing files, unresolved clarification markers, and missing
  classification-required modules using temporary copies.
- Review all local links, manifest paths, profile names, duplicate rules,
  authority statements, and solo/regulated interactions.
- Confirm low-risk routes avoid unrelated production or compliance artifacts.
- Confirm high-risk routes activate security, operations, evidence, and review
  controls.

## Git and Publication

The workspace is initialized from the existing private GitHub repository
`nealsolves/spec-driven-dev`. Its `main` branch and Apache 2.0 `LICENSE` are
preserved. Work will be committed with Conventional Commit messages and pushed
to that repository only after applicable validation and review gates pass.

## Acceptance

The implementation is accepted when every deliverable in the source brief
exists, scripts are executable, positive validation passes, deliberate negative
checks fail actionably, `CLAUDE.md` is no more than 350 lines, no fake feature
directory exists, no repository commands are invented, and the final report
lists placeholders and any deliberate deviations.
