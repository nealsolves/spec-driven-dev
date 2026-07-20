# Modular Instruction System Design

## Status

Revised following design review on 2026-07-20. This design governs the migration
of the repository's existing `CLAUDE.md` into a reusable, policy-driven
autonomous delivery template aligned with GitHub Spec Kit. The revision is
pending final written-spec approval.

## Operating Doctrine

The system is autonomous by default. Human intervention is not a standard
lifecycle stage. It is an explicit exception triggered only when configured
authority, deterministic evidence, or policy-bounded risk controls are
insufficient to proceed safely.

> Automate by default. Escalate only when deterministic policy cannot safely
> resolve the decision.

Every decision belongs to one of three classes:

| Decision type | Handling |
|---|---|
| Deterministic engineering | The agent resolves it and records evidence. |
| Policy-bounded risk | The agent resolves it within configured thresholds. |
| Irreducible authority | The agent creates a decision packet and requires human action. |

Irreducible authority includes changing material business intent, accepting
legal or contractual risk, exceeding an approved financial limit, overriding
regulatory segregation, introducing a new sensitive-data use, accepting
critical residual security risk, and authorizing an irreversible destructive
production operation. Profiles may add stricter conditions but must not turn
routine evidence-based decisions into implicit human gates.

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
- Make policy-bounded engineering, review, merge, release, and deployment
  autonomous when the active authority policy permits them.
- Compute classification, risk, authority, lifecycle transitions, exceptions,
  and evidence requirements from machine-readable policy.
- Minimize human workload by escalating only a precise irreducible decision
  with collected evidence, options, consequences, and a recommendation.
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
- Do not grant unconditional remote or production authority. Authority must be
  explicit, scoped by action and risk tier, and disabled by default in the
  uninstantiated template.
- Do not treat model-authored classifications or approvals as deterministic
  merely because they are written to YAML. Observable facts are inputs; code
  evaluates the policy.

## Selected Approach

Use a policy-driven modular system with three layers:

1. `CLAUDE.md` is the compact behavioral kernel.
2. Markdown modules explain detailed policy, workflows, and evidence.
3. A machine-readable control plane and deterministic policy engine compute
   classification, risk, authority, transitions, exceptions, and escalation.

Templates capture evidence and portable scripts verify and execute the system.

### Practical implementation boundary

The control plane is a local CLI and file format, not a hosted workflow system.
Implementation is limited to pure policy functions, one command-line entry
point, declarative YAML, narrow JSON Schemas, file-based evidence, and unit or
fixture tests. It uses no daemon, database, message queue, plugin framework,
schema generator, custom policy language, or vendor-specific deployment code.
It evaluates and records whether an external action is authorized and safe to
retry; the coding agent invokes the available external capability.

The engine supports only the operations named in this design. Policy files use
explicit condition structures—never embedded code, `eval`, or a general-purpose
rules DSL. New abstraction is deferred until at least two implemented policies
need the same behavior.

This approach was selected over:

1. A Spec Kit preset-only implementation, which would couple the contract to
   changing Spec Kit internals and would not satisfy the required `.claude`
   routing system.
2. A root contract with unstructured appendices, which would be simpler but
   would leave module activation to nondeterministic agent judgment.
3. Markdown routing without an executable policy engine, which would document
   decisions but could not enforce autonomous transitions or authority limits.

## Architecture

### Root kernel

`CLAUDE.md` contains only durable, universal material:

- purpose and project identity;
- authority and actual-versus-intended behavior;
- startup, workflow selection, and conditional feature resolution;
- universal invariants;
- Spec Kit lifecycle and gates;
- change classification and routing summary;
- universal Git, PR, and CI rules;
- exceptions and completion criteria;
- links to the detailed system.

Detailed rules are linked rather than copied. Activated modules are mandatory.

### Machine-readable control plane

The control plane supplements Markdown policy with these files:

