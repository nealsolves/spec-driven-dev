# Modular Autonomous Delivery System Design

## Status

The architecture and phased boundary are approved for MVP implementation. This
revision defines a practical Version 1 and explicitly defers operational
orchestration and advanced assurance until real-project experience justifies
them.

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
| Deterministic engineering | Resolve automatically and record evidence. |
| Policy-bounded risk | Resolve within configured thresholds and record evidence. |
| Irreducible authority | Generate a bounded decision packet and require human action. |

Irreducible authority includes changing material business intent, accepting
legal or contractual risk, exceeding an approved financial limit, overriding
regulatory segregation, introducing a new sensitive-data use, accepting
critical residual security risk, and authorizing an irreversible destructive
production operation.

## Context

The repository begins with an Apache 2.0 license and a 264-line `CLAUDE.md`. It
has no application source, CI configuration, Spec Kit artifacts, feature
directories, or repository-specific development commands. The result must
remain a reusable template and must not invent project facts.

The source implementation brief requires a compact root contract,
deterministic progressive disclosure, proportional controls, solo-developer
compatibility, complete Markdown modules and templates, status tracking, and
executable validation. Later review extended that goal to a policy-driven
autonomous delivery control plane. This design implements the smallest useful
intersection of those requirements first.

## Goals

- Keep root `CLAUDE.md` at or below 350 physical lines, preferably 250–320.
- Separate the compact behavioral kernel from detailed Markdown guidance.
- Derive classifications, risk, authority, modules, and lifecycle transitions
  from machine-readable policy.
- Support a solo owner without routine approval ceremonies.
- Escalate only precise business, legal, financial, regulatory, security, or
  destructive-production decisions that exceed configured authority.
- Keep Version 1 small enough to understand, test, and tune on real projects.
- Align with Spec Kit v0.13.0 as a design reference without claiming tested
  compatibility in an uninstantiated repository.

## Practical Implementation Boundary

Version 1 is a local CLI and file format, not a governance platform or hosted
workflow service. It consists of:

- one compact root contract;
- focused Markdown rules, workflows, profiles, and evidence templates;
- four YAML control-plane files;
- four JSON Schemas;
- one Python policy engine with four commands;
- one primary validator and a thin compatibility wrapper;
- file-based feature or maintenance context;
- unit and table-driven fixture tests.

It uses no daemon, database, message queue, plugin framework, schema generator,
custom rules language, or vendor-specific release/deployment adapter. Policy
conditions are explicit data structures—never embedded code or `eval`.

## Phased Delivery Boundary

### MVP — Practical autonomous core

The first implementation includes:

- compact `CLAUDE.md` and modular Markdown guidance;
- safe project initialization;
- observable facts and deterministic classification;
- simple four-tier risk evaluation;
- authority evaluation and deny-overrides;
- lifecycle transitions and terminal paths;
- clarification triage;
- bounded risk-based review and repair;
- structured escalation packets and basic responses;
- unconfigured-safe defaults;
- three-hash evidence freshness;
- formal validation and focused acceptance fixtures.

### Phase 2 — Operational autonomy

Phase 2 is documented but not implemented until the MVP has processed several
real features. It may add:

- autonomous PR creation, updating, and merge;
- release and deployment execution authority;
- targeted idempotency for PR creation, merge, release, deployment, and
  rollback;
- production-readiness integration;
- stronger human identity/authority verification for responses;
- table-based trusted-policy weakening detection;
- targeted evidence invalidation where full resets prove expensive.

### Deferred — Advanced assurance

These features require observed failure modes or maintenance pain before work
begins:

- granular dependency-graph invalidation;
- separate schemas for every evidence type;
- dimensional or weighted risk aggregation;
- repository-wide formal corroboration policies;
- full external-action reconciliation;
- universal multi-agent review orchestration;
- general semantic policy comparison;
- sophisticated policy-version migration.

Deferred features are not placeholders in MVP code and are not MVP acceptance
requirements.

## Version 1 Architecture

### Root behavioral kernel

`CLAUDE.md` contains only durable, universal material:

