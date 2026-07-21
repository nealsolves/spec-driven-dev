# Autonomous Spec-Driven Delivery Template

A reusable repository template for policy-driven software delivery with
deterministic routing, explicit authority boundaries, and human intervention
reserved for decisions automation cannot safely make.

The template is safe by default. Creating a repository from it does not make
that repository production-ready or grant an agent permission to publish,
release, or deploy changes.

## What this template provides

- A compact [behavioral kernel](CLAUDE.md) that defines startup, authority,
  lifecycle, escalation, and completion rules.
- Modular rules, workflows, profiles, and evidence templates under
  [`.claude/`](.claude/README.md).
- Four machine-readable control files for project identity, routing, policy,
  and lifecycle decisions.
- Four JSON Schemas and a local policy engine for deterministic validation and
  evaluation.
- Safe project defaults that allow local design, implementation, testing, and
  review while remote and production actions remain disabled.
- Compatibility with specification-driven workflows without requiring a
  hosted governance service, database, daemon, or vendor deployment adapter.

Use this template when you want an agent to automate routine engineering work
while escalating only material business, legal, financial, security, or
production-risk decisions.

## Quick start

1. On GitHub, select **Use this template**, then **Create a new repository**.
2. Choose the owner, repository name, visibility, and default branch for the
   new project.
3. Clone the newly created repository and install the policy runtime:

```bash
git clone https://github.com/<your-account>/<your-repository>.git
cd <your-repository>
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-policy.txt
bash scripts/validate-instructions.sh
```

The final command should report that instruction-system validation passed. A
repository-only warning is expected until you supply a live feature or
maintenance context.

Windows PowerShell users can activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

## Initialize the project policy

Before enabling publication or production actions, replace the placeholders
and explicit `unknown` values in [`.claude/project.yaml`](.claude/project.yaml)
with facts supported by repository or owner evidence.

Configure these areas in order:

1. **Project identity** — name, GitHub repository, and intended lifecycle.
2. **Ownership** — delivery owner, escalation owner, base profile, and any
   regulated overlay.
3. **Repository commands** — derive install, test, lint, type-check, build, and
   release commands from real project configuration. Use `not_applicable` only
   when a command genuinely does not exist and that conclusion is recorded.
4. **Data and environments** — identify data classifications, regulatory
   posture, allowed environments, and production-data restrictions.
5. **Spec Kit compatibility** — record tested and minimum versions when it is
   enabled, or explicitly disable it when it does not apply.
6. **Remote and production authority** — keep permissions off until the exact
   repository, target, deployment mechanism, rollback mechanism, and financial
   bounds have been verified.
7. **Lifecycle** — change the project from `unconfigured` to `configured` only
   after the complete profile validates.

Application-specific commands must come from the instantiated repository. Do
not invent plausible install, test, release, deployment, or rollback commands
to satisfy initialization.

Follow the detailed
[project-initialization workflow](.claude/workflows/project-initialization.md)
for its gates, evidence, and stop conditions.

## Validate the template

Run the primary validator after every control-plane or instruction change:

```bash
bash scripts/validate-instructions.sh
```

Useful direct checks are:

```bash
.venv/bin/python scripts/policy-engine.py validate --root .
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

To validate a feature or maintenance context as well:

```bash
.venv/bin/python scripts/policy-engine.py validate \
  --root . \
  --context path/to/instruction-context.yaml