| File | Function |
|---|---|
| `.claude/instructions.yaml` | Map derived classifications to modules and workflows. |
| `.claude/project-profile.yaml` | Declare project identity, environments, data posture, and active policy sets. |
| `.claude/authority-policy.yaml` | Define autonomous, enhanced-gate, human-required, and prohibited actions by risk tier. |
| `.claude/risk-model.yaml` | Define weighted factors, thresholds, and automatic critical conditions. |
| `.claude/classification-rules.yaml` | Derive classifications from observable change facts. |
| `.claude/lifecycle.yaml` | Define states, allowed transitions, and machine-checkable prerequisites. |
| `.claude/exception-policy.yaml` | Define autonomous exception limits, evidence, expiry, and prohibited cases. |
| `.claude/evidence-schema.yaml` | Declare evidence types and requirements for gates and decisions. |
| `.claude/resource-policy.yaml` | Bound iterations, spend, retries, elapsed time, and external resource use. |

Formal JSON Schemas under `.claude/schemas/` validate the parsed representation
of every control-plane and evidence record. YAML remains the human-authored
format; `evidence-schema.yaml` declares which schema-backed evidence is required
for each control rather than duplicating JSON Schema definitions.

`scripts/policy-engine.py` is the deterministic executor. It accepts a feature
or maintenance context and control-plane files, validates the schemas, derives
routes and risk, checks authority and exceptions, validates a requested state
transition, and emits a machine-readable decision record. It never infers facts
internally. Agents may extract facts from repository evidence, but route, score,
authority, and transition evaluation occur in code.

The engine uses Python, PyYAML, and `jsonschema`. They are control-plane runtime
dependencies, not validation-only conveniences; a missing runtime dependency
produces `BLOCKED_TECHNICAL` rather than a nondeterministic fallback. Shell
validators may still provide reduced structural diagnostics when the runtime is
unavailable.

### Routing and project configuration

`.claude/instructions.yaml` retains the required top-level routing schema.
Routes are additive: a feature may activate `feature`, `security_sensitive`,
`data_sensitive`, and `production_impact` simultaneously. All applicable
workflow and rule files load, with duplicates de-duplicated. The agent does not
select these classifications directly: `classification-rules.yaml` maps
validated facts to them.

`.claude/project-profile.yaml` is solo-capable but unconfigured. It uses reusable
placeholders for project identity and begins with:

```yaml
project:
  lifecycle: unconfigured
authority:
  remote_actions_enabled: false
  production_actions_enabled: false
```

Its Spec Kit section uses:

```yaml
tested_version: unknown
minimum_version: unknown
allow_equivalent_manual_gates: true
```

The README records v0.13.0 as the lifecycle design reference, not a test claim.
Repository owners replace `unknown` only after validating their instantiated
repository.

The reusable profile prohibits remote mutations, merges, releases, deployments,
and autonomous risk exceptions until project initialization passes. Local
design, specification, implementation, and validation remain allowed.
Initialization may set `project.lifecycle: production`, select `solo` as the
base profile, and explicitly authorize branch pushes, PR creation and updates,
merging, releases, and deployments by risk tier. Absence of authority means the
action is not authorized; it does not mean a human must automatically approve
it.

### Observable facts and deterministic classification

Feature context contains typed facts such as runtime-code changes,
authentication or authorization impact, customer-data reads and writes, public
API changes, schema migrations, infrastructure changes, LLM use, and production
deployment intent. Fact validity and fact truth are distinct. The engine can
validate structure, provenance, evidence existence, contradictions, and
corroboration policy; it cannot prove that an extractor's assertion is true.

Each fact therefore records:

```yaml
value: false
source_type: diff_analysis
source_ref: evidence/diff-analysis.json
extractor: repository-fact-extractor-v1
confidence: 0.96
observed_at_commit: abc123
```

Material facts use `true`, `false`, or `unknown`. Material `false` assertions
require corroboration from at least two configured independent source types,
such as path analysis, semantic diff analysis, dependency graph analysis, or
contract-change detection. Material `unknown` values and facts below the
configured confidence threshold fail closed before `CLASSIFIED`; the agent
first gathers more evidence, then applies clarification policy if uncertainty
remains. A source is independent only when its extractor and evidence basis are
distinct, not merely when the same conclusion is copied into two files.