- purpose, scope, and unconfigured project identity;
- authority hierarchy and intended-versus-actual behavior;
- startup protocol and conditional feature resolution;
- universal invariants;
- Spec Kit lifecycle and gates;
- deterministic routing summary;
- universal Git, PR, and CI rules;
- escalation contract;
- exceptions and definition of done;
- links to detailed modules and workflows.

Activated modules are mandatory. Detailed controls are linked rather than
copied. Required CI on the exact reviewed merge candidate is authoritative for
merge; local checks remain required pre-PR evidence.

### Markdown guidance layer

The required rule modules remain focused on engineering, testing, security,
architecture, data privacy, production readiness, observability, release,
compliance, ownership, AI systems, and documentation.

Workflows cover project initialization, instruction-system change, features,
bugs, maintenance, dependency updates, brownfield changes, releases, and
incident hotfixes. Profiles cover solo, team, prototype, and regulated overlay
behavior. The reusable evidence templates from the source brief remain complete
but do not create live feature or evidence instances.

Each rule module states purpose, applicability, required inputs, mandatory
controls, evidence, exceptions, solo interpretation, overlay notes, and a short
completion checklist. Each workflow states entry criteria, artifacts, gates,
ordered steps, evidence, exit criteria, and stop conditions.

### Consolidated control plane

Version 1 uses four YAML files:

```text
.claude/
├── project.yaml
├── routing.yaml
├── policy.yaml
└── lifecycle.yaml
```

`project.yaml` contains project identity, lifecycle, environments, base profile,
overlays, data posture, known repository commands, escalation owner, financial
limits, and remote/production permissions.

`routing.yaml` contains fact definitions, workflow-family rules, fact and action
classification rules, and additive classification-to-module mappings.

`policy.yaml` contains the risk model, authority matrix, exception rules,
resource limits, clarification policy, deny-overrides outcome precedence, and
policy-source precedence.

`lifecycle.yaml` contains states, allowed transitions, evidence prerequisites,
exceptional states, recovery paths, and terminal paths.

This consolidation supersedes the earlier separate `instructions.yaml`,
`project-profile.yaml`, authority, risk, classification, exception, evidence,
and resource manifests. `.claude/README.md` documents the compatibility mapping
and the final report records it as a deliberate design revision.

### Formal schemas

Version 1 uses four JSON Schema Draft 2020-12 files:

```text
.claude/schemas/
├── project.schema.json
├── routing.schema.json
├── policy.schema.json
└── context.schema.json
```

`context.schema.json` provides reusable definitions for facts, classifications,
risk decisions, findings, exceptions, lifecycle evidence, escalation packets,
and responses. Schemas are handwritten and narrow. They may split only when
independent evolution becomes a demonstrated problem.

### Context records

Feature work stores machine-readable context at
`specs/<NNN>-<feature>/instruction-context.yaml`, with a linked summary in
`plan.md`. Reduced-overhead work stores a maintenance record and context under
`evidence/maintenance/<change-id>/`.

The reusable repository provides templates only. It does not create a fake
feature directory or live evidence record.

### Policy engine

`scripts/policy-engine.py` exposes four commands:

```text
policy-engine validate
policy-engine evaluate
policy-engine transition
policy-engine respond
```

`validate` parses YAML, validates the four schemas, checks cross-references,
and validates a supplied context.

`evaluate` performs classification, risk determination, additive routing,
authority resolution, clarification policy, exception checks, and resource
checks. It emits one decision record.

`transition` checks lifecycle prerequisites against the current decision and
records an allowed state change.

`respond` validates a bounded human response against the open escalation packet
and current hashes, records the choice, and reevaluates the blocked decision.
Identity federation, digital signatures, and external authority directories are
Phase 2 concerns.

Policy comparison and external-action reconciliation remain internal or
deferred; they are not Version 1 public commands.

The engine uses Python, PyYAML, and `jsonschema`. Missing runtime dependencies
produce `BLOCKED_TECHNICAL`; the agent must not replace policy execution with
subjective routing.

## Startup and Workflow Selection