```

Missing dependencies or malformed policy are technical blocks. Do not replace
the engine with an agent's subjective interpretation.

## Start delivery work

For a feature:

1. Record the intent and choose the feature workflow.
2. Create an instruction context from the
   [feature context template](.claude/templates/feature-instruction-context.md).
3. Attach repository evidence to each observable fact.
4. Run policy evaluation to derive classifications, risk, authority, modules,
   workflows, and evidence hashes.
5. Follow the returned workflow and load every activated module.
6. Implement, validate, review, repair, and converge until the lifecycle gate
   permits completion or produces a bounded escalation packet.

Documentation, dependency hygiene, repository setup, and similar reduced-scope
work can use the [maintenance workflow](.claude/workflows/maintenance.md)
without creating a fake feature directory. Maintenance work still records
facts, risk, authority, validation, and review evidence.

## Authority and safe defaults

The reusable repository starts with:

- `project.lifecycle: unconfigured`;
- remote actions disabled;
- production actions disabled;
- application commands, owners, data posture, and environments explicitly
  unresolved rather than guessed.

The policy engine returns one of four authority outcomes:

| Outcome | Meaning |
|---|---|
| `autonomous` | The action may proceed when its lifecycle prerequisites pass. |
| `autonomous_with_enhanced_gates` | The action may proceed only after the additional policy-selected reviews or controls pass. |
| `human_required` | Automation must stop and produce a bounded decision packet for an authorized person. |
| `prohibited` | The action cannot proceed through an ordinary approval or exception. |

The most restrictive applicable outcome wins. A project-level permission cannot
weaken a constitutional, legal, contractual, regulated, or prohibited result.

Human approval is an exception, not a routine lifecycle stage. The agent should
resolve inferable engineering decisions and reversible defaults from evidence,
then escalate only genuinely material or authority-bound decisions.

## Agent and Spec Kit compatibility

This repository is **Claude-first**: its primary instruction entry point is
[`CLAUDE.md`](CLAUDE.md), with detailed guidance and controls under `.claude/`.
Another coding agent can use the template only when it reads and follows those
same files; compatibility is not universal or automatic.

[GitHub Spec Kit](https://github.com/github/spec-kit) is an optional compatible
workflow reference for specification-driven development. It is not bundled,
installed, or automatically compatibility-tested by this template. The default
project profile therefore keeps its tested and minimum Spec Kit versions as
`unknown` until project initialization verifies them.

Equivalent manual artifacts and gates are allowed when a repository does not
install Spec Kit or an installed version lacks a referenced command.

## Repository map

```text
CLAUDE.md                         Behavioral kernel and normative startup contract
.claude/
├── README.md                    Detailed operating guide
├── project.yaml                 Identity, ownership, environments, and permissions
├── routing.yaml                 Facts, classifications, workflows, and modules
├── policy.yaml                  Risk, authority, exceptions, and resource limits
├── lifecycle.yaml               States, transitions, recoveries, and terminal paths
├── schemas/                     Four JSON Schema contracts
├── rules/                       Focused engineering and assurance guidance
├── workflows/                   Initialization, delivery, maintenance, and release flows
├── profiles/                    Solo, team, prototype, and regulated profiles
└── templates/                   Context and evidence forms
.specify/memory/constitution.md  Non-negotiable governing principles
scripts/policy-engine.py         Four-command deterministic policy CLI
scripts/validate-instructions.sh Primary repository validator
requirements-policy.txt         Bounded policy-runtime dependencies
tests/                           Executable contracts and regression tests
```

The [operating guide](.claude/README.md) explains how these pieces interact.

## Delivery scope

### MVP

The current practical core provides deterministic classification, simple
four-tier risk, deny-overrides authority, lifecycle transitions, clarification
triage, bounded repair and escalation, evidence freshness, formal schemas, and
safe defaults. It evaluates remote, release, and deployment authority but does
not execute those actions through vendor-specific adapters.

### Phase 2

After real-project use justifies it, Phase 2 may add autonomous PR, merge,
release, and deployment execution; targeted idempotency; stronger human identity
checks; production-readiness integration; and focused policy-change comparison.

### Deferred

Advanced assurance remains Deferred until observed failures justify it,
including granular invalidation, per-record schemas, dimensional risk,
full external-action reconciliation, universal multi-agent orchestration, and
general policy-version migration.

## Detailed guidance

- [Behavioral kernel](CLAUDE.md)
- [Modular delivery operating guide](.claude/README.md)
- [Project initialization workflow](.claude/workflows/project-initialization.md)
- [Delivery constitution](.specify/memory/constitution.md)
- [Approved autonomous-delivery design](docs/superpowers/specs/2026-07-20-modular-instruction-system-design.md)
- [README guidance design](docs/superpowers/specs/2026-07-20-readme-guidance-design.md)

The README is an onboarding layer. If it conflicts with the behavioral kernel
or validated control plane, those normative sources take precedence.