Classification rules are declarative implications. For example:

```text
modifies_authorization -> security_sensitive
reads_customer_data -> data_sensitive
uses_llm -> ai_system_change
deploys_to_production -> production_impact + observability_impact + release
```

The policy engine rejects unresolved material facts, contradictory mutually
exclusive facts, unsupported evidence references, inadequate corroboration, and
facts observed against a stale commit. It emits every matched rule and
provenance record so the result can be audited.

### Computable risk

`risk-model.yaml` groups factors into security, data, operational,
compatibility, financial, and delivery dimensions. Each factor has a severity,
evidence requirement, and optional `subsumes` relationship. Each dimension has
one simple aggregation rule:

| Dimension | Baseline aggregation |
|---|---|
| Security | Highest factor plus explicitly non-subsumed modifiers, capped. |
| Data | Highest factor. |
| Operational | Sum of independent factors, capped. |
| Compatibility | Highest factor. |
| Financial | Highest factor. |
| Delivery | Sum of independent factors, capped. |

Dimension scores map to low, moderate, high, or critical using non-overlapping
thresholds declared in the file. The overall tier is the highest dimension
tier. It increases only through an explicit cross-domain escalation rule, such
as authorization changes combined with regulated-data writes, rather than by
blindly adding correlated factors. Runtime behavior does not add again when it
is declared subsumed by a more specific factor in the same decision context.
Documentation-only is a route constraint, not a negative score, and is invalid
when runtime, dependency, infrastructure, data, or deployment facts are true.

The decision record contains factors, dimensions, aggregation steps, caps,
subsumption, cross-domain rules, evidence, automatic overrides, and final tier.
The model ships with table-driven examples for documentation-only maintenance,
a runtime feature, an authorization change reading customer data, a reversible
migration, and an irreversible production migration.

Automatic critical conditions override aggregation. They include destructive
production work without a verified recovery path, exposed credentials,
unsupported regulatory exceptions, unbounded financial commitments, and any
configured prohibited condition. Instantiated profiles may increase severity or
lower thresholds; weakening the baseline is an instruction-system change and
requires explicit authority.

### Authority policy

`authority-policy.yaml` grants scoped standing authority by action,
environment, and risk tier. Outcomes are:

- `autonomous`: proceed when normal transition evidence passes;
- `autonomous_with_enhanced_gates`: proceed only when the named extra gates pass;
- `human_required`: emit a human-decision packet and stop;
- `prohibited`: stop; human approval cannot override the policy without an
  authorized policy change.

The policy covers specification changes, implementation, PR mutations, merge,
release, deployment, financial actions, destructive operations, and risk
exceptions. Low- and moderate-risk production changes may be autonomous when
the instantiated profile grants authority and defines progressive delivery,
verification, and automatic rollback. High-risk production deployment is
human-required by default; critical deployment is prohibited by default.

The baseline authority matrix is:

| Action | Low | Moderate | High | Critical |
|---|---|---|---|---|
| Create specifications and resolve evidenced clarifications | autonomous | autonomous | autonomous | autonomous with enhanced evidence |
| Change material business intent | human required | human required | human required | human required |
| Implement | autonomous | autonomous | enhanced gates | human required |
| Create or update a PR | autonomous when remote actions are enabled | autonomous when enabled | enhanced gates when enabled | human required |
| Merge a PR | autonomous when remote actions are enabled | autonomous when enabled | enhanced gates when enabled | human required |
| Create a release | autonomous when remote actions are enabled | autonomous when enabled | human required | prohibited |
| Deploy to development or staging | autonomous | autonomous | enhanced gates | human required |
| Deploy to production | autonomous when enabled | progressive delivery and automatic rollback | human required | prohibited |
| Create a risk exception | autonomous within policy | autonomous with compensating controls | human required | prohibited |