The agent performs these steps:

1. Read `CLAUDE.md` and the four control-plane files.
2. Determine the workflow family from intent.
3. Resolve a feature only when that workflow requires one; otherwise assign a
   stable maintenance/change ID.
4. Extract typed facts and attach repository evidence.
5. Run `policy-engine evaluate`.
6. Load always-on and derived Markdown modules and the selected workflow.
7. Record the decision and context summary.
8. Request the next lifecycle transition.
9. Proceed, run enhanced gates, repair, escalate, or stop according to policy.

Absence of an active feature does not block project initialization,
documentation, repository hygiene, dependency maintenance, or instruction-system
work.

## Project Initialization and Safe Defaults

The reusable template is solo-capable but unconfigured:

```yaml
project:
  lifecycle: unconfigured
remote_actions:
  enabled: false
production_actions:
  enabled: false
```

Until initialization passes, local specification, design, implementation,
testing, and review are allowed. Push, merge, release, deployment, and autonomous
risk exceptions are prohibited.

Changing lifecycle to `configured` fails unless project and repository identity,
owner and escalation owner, repository targets, and data posture are resolved.
Child permissions cannot be true while their parent switch is false. Enabled
production authority additionally requires a concrete configured target and
rollback permission. Validation and evaluation apply the same semantic gate.

`workflows/project-initialization.md` derives or collects project identity,
repository, lifecycle, environments, known install/test/lint/typecheck/build
commands, data classes, base authority, financial limits, production
permissions, overlays, deployment and rollback mechanisms, Spec Kit version,
escalation owner, and external obligations. Unknown values stay explicit; the
workflow never invents commands or permissions.

## Observable Facts and Classification

The agent extracts facts; code evaluates consequences. Each fact records:

```yaml
value: true | false | unknown
source_type: diff_analysis
source_ref: evidence/diff-analysis.json
extractor: repository-fact-extractor-v1
confidence: 0.96
observed_at_change: <change_hash>
```

One strong repository reference is sufficient for ordinary facts. Additional
corroboration is required only for configured high-risk negative claims, such
as no authorization impact, a reversible migration, or no customer-data
exposure. Material `unknown` values fail closed; the agent gathers more evidence
or applies clarification policy.

`routing.yaml` deterministically derives additive classifications. Examples:

```text
modifies_authorization -> security_sensitive
reads_customer_data -> data_sensitive
uses_llm -> ai_system_change
deploys_to_production -> production_impact + observability_impact + release
```

Action routes apply the same controls when release, production deployment, or
instruction-system authority is requested even if extracted facts are sparse.
They are additive and do not weaken contradiction checks on the facts.

Unknown fact names, stale evidence, invalid types, inadequate required
corroboration, and contradictory facts fail validation.

## Simple Risk Determination

Version 1 uses three steps:

1. Select the highest inherent tier among matched factors.
2. Apply explicit escalation modifiers or minimum tiers.
3. Apply automatic critical overrides.

Example policy:

```yaml
risk:
  factors:
    documentation_only: low
    runtime_behavior: moderate
    customer_data_read: moderate
    customer_data_write: high
    authentication_change: high
    authorization_change: high
    irreversible_migration: critical
    destructive_production_action: critical
  escalation:
    - when_all: [customer_data_write, external_integration]
      raise_by: 1
    - when_all: [authorization_change, production_deployment]
      minimum: high
  automatic_critical:
    - credential_exposure
    - unsupported_regulatory_exception
    - unbounded_financial_commitment
```

There are no weights, dimension caps, or subsumption rules in MVP. The decision
record lists the inherent factor, modifiers, overrides, and resulting tier so
owners can tune the model from real examples.

## Authority and Precedence

Authority outcomes are:

```text
autonomous
autonomous_with_enhanced_gates
human_required
prohibited
```

The most restrictive applicable outcome wins:

```text
prohibited > human_required > autonomous_with_enhanced_gates > autonomous
```

Policy sources are authoritative in this order:

```text
external legal or contractual constraint
> constitution
> regulated overlay
> project policy
> base profile
> workflow default
```