Financial limits, destructive operations, sensitive-data introductions, and
regulated segregation are evaluated as separate authority conditions and may
override the tier row. Remote-action rows remain disabled until an instantiated
profile explicitly enables each action and names its target repository.

### Deny-overrides precedence

When applicable policies disagree, the most restrictive outcome wins:

```text
prohibited > human_required > autonomous_with_enhanced_gates > autonomous
```

Policy sources are authoritative in this order:

```text
external legal or contractual constraint
> constitution
> regulated overlay
> prohibited-condition policy
> project authority policy
> base profile
> workflow default
```

A lower source cannot weaken a higher source. A higher source may define an
explicit resolution for a named conflict; silence always preserves the more
restrictive outcome. The engine records every contributing decision and the
precedence step that selected the final result. Validators exercise the full
matrix and reject unknown outcome levels or ambiguous source ranks.

### Control-plane self-governance

Changes to `CLAUDE.md`, control-plane YAML, schemas, instruction modules,
`scripts/policy-engine.py`, or validation scripts activate
`instruction_system_change`. The trusted policy revision at the branch merge
base evaluates the proposed revision. The proposed revision cannot authorize,
score, classify, or approve itself.

Every such change requires:

- `evaluated_by_policy_hash` and `proposed_policy_hash`;
- before-and-after semantic policy comparison;
- identification of added, removed, and weakened controls;
- a control-plane version increment and schema-version impact assessment;
- regression fixtures for each changed decision outcome;
- authority under the trusted revision for any weakening.

Any proposal that expands autonomous production, financial, destructive,
security-exception, sensitive-data, or regulatory authority enters
`HUMAN_DECISION_REQUIRED`. A prohibited trusted-policy result cannot be relaxed
by the proposal under evaluation.

Initial installation is the only bootstrap case because no trusted control
plane exists at the branch base. It requires explicit human approval of this
design, records `bootstrap: true`, and installs the unconfigured,
production-disabled profile. After bootstrap, no missing-base fallback is
allowed.

### Modules

Rule modules cover engineering, testing, security, architecture, data privacy,
production readiness, observability, release management, compliance,
ownership, AI systems, and documentation. Every rule module provides purpose,
applicability, inputs, mandatory controls, evidence, exceptions, solo
interpretation, relevant overlay notes, and a completion checklist.

Workflow modules cover project initialization, instruction-system changes,
features, bugs, maintenance, dependencies, brownfield behavior, releases, and
incident hotfixes. Each defines entry criteria, artifacts, gates, ordered steps,
evidence, exit criteria, solo interpretation, and stop conditions.

`workflows/project-initialization.md` deterministically derives or collects
project identity, repository target, lifecycle, environments, known install,
test, lint, typecheck, and build commands, data classifications, authority
matrix, financial limits, production permissions, overlays, deployment and
rollback mechanisms, Spec Kit compatibility, escalation owner, and external
obligations. Unknown values remain explicit. Initialization passes only when
formal schema validation and required evidence are complete; until then, remote
mutations and autonomous exceptions remain prohibited.

`workflows/instruction-system-change.md` requires trusted-base evaluation,
semantic policy comparison, schema/version assessment, regression fixtures,
and authority checks for weakening. `instruction_system_change` routes to this
workflow; it is not treated as ordinary documentation maintenance.

Profiles distinguish solo, team, prototype, and regulated-overlay behavior.
One person may hold all solo roles. High-risk solo work requires a temporally
separate adversarial review sequence, but not routine human self-approval when
policy grants autonomous authority. AI review is advisory and is never
represented as independent human approval or regulated segregation. A
regulated overlay may override autonomous allowances when an external control
requires separation.

### Evidence templates

Templates provide complete, usable records for feature instruction context,
architecture decisions, threat models, privacy, production readiness,
observability, compliance, risk exceptions, release readiness, incidents, and
maintenance. Feature context includes facts, factor score, resulting risk tier,
activated controls, current lifecycle state, authority decision, and escalation
status. Mandatory fields make decisions and evidence visible without requiring
private model reasoning.

For feature work, the canonical machine-readable record is
`specs/<NNN>-<feature>/instruction-context.yaml`; `plan.md` contains a linked
human-readable summary. Reduced-overhead work uses a generated maintenance
record and sidecar context under `evidence/maintenance/<change-id>/`. Template
files define both forms, but no feature or evidence instance is created in this
reusable repository.

The implementation provides focused JSON Schema Draft 2020-12 files for project
profile, instruction context, authority policy, risk model, classification
rules, lifecycle, exception policy, resource policy, decision record, finding,
escalation packet, human-decision response, and external-action record. Schemas
share definitions where useful but are handwritten and narrow; the design does
not add schema generation, a registry service, or a database.

```text
.claude/schemas/
├── project-profile.schema.json
├── instruction-context.schema.json
├── authority-policy.schema.json
├── risk-model.schema.json
├── classification-rules.schema.json
├── lifecycle.schema.json
├── exception-policy.schema.json
├── resource-policy.schema.json
├── decision-record.schema.json
├── finding.schema.json
├── escalation-packet.schema.json
├── human-decision-response.schema.json
└── external-action.schema.json
```

When human action is required, the system creates a compact escalation packet
containing the exact decision, triggering policy, reason automation stopped,
evidence already collected, bounded options and consequences, a recommended
resolution, and the required response format. Open-ended approval requests are
invalid.

Human responses are machine-readable and include decision ID, selected option,
actor, authority basis, timestamp, feature or maintenance scope, commit,
conditions, and signed or authoritative source reference. The engine accepts a
response only when it matches an open unexpired decision, the actor has the
required authority, feature and policy hashes remain current, and conditions
have been incorporated. It then reevaluates the blocked transition; it never
blindly resumes or permits a decision to be replayed against changed context.

### External-action idempotency

Branch creation, push, PR creation and merge, release, deployment, rollback,
issue creation, and exception creation use schema-valid action records under
`evidence/actions/`. Each record contains `action_id`, `idempotency_key`,
`requested_state`, `target`, `policy_decision_hash`, `attempts`,
`external_reference`, `observed_result`, and `reconciled_at`.

Before executing or retrying, the agent must query actual external state through
the available capability and ask the policy engine to reconcile it. A matching
completed action returns its prior result; an uncertain or conflicting state
blocks retry. This repository supplies record validation, deterministic keys,
and reconciliation rules, not vendor-specific deployment adapters or a remote
orchestration service.

### Status

The root `implementation_status.md` is a reusable repository summary. It uses
distinct not-started, in-progress, in-review, merged, deployed, blocked, and
deferred states. It contains no unsupported current-state claims. Feature-level
status belongs in the active feature directory when one exists.

## Autonomous Lifecycle and Data Flow

The delivery sequence is:

```text
intent -> extract facts -> classify -> derive policy -> specify
       -> resolve answerable ambiguities -> plan -> generate controls
       -> implement -> test -> review -> repair -> converge -> release
       -> verify -> record evidence
```

An agent performs these operations in order:

1. Read `CLAUDE.md`, `.claude/project-profile.yaml`, and
   `.claude/instructions.yaml`.
2. Determine the workflow family from intent: project initialization, feature,
   bug, brownfield, maintenance, dependency, instruction-system, release, or
   incident.
3. Resolve an active feature only when that workflow requires one, using
   explicit selection, `SPECIFY_FEATURE_DIRECTORY`, `.specify/feature.json`, or
   the branch pattern. Otherwise assign a stable maintenance/change ID.
4. Load engineering, testing, and documentation as always-on rules.
5. Extract typed facts and attach repository evidence to each fact.
6. Run the policy engine to derive classifications, modules, risk tier,
   authority boundaries, exception limits, and transition prerequisites.