A lower source cannot weaken a higher source. The engine records all applicable
outcomes and the rule that selected the final result.

The unconfigured authority matrix permits local work but prohibits remote and
production actions. An instantiated profile may grant standing authority by
action and risk tier. Critical risk exceptions and configured prohibited actions
cannot be approved through an ordinary response.

## Instruction-System Changes

The initial installation is an explicit human-authorized bootstrap because no
trusted prior control plane exists. It installs remote-disabled and
production-disabled defaults.

During MVP, any later change to `CLAUDE.md`, the four control-plane files,
schemas, instruction modules, policy engine, or validators activates
`instruction_system_change` and requires a human decision. This simple rule
prevents the proposed policy from authorizing its own weakening without
implementing a premature semantic policy differ.

Phase 2 may replace this blanket gate with table-based comparison of explicit
sensitive changes, including less restrictive authority, reduced risk,
removed critical overrides, longer exceptions, higher resource limits, or newly
enabled remote/production actions. A general semantic differ remains deferred.

## Clarification Triage

Clarifications have three classes:

- `inferable`: resolve from repository evidence and record the source;
- `reversible_default`: apply a configured bounded default and record its
  reversal path;
- `material_business`: enter `HUMAN_DECISION_REQUIRED` with a decision packet.

Material business ambiguity includes choices that materially affect user
experience, commercial outcome, legal obligation, data use, public behavior,
cost, or irreversible architecture. The agent may not label a material choice
inferable merely to avoid escalation.

## Lifecycle

The full code-delivery spine is:

```text
UNCLASSIFIED -> CLASSIFIED -> SPECIFIED -> CLARIFIED -> PLANNED -> TASKED
-> ANALYZED -> IMPLEMENTING -> VALIDATING -> REVIEWING -> CONVERGING
```

The workflow and intent select a terminal path:

```text
Code delivered:   CONVERGING -> COMPLETE
Release artifact: CONVERGING -> RELEASE_READY -> COMPLETE
Deployment:       CONVERGING -> RELEASE_READY -> DEPLOYING
                  -> VERIFYING -> COMPLETE
Maintenance:      UNCLASSIFIED -> CLASSIFIED -> VALIDATING
                  -> REVIEWING -> COMPLETE
```

Exceptional states are `BLOCKED_REQUIREMENT`, `BLOCKED_POLICY`,
`BLOCKED_TECHNICAL`, `HUMAN_DECISION_REQUIRED`, `ROLLBACK_REQUIRED`, and
`INCIDENT`. Each has one declared recovery or escalation path. Release and
deployment states are evaluated in MVP but external execution is Phase 2.

The Spec Kit evidence lifecycle is:

```text
constitution -> specify -> clarify -> plan -> checklist -> tasks
             -> analyze -> implement -> converge
```

Commands and agent skills are preferred interfaces, not dependencies. If an
installed integration lacks `checklist` or `converge`, the agent creates the
equivalent artifact manually and records the fallback.

## Evidence Freshness

Version 1 binds decisions to three hashes:

- `policy_hash`: all control-plane configuration and schemas;
- `context_hash`: facts, intent, decisions, exceptions, and target;
- `change_hash`: relevant code and configuration diff.

Invalidation is intentionally coarse:

- a policy change invalidates all decisions;
- a context change invalidates classification and later decisions;
- a change hash update invalidates validation, review, convergence, release,
  and deployment evidence.

Granular dependency invalidation is deferred until full resets prove materially
expensive.

## Risk-Based Review and Repair

Review perspectives are policy-activated rather than universally instantiated:

- Low risk: one combined correctness, tests, and spec-alignment review.
- Moderate risk: general engineering review plus security/operations review
  only when triggered.
- High risk: separate correctness, security, test-adequacy, convergence, and
  release-readiness reviews when applicable.
- Critical risk: human authority or prohibition according to policy.

A reviewer receives approved artifacts, diff, tests, and policy, but not the
builder's conclusions. Findings have ID, category, severity, confidence,
location, violated rule, evidence, and required resolution. The builder repairs
actionable findings and reruns affected gates.