7. Load the base profile, overlays, routed rules, and workflows.
8. Read active feature artifacts when applicable.
9. Record or update machine-readable context and its Markdown summary.
10. Request the next lifecycle transition from the policy engine.
11. Proceed autonomously, apply enhanced gates, generate an escalation packet,
    or stop as dictated by the engine outcome.

Ambiguous feature resolution, a missing required module, a constitutional
conflict, invalid evidence, or a prohibited exception blocks the relevant
transition. These conditions do not all require a human; each maps to a defined
exceptional state and remediation path.

### Lifecycle state machine

The full delivery spine is:

```text
UNCLASSIFIED -> CLASSIFIED -> SPECIFIED -> CLARIFIED -> PLANNED -> TASKED
-> ANALYZED -> IMPLEMENTING -> VALIDATING -> REVIEWING -> CONVERGING
```

The workflow and deployment intent select an explicit terminal path:

```text
Code delivered:     CONVERGING -> COMPLETE
Release artifact:   CONVERGING -> RELEASE_READY -> COMPLETE
Deployment:         CONVERGING -> RELEASE_READY -> DEPLOYING
                    -> VERIFYING -> COMPLETE
Maintenance:        UNCLASSIFIED -> CLASSIFIED -> VALIDATING
                    -> REVIEWING -> COMPLETE
```

Project initialization and incident workflows have similarly explicit paths in
`lifecycle.yaml`. No workflow enters release or deployment states without
declared release or deployment intent.

Exceptional states are `BLOCKED_REQUIREMENT`, `BLOCKED_POLICY`,
`BLOCKED_TECHNICAL`, `HUMAN_DECISION_REQUIRED`, `ROLLBACK_REQUIRED`, and
`INCIDENT`. `lifecycle.yaml` defines every allowed transition, prerequisite,
failure state, and evidence output. Skipping states requires an explicit
workflow rule, such as reduced maintenance scope; it is never an agent shortcut.

Every exceptional state has a declared recovery: gather or clarify requirements,
change the request or obtain authorized policy change, apply a bounded technical
alternative, ingest a valid human response, execute verified rollback, or enter
the incident workflow. A state with no configured recovery is invalid and fails
control-plane validation.

Transitions are idempotent. The engine records policy version hashes and input
evidence hashes, preventing stale evidence from authorizing a changed diff or
deployment. Examples include requiring calculated risk and resolved
applicability before `PLANNED -> TASKED`, clean CI and review resolution before
`REVIEWING -> CONVERGING`, and release evidence, deployment authority, verified
rollback, and readiness before `RELEASE_READY -> DEPLOYING`.

### Change detection and selective invalidation

Every decision binds to base commit, head commit, normalized diff hash,
control-plane hash, project-profile hash, feature-context hash, dependency-lock
hash, deployment-manifest hash, exception-set hash, and target-environment
identity. Non-applicable inputs use an explicit `not_applicable`, never an empty
or omitted value.

`lifecycle.yaml` defines the decision dependency graph. Input changes invalidate
only dependent evidence:

- a documentation-only diff change invalidates validation, review, and
  convergence, but not an unchanged architecture decision;
- a feature-context or material-fact change invalidates classification and all
  downstream decisions;
- a control-plane change activates `instruction_system_change`, is evaluated
  under the trusted revision, and invalidates classification onward;
- a dependency-lock change invalidates dependency classification, risk,
  security evidence, tests, review, and later decisions;
- a deployment target or manifest change invalidates production readiness,
  deployment authority, release readiness, deployment, and verification;
- an exception-set change invalidates every gate that consumed an exception.

The engine refuses a transition backed by stale decision hashes and reports the
smallest evidence set that must be regenerated.

### Clarification triage

Clarifications have three policy classes:

- `inferable`: resolve from specs, code, tests, ADRs, schemas, telemetry, or
  established conventions and record evidence;
- `reversible_default`: apply a configured, bounded default and record the
  choice and reversal path;
- `material_business`: enter `HUMAN_DECISION_REQUIRED` with an escalation
  packet because alternatives materially affect user experience, commercial
  outcome, legal obligation, data use, public behavior, cost, or irreversible
  architecture.