`policy.yaml` sets a small maximum repair count, CI rerun count, elapsed-time
limit, retry backoff, and optional cost ceiling. Version 1 defaults to three
repair cycles and two CI reruns per unchanged change hash. Exhaustion enters a
configured blocked or human-decision state; counters survive session restarts.

## Exceptions

Exception rules live in `policy.yaml`:

- low risk may be autonomous for up to 30 days with rationale, owner,
  remediation task, expiry, and no security-boundary or regulatory impact;
- moderate risk may be autonomous for up to 14 days with compensating controls,
  expiry, follow-up, and no regulatory impact;
- high risk requires human authority;
- critical exceptions are prohibited.

Expired exceptions fail automatically. MVP does not build an external exception
registry.

## Human Escalation and Response

An escalation packet contains:

- exact decision and open decision ID;
- policy trigger and why automation stopped;
- evidence already collected;
- bounded options and consequences;
- recommended option;
- required response format;
- current policy, context, and change hashes.

`policy-engine respond` accepts the decision ID and selected option, verifies
the open packet and hashes, records the response, incorporates stated
conditions, and reevaluates the blocked decision. It does not blindly resume or
accept a response against changed context.

Every final `human_required` result has exactly one bounded packet. Material
clarifications retain their business options; other authority gates offer a
single-use authorization scoped to the exact action, triggering rules, policy,
context, and change hashes. The recorded approval can suppress only those exact
`human_required` rules, applies enhanced gates, and cannot suppress a
`prohibited` result. Identity federation and signatures remain Phase 2.

## Validation

`scripts/validate-instructions.sh` is the primary validator. It calls
`policy-engine validate` and checks required files, schemas, cross-references,
root line count, local links, lifecycle reachability, deny-overrides, safe
defaults, required Markdown modules/templates, and executable permissions.

The source brief's `scripts/validate-feature-context.sh` remains only as a thin
compatibility wrapper around the same validation path; it contains no separate
policy logic.

Verification commands include:

```bash
bash -n scripts/validate-instructions.sh
bash -n scripts/validate-feature-context.sh
python3 -m py_compile scripts/policy-engine.py
python3 -m unittest discover -s tests -p 'test_*.py'
bash scripts/validate-instructions.sh
wc -l CLAUDE.md
```

## MVP Acceptance Criteria

1. Root `CLAUDE.md` is no more than 350 lines and local links resolve.
2. Required Markdown rules, workflows, profiles, templates, and status files
   exist without a fake feature directory.
3. Four control-plane files and four schemas parse and validate.
4. Ordinary facts route deterministically from one strong evidence source.
5. Configured high-risk negative claims require corroboration.
6. Material unknown or contradictory facts fail closed.
7. Simple risk factors, modifiers, and critical overrides produce expected
   table-driven outcomes.
8. Deny-overrides selects the most restrictive authority result.
9. An unconfigured repository cannot authorize remote or production actions,
   and an incompletely configured repository cannot activate them.
10. Feature and maintenance workflows both reach valid terminal states.
11. Clarifications resolve, default, or escalate according to policy.
12. Repair, CI retry, and elapsed-time limits stop runaway loops.
13. Material and generic authority escalation packets are complete, scoped, and
    responses cannot replay against changed hashes or override prohibition.
14. Policy, context, and change hashes invalidate the documented evidence.
15. Post-bootstrap instruction-system changes require human authority in MVP.
16. Required validation commands pass, and negative fixtures fail actionably.

Advanced Phase 2 and deferred behavior is not part of MVP acceptance.

## Git and Publication

The workspace uses the existing private GitHub repository
`nealsolves/spec-driven-dev`, preserving its `main` history and Apache 2.0
license. The active branch is `feat/001-modular-instruction-system`.

Work may be committed, pushed, submitted as a PR, and merged autonomously only
when the instantiated authority policy explicitly enables the action and the
applicable lifecycle gates pass. Until initialization, explicit user authority
is required for remote mutation. No merge, deployment, or compliance claim may
be made without verifiable evidence.