Unresolved markers block implementation only when the triage result or missing
evidence requires it. The agent may not label a material ambiguity inferable to
avoid escalation.

### Policy-resolved exceptions

Low-risk exceptions may be autonomous for at most 30 days when they have a
rationale, owner, remediation issue, automated expiry, and no security-boundary
or regulatory effect. Moderate exceptions may be autonomous for at most 14 days
when compensating controls and follow-up tasks exist and there is no regulatory
impact. High exceptions require human authority. Critical exceptions are
prohibited. The engine fails expired exceptions automatically and recomputes
the affected transition.

### Context-separated review and repair

Review uses distinct roles: builder, correctness reviewer, security reviewer,
test-adequacy reviewer, spec-convergence reviewer, and release reviewer. A role
may be fulfilled by a separate agent session, isolated prompt, model, static
tool, or combination. Reviewer context contains the approved artifacts, final
diff, tests, and policies but not the builder's conclusions.

Findings conform to `evidence-schema.yaml` and include stable ID, category,
severity, confidence, location, violated rule, evidence, and required
resolution. The builder repairs actionable findings and reruns affected gates.
The loop continues until findings are resolved or excepted, the configured
iteration/cost limit creates `BLOCKED_TECHNICAL`, or policy triggers
`HUMAN_DECISION_REQUIRED`. High-risk work requires all enhanced review roles.

### Resource and cost bounds

`resource-policy.yaml` owns maximum repair iterations, model or token spend,
CI reruns, sandbox or infrastructure cost, elapsed workflow duration, retry
backoff, external API attempts, and escalation thresholds. The reusable baseline
permits three review/repair cycles, two CI reruns per unchanged commit, and three
reconciled external-action attempts with bounded exponential backoff. Paid
infrastructure, unbounded external API use, and production spend remain zero or
disabled until project initialization provides explicit limits.

Exhaustion enters `BLOCKED_TECHNICAL` when a different deterministic strategy
remains possible, `BLOCKED_POLICY` when the requested work exceeds configured
authority, or `HUMAN_DECISION_REQUIRED` when increasing a financial or resource
limit requires irreducible authority. The engine records consumption and never
resets a counter merely because an agent session restarts.

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

Spec Kit stages feed the lifecycle state machine; they do not replace it.
`checklist`, `analyze`, and `converge` outputs are transition evidence.

## Policy Corrections

- Required CI on the exact reviewed merge candidate is authoritative for merge;
  local checks remain required pre-PR evidence.
- Production is never a test target. Unit, contract, integration, end-to-end,
  sandbox, and production verification have explicit boundaries.
- Behavioral and risk-based coverage replaces a unit-test-per-function rule.
- Percentage coverage is a floor, supplemented by acceptance-criteria,
  changed-code, contract, schema, migration, and risk coverage.
- Security findings may be fixed or governed by a policy-authorized, expiring
  exception with compensating controls; high-risk residual security acceptance
  requires human authority and critical residual risk is prohibited by default.
- Direct-to-main remains prohibited by default, with controlled break-glass and
  incident restoration procedures.
- Brownfield specifications govern intended behavior; code, telemetry, data,
  and consumer contracts are evidence of actual behavior that must be
  reconciled before behavior changes.

## Validation and Error Handling

`scripts/validate-instructions.sh` verifies required files, the root line limit,
YAML parsing, cross-control-plane references, required lifecycle language, local
Markdown links, profile validity, non-overlapping risk thresholds, complete
authority matrices, deny-overrides precedence, trusted-policy self-governance,
formal schemas, lifecycle paths and recovery, invalidation dependencies,
resource bounds, and mandatory autonomy, solo/regulated, and CI statements.
Without the Python runtime dependencies, it performs reduced structural
diagnostics and warns that policy execution is unavailable.

`scripts/validate-feature-context.sh <feature-directory>` verifies Spec Kit
artifacts, the Instruction Context declaration, classifications, loaded modules,
risk and readiness levels, not-applicable rationales, clarification markers,
and classification-specific module dependencies.

`scripts/policy-engine.py` provides `classify`, `authorize`, `transition`,
`check-exceptions`, `compare-policy`, `validate-evidence`, `reconcile-action`,
and `ingest-decision` operations. Successful results are machine-readable and
include trusted and proposed control-plane hashes. Invalid or incomplete input
fails closed with a mapped exceptional state and actionable errors.

Validators use actionable `ERROR`, `WARNING`, and success messages and return a
non-zero status on failure. They do not modify the repository.

## Verification Strategy

- Run the instruction-system validator on the completed repository.
- Check `CLAUDE.md` with `wc -l`.
- Run `bash -n scripts/validate-instructions.sh` and
  `bash -n scripts/validate-feature-context.sh`.
- Run `python3 -m py_compile scripts/policy-engine.py` and its unit tests.
- Unit-test dimensional risk aggregation, group caps, subsumption, cross-domain
  escalation, automatic critical overrides, fact provenance and corroboration,
  contradictory facts, additive routes, deny-overrides authority, exception
  expiry, transition prerequisites, selective invalidation, stale evidence,
  resource exhaustion, and escalation-packet completeness.
- Run table-driven end-to-end fixtures for low, moderate, high, and critical
  delivery scenarios.
- Exercise feature-context validation against temporary valid and invalid
  fixtures.
- Deliberately test missing files, unresolved clarification markers, and missing
  classification-required modules using temporary copies.
- Review all local links, manifest paths, profile names, duplicate rules,
  authority statements, and solo/regulated interactions.
- Confirm low-risk routes avoid unrelated production or compliance artifacts.
- Confirm high-risk routes activate security, operations, evidence, and review
  controls.
- Confirm remote actions are disabled in the reusable default and become
  autonomous only through explicit scoped configuration.
- Confirm every human-required outcome cites its authority rule and produces a
  complete bounded decision packet.
- Confirm prohibited outcomes cannot be converted into autonomous actions by an
  exception record.
- Confirm trusted branch-base policy evaluates proposed instruction-system
  changes and a proposal cannot authorize its own weakening.
- Confirm repeated external-action requests reconcile state and do not create
  duplicate side effects.
- Confirm a human response cannot be replayed against changed evidence or
  policy.
- Confirm JSON Schemas reject malformed control-plane and evidence records.

## Git and Publication

The workspace is initialized from the existing private GitHub repository
`nealsolves/spec-driven-dev`. Its `main` branch and Apache 2.0 `LICENSE` are
preserved. Work will be committed with Conventional Commit messages and pushed
to that repository only after applicable validation and review gates pass.
The active implementation branch is `feat/001-modular-instruction-system`.

## Acceptance

The implementation is accepted when every deliverable in the source brief
exists, scripts are executable, positive validation passes, deliberate negative
checks fail actionably, and the executable control plane produces deterministic
and auditable decisions for classification, risk, authority, transitions,
exceptions, and evidence. `CLAUDE.md` must remain no more than 350 lines, no fake
feature directory may exist, no repository commands may be invented, and the
final report must list placeholders and any deliberate deviations.

The acceptance suite must also prove:

1. A proposed policy weakening cannot authorize itself.
2. Deny-overrides selects the most restrictive applicable result.
3. An unconfigured repository cannot mutate remotes or production.
4. Maintenance succeeds without an active feature.
5. Correlated risk factors do not cause unintended tier inflation.
6. Material false or unknown facts without required provenance fail closed.
7. Changed inputs selectively invalidate prior decisions.
8. Repeated external-action requests do not duplicate side effects.
9. Human decisions cannot be replayed against changed context.
10. Every normal state has a valid path to completion.
11. Every exceptional state has deterministic remediation or escalation.
12. Resource limits stop runaway autonomous loops.
13. Policy-engine changes are evaluated by the trusted prior revision.
14. Formal schemas reject malformed control-plane records.
