# Modular Autonomous Delivery MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the approved practical MVP: a compact modular instruction system backed by four validated policy files and a deterministic local policy engine.

**Architecture:** `CLAUDE.md` is the durable behavioral kernel, focused Markdown files provide detailed guidance, and four YAML files form the machine-readable control plane. A single Python CLI validates configuration and context, evaluates classification/risk/authority, checks lifecycle transitions, and processes bounded human responses; one shell validator is authoritative and a second script is a compatibility wrapper.

**Tech Stack:** Markdown, YAML 1.2, JSON Schema Draft 2020-12, Bash 3.2+, Python 3.11+, PyYAML 6.x, jsonschema 4.x, standard-library `unittest`.

## Global Constraints

- Root `CLAUDE.md` must contain no more than 350 physical lines measured by `wc -l CLAUDE.md`.
- Version 1 has exactly four control files: `.claude/project.yaml`, `.claude/routing.yaml`, `.claude/policy.yaml`, and `.claude/lifecycle.yaml`.
- Version 1 has exactly four formal schemas: project, routing, policy, and context.
- The public engine interface is exactly `validate`, `evaluate`, `transition`, and `respond`.
- The reusable template is solo-capable but starts with lifecycle `unconfigured`; remote and production actions are disabled.
- Risk uses highest inherent tier, explicit escalation modifiers, and automatic critical overrides—no weights or dimensional aggregation.
- Evidence freshness uses `policy_hash`, `context_hash`, and `change_hash` only.
- Ordinary facts need one strong source; corroboration applies only to configured high-risk negative claims.
- Post-bootstrap instruction-system changes are `human_required` in MVP.
- Phase 2 and Deferred capabilities in the approved design are not implementation tasks or MVP acceptance requirements.
- Do not invent application install, test, lint, typecheck, build, deployment, or release commands.
- Do not create a fake `specs/<NNN>-<feature>` directory or live evidence records.
- Preserve `LICENSE`, the approved design, and the untracked `docs/superpowers/specs/2026-07-20-modular-instruction-system-design_original.md`.
- Never stage `.DS_Store` files; add them to `.gitignore` without deleting user files.
- Use test-first cycles, actionable errors, small commits, and no hidden chain-of-thought evidence.

## File Map

### Runtime and configuration

- `.claude/project.yaml` — unconfigured project identity, commands, environments, overlays, and remote/production permissions.
- `.claude/routing.yaml` — fact catalog, workflow selection, classification rules, and additive module routes.
- `.claude/policy.yaml` — simple risk tiers, authority, precedence, clarifications, exceptions, reviews, and resource limits.
- `.claude/lifecycle.yaml` — states, transitions, evidence prerequisites, recoveries, and terminal paths.
- `.claude/schemas/*.schema.json` — four validation contracts.
- `scripts/policy-engine.py` — pure policy functions and four-command CLI.
- `scripts/validate-instructions.sh` — authoritative repository validator.
- `scripts/validate-feature-context.sh` — thin compatibility wrapper.
- `requirements-policy.txt` — bounded runtime dependency ranges.

### Guidance and reusable artifacts

- `CLAUDE.md` — compact instruction kernel and router.
- `.claude/README.md` — operating guide and old-to-new manifest mapping.
- `.claude/rules/*.md` — twelve focused domain modules.
- `.claude/workflows/*.md` — nine focused workflows, including initialization and instruction-system changes.
- `.claude/profiles/*.md` — solo, team, prototype, and regulated overlay.
- `.claude/templates/*.md` — the eleven evidence templates required by the source brief.
- `.specify/memory/constitution.md` — substantive starter constitution.
- `implementation_status.md` — repository status template.

### Tests

- `tests/helpers.py` — load the hyphenated engine module and create temporary repositories.
- `tests/test_control_plane_contracts.py` — required files and JSON Schema validation.
- `tests/test_policy_evaluate.py` — facts, routes, risk, authority, precedence, clarifications, exceptions, and resources.
- `tests/test_policy_lifecycle.py` — transitions, three-hash freshness, terminal paths, and responses.
- `tests/test_instruction_structure.py` — root limit, links, required modules, and Markdown contracts.
- `tests/fixtures/contexts/*.yaml` — valid and negative table-driven contexts.

---

### Task 1: Establish the four-file control-plane contracts

**Files:**
- Create: `.gitignore`
- Create: `requirements-policy.txt`
- Create: `.claude/project.yaml`
- Create: `.claude/routing.yaml`
- Create: `.claude/policy.yaml`
- Create: `.claude/lifecycle.yaml`
- Create: `.claude/schemas/project.schema.json`
- Create: `.claude/schemas/routing.schema.json`
- Create: `.claude/schemas/policy.schema.json`
- Create: `.claude/schemas/context.schema.json`
- Create: `tests/test_control_plane_contracts.py`

**Interfaces:**
- Consumes: Approved design sections “Consolidated control plane,” “Formal schemas,” “Simple Risk Determination,” and “Lifecycle.”
- Produces: Four schema-valid dictionaries consumed by `load_control_plane(root: Path) -> dict[str, Any]` in Task 2.

- [ ] **Step 1: Add dependency and ignore contracts**

Create `.gitignore`:

```gitignore
.worktrees/
.DS_Store
.venv/
__pycache__/
*.py[cod]
```

Create `requirements-policy.txt`:

```text
PyYAML>=6.0,<7
jsonschema>=4.23,<5
```

- [ ] **Step 2: Install runtime dependencies in a disposable virtual environment**

Run:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-policy.txt
```

Expected: PyYAML 6.x and jsonschema 4.x install successfully. If network access
is blocked, request authorization; do not substitute an ad hoc parser.

- [ ] **Step 3: Create the failing control-plane contract test**

```python
# tests/test_control_plane_contracts.py
import json
import unittest
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
PAIRS = {
    "project": (".claude/project.yaml", ".claude/schemas/project.schema.json"),
    "routing": (".claude/routing.yaml", ".claude/schemas/routing.schema.json"),
    "policy": (".claude/policy.yaml", ".claude/schemas/policy.schema.json"),
    "lifecycle": (".claude/lifecycle.yaml", ".claude/schemas/policy.schema.json"),
}

class ControlPlaneContractsTest(unittest.TestCase):
    def test_required_control_files_exist(self):
        for data_path, schema_path in PAIRS.values():
            self.assertTrue((ROOT / data_path).is_file(), data_path)
            self.assertTrue((ROOT / schema_path).is_file(), schema_path)

    def test_yaml_is_schema_valid(self):
        schema_map = {
            "project": "project.schema.json",
            "routing": "routing.schema.json",
            "policy": "policy.schema.json",
            "lifecycle": "policy.schema.json",
        }
        for name, (data_path, _) in PAIRS.items():
            data = yaml.safe_load((ROOT / data_path).read_text())
            schema = json.loads((ROOT / ".claude/schemas" / schema_map[name]).read_text())
            if name == "lifecycle":
                schema = schema["$defs"]["lifecycle"]
            jsonschema.Draft202012Validator(schema).validate(data)

    def test_unconfigured_defaults_are_safe(self):
        project = yaml.safe_load((ROOT / ".claude/project.yaml").read_text())
        self.assertEqual(project["project"]["lifecycle"], "unconfigured")
        self.assertFalse(project["remote_actions"]["enabled"])
        self.assertFalse(project["production_actions"]["enabled"])

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 4: Run the test and observe the missing-file failure**

Run:

```bash
python3 -m unittest tests.test_control_plane_contracts -v
```

Expected: FAIL listing `.claude/project.yaml` as missing.

- [ ] **Step 5: Create the four YAML control files with these exact top-level contracts**

Create `.claude/project.yaml`:

```yaml
schema_version: 1
control_plane_version: 1
project:
  name: <product>
  repository: <owner/repository>
  lifecycle: unconfigured
delivery:
  base_profile: solo
  overlays: []
  owner: <name>
  escalation_owner: <email-or-handle>
spec_kit:
  enabled: true
  design_reference: v0.13.0
  tested_version: unknown
  minimum_version: unknown
  allow_equivalent_manual_gates: true
commands:
  install: unknown
  test: unknown
  lint: unknown
  typecheck: unknown
  build: unknown
  release: unknown
data:
  classifications: [unknown]
  regulated_data: unknown
  production_data_in_nonproduction: prohibited
environments:
  configured: []
remote_actions:
  enabled: false
  repository: unknown
  push_branch: false
  open_pull_request: false
  update_pull_request: false
  merge_pull_request: false
  create_release: false
production_actions:
  enabled: false
  target: unknown
  deploy: false
  rollback: false
financial_limits:
  currency: unknown
  autonomous_spend: 0
external_obligations: []
```

Create `.claude/routing.yaml` with:

```yaml
schema_version: 1
always:
  rules: [rules/engineering.md, rules/testing.md, rules/documentation.md]
facts:
  documentation_only: {type: boolean, material: false}
  modifies_runtime_code: {type: boolean, material: false}
  modifies_authentication: {type: boolean, material: true, corroborate_when_false: true}
  modifies_authorization: {type: boolean, material: true, corroborate_when_false: true}
  reads_customer_data: {type: boolean, material: true}
  writes_customer_data: {type: boolean, material: true}
  changes_public_contract: {type: boolean, material: true}
  changes_database_schema: {type: boolean, material: true}
  irreversible_migration: {type: boolean, material: true, corroborate_when_false: true}
  changes_infrastructure: {type: boolean, material: true}
  adds_external_dependency: {type: boolean, material: false}
  uses_llm: {type: boolean, material: true}
  deploys_to_production: {type: boolean, material: true}
  destructive_production_action: {type: boolean, material: true}
  credential_exposure: {type: boolean, material: true}
  unsupported_regulatory_exception: {type: boolean, material: true}
  unbounded_financial_commitment: {type: boolean, material: true}
  instruction_system_change: {type: boolean, material: true}
workflow_rules:
  project_initialization: workflows/project-initialization.md
  feature: workflows/feature-development.md
  bug_fix: workflows/bug-fix.md
  brownfield: workflows/brownfield-change.md
  maintenance: workflows/maintenance.md
  dependency: workflows/dependency-update.md
  instruction_system: workflows/instruction-system-change.md
  release: workflows/release.md
  incident: workflows/incident-hotfix.md
classification_rules:
  - {fact: documentation_only, equals: true, add: [documentation_only]}
  - {fact: modifies_runtime_code, equals: true, add: [feature]}
  - {fact: modifies_authentication, equals: true, add: [security_sensitive]}
  - {fact: modifies_authorization, equals: true, add: [security_sensitive]}
  - {fact: reads_customer_data, equals: true, add: [data_sensitive]}
  - {fact: writes_customer_data, equals: true, add: [data_sensitive]}
  - {fact: changes_public_contract, equals: true, add: [public_contract_change]}
  - {fact: changes_database_schema, equals: true, add: [data_sensitive, production_impact]}
  - {fact: changes_infrastructure, equals: true, add: [architecture_change, production_impact]}
  - {fact: adds_external_dependency, equals: true, add: [dependency_change]}
  - {fact: uses_llm, equals: true, add: [ai_system_change]}
  - {fact: deploys_to_production, equals: true, add: [production_impact, observability_impact, release]}
  - {fact: destructive_production_action, equals: true, add: [production_impact, release]}
  - {fact: credential_exposure, equals: true, add: [security_sensitive, incident_hotfix]}
  - {fact: unsupported_regulatory_exception, equals: true, add: [regulated_scope]}
  - {fact: instruction_system_change, equals: true, add: [instruction_system_change]}
routes:
  documentation_only: {workflows: [workflows/maintenance.md], rules: []}
  feature: {workflows: [workflows/feature-development.md], rules: [rules/architecture.md]}
  bug_fix: {workflows: [workflows/bug-fix.md], rules: []}
  brownfield_behavior_change: {workflows: [workflows/brownfield-change.md], rules: [rules/architecture.md]}
  dependency_change: {workflows: [workflows/dependency-update.md], rules: [rules/security.md, rules/release-management.md]}
  architecture_change: {rules: [rules/architecture.md, rules/security.md, rules/production-readiness.md, rules/observability.md]}
  security_sensitive: {rules: [rules/security.md, rules/testing.md]}
  data_sensitive: {rules: [rules/data-privacy.md, rules/security.md]}
  production_impact: {rules: [rules/production-readiness.md, rules/observability.md, rules/release-management.md]}
  observability_impact: {rules: [rules/observability.md]}
  public_contract_change: {rules: [rules/architecture.md, rules/testing.md, rules/release-management.md]}
  ai_system_change: {rules: [rules/ai-systems.md, rules/security.md, rules/data-privacy.md, rules/observability.md]}
  release: {workflows: [workflows/release.md], rules: [rules/release-management.md, rules/production-readiness.md, rules/observability.md]}
  incident_hotfix: {workflows: [workflows/incident-hotfix.md], rules: [rules/security.md, rules/production-readiness.md, rules/observability.md, rules/release-management.md]}
  regulated_scope: {rules: [rules/compliance.md, rules/ownership.md]}
  instruction_system_change: {workflows: [workflows/instruction-system-change.md], rules: [rules/security.md, rules/documentation.md]}
```

Create `.claude/policy.yaml`:

```yaml
schema_version: 1
risk:
  tiers: [low, moderate, high, critical]
  factors:
    documentation_only: low
    modifies_runtime_code: moderate
    reads_customer_data: moderate
    adds_external_dependency: moderate
    uses_llm: moderate
    writes_customer_data: high
    modifies_authentication: high
    modifies_authorization: high
    changes_public_contract: high
    changes_infrastructure: high
    irreversible_migration: critical
    destructive_production_action: critical
  escalation:
    - id: customer_write_external
      when_all: [writes_customer_data, adds_external_dependency]
      raise_by: 1
    - id: authorization_in_production
      when_all: [modifies_authorization, deploys_to_production]
      minimum: high
  automatic_critical: [credential_exposure, unsupported_regulatory_exception, unbounded_financial_commitment]
authority:
  outcomes: [autonomous, autonomous_with_enhanced_gates, human_required, prohibited]
  source_precedence: [external_obligation, constitution, regulated_overlay, project, base_profile, workflow]
  actions:
    local_implementation: {low: autonomous, moderate: autonomous, high: autonomous_with_enhanced_gates, critical: human_required}
    push_branch: {low: autonomous, moderate: autonomous, high: autonomous_with_enhanced_gates, critical: human_required}
    open_pull_request: {low: autonomous, moderate: autonomous, high: autonomous_with_enhanced_gates, critical: human_required}
    merge_pull_request: {low: autonomous, moderate: autonomous, high: autonomous_with_enhanced_gates, critical: human_required}
    create_release: {low: autonomous, moderate: autonomous, high: human_required, critical: prohibited}
    deploy_production: {low: autonomous, moderate: autonomous_with_enhanced_gates, high: human_required, critical: prohibited}
    risk_exception: {low: autonomous, moderate: autonomous_with_enhanced_gates, high: human_required, critical: prohibited}
    instruction_system_change: {low: human_required, moderate: human_required, high: human_required, critical: human_required}
clarifications:
  inferable: resolve_and_record
  reversible_default: apply_configured_default
  material_business: human_required
exceptions:
  low: {allowed: true, autonomous: true, max_duration_days: 30, required: [rationale, owner, remediation_task, expires_at, no_security_boundary_impact, no_regulatory_impact]}
  moderate: {allowed: true, autonomous: true, max_duration_days: 14, required: [rationale, owner, compensating_control, follow_up_task, expires_at, no_regulatory_impact]}
  high: {allowed: true, autonomous: false, outcome: human_required}
  critical: {allowed: false, autonomous: false, outcome: prohibited}
reviews:
  low: [combined_engineering]
  moderate: [general_engineering]
  high: [correctness, security, test_adequacy, convergence]
  critical: []
resources:
  max_repair_cycles: 3
  max_ci_reruns_per_change: 2
  max_elapsed_minutes: 120
  retry_backoff_seconds: [1, 5, 15]
```

Create `.claude/lifecycle.yaml`:

```yaml
schema_version: 1
normal_states: [UNCLASSIFIED, CLASSIFIED, SPECIFIED, CLARIFIED, PLANNED, TASKED, ANALYZED, IMPLEMENTING, VALIDATING, REVIEWING, CONVERGING, RELEASE_READY, DEPLOYING, VERIFYING, COMPLETE]
exceptional_states: [BLOCKED_REQUIREMENT, BLOCKED_POLICY, BLOCKED_TECHNICAL, HUMAN_DECISION_REQUIRED, ROLLBACK_REQUIRED, INCIDENT]
paths:
  code: [UNCLASSIFIED, CLASSIFIED, SPECIFIED, CLARIFIED, PLANNED, TASKED, ANALYZED, IMPLEMENTING, VALIDATING, REVIEWING, CONVERGING, COMPLETE]
  release: [UNCLASSIFIED, CLASSIFIED, SPECIFIED, CLARIFIED, PLANNED, TASKED, ANALYZED, IMPLEMENTING, VALIDATING, REVIEWING, CONVERGING, RELEASE_READY, COMPLETE]
  deployment: [UNCLASSIFIED, CLASSIFIED, SPECIFIED, CLARIFIED, PLANNED, TASKED, ANALYZED, IMPLEMENTING, VALIDATING, REVIEWING, CONVERGING, RELEASE_READY, DEPLOYING, VERIFYING, COMPLETE]
  maintenance: [UNCLASSIFIED, CLASSIFIED, VALIDATING, REVIEWING, COMPLETE]
transitions:
  - {from: UNCLASSIFIED, to: CLASSIFIED, requires: [evaluation_passed]}
  - {from: CLASSIFIED, to: SPECIFIED, requires: [spec_complete]}
  - {from: SPECIFIED, to: CLARIFIED, requires: [material_clarifications_resolved]}
  - {from: CLARIFIED, to: PLANNED, requires: [plan_complete, instruction_context_valid]}
  - {from: PLANNED, to: TASKED, requires: [tasks_trace_to_acceptance]}
  - {from: TASKED, to: ANALYZED, requires: [artifact_analysis_clean]}
  - {from: ANALYZED, to: IMPLEMENTING, requires: [implementation_authorized]}
  - {from: IMPLEMENTING, to: VALIDATING, requires: [implementation_tasks_complete]}
  - {from: CLASSIFIED, to: VALIDATING, requires: [maintenance_scope_recorded]}
  - {from: VALIDATING, to: REVIEWING, requires: [local_validation_passed]}
  - {from: REVIEWING, to: CONVERGING, requires: [required_reviews_passed, required_ci_passed]}
  - {from: REVIEWING, to: COMPLETE, requires: [required_reviews_passed, required_ci_passed]}
  - {from: CONVERGING, to: COMPLETE, requires: [convergence_passed]}
  - {from: CONVERGING, to: RELEASE_READY, requires: [convergence_passed, release_evidence_complete]}
  - {from: RELEASE_READY, to: COMPLETE, requires: [release_artifact_verified]}
  - {from: RELEASE_READY, to: DEPLOYING, requires: [deployment_authorized, rollback_verified]}
  - {from: DEPLOYING, to: VERIFYING, requires: [deployment_observed]}
  - {from: VERIFYING, to: COMPLETE, requires: [production_verification_passed]}
recoveries:
  BLOCKED_REQUIREMENT: gather_evidence_or_clarify
  BLOCKED_POLICY: change_request_or_authorized_policy
  BLOCKED_TECHNICAL: bounded_retry_or_alternative
  HUMAN_DECISION_REQUIRED: validated_response
  ROLLBACK_REQUIRED: execute_verified_rollback
  INCIDENT: incident_hotfix_workflow
```

- [ ] **Step 6: Create the four JSON Schemas**

Use Draft 2020-12, `additionalProperties: false` at control-plane object boundaries, string enums for tiers/outcomes/states, and `$defs` for reusable path lists, fact records, rules, context facts, findings, exceptions, escalation packets, and responses. `policy.schema.json` must expose `$defs.lifecycle` so the Task 1 test validates `.claude/lifecycle.yaml` without adding a fifth schema.

- [ ] **Step 7: Run the control-plane contract test**

Run:

```bash
.venv/bin/python -m unittest tests.test_control_plane_contracts -v
```

Expected: 3 tests PASS.

- [ ] **Step 8: Commit the contract**

```bash
git add .gitignore requirements-policy.txt .claude/project.yaml .claude/routing.yaml .claude/policy.yaml .claude/lifecycle.yaml .claude/schemas tests/test_control_plane_contracts.py
git commit -m "feat(policy): define MVP control-plane contracts"
```

---

### Task 2: Implement validation and canonical hashing

**Files:**
- Create: `scripts/policy-engine.py`
- Create: `tests/helpers.py`
- Create: `tests/test_policy_validate.py`

**Interfaces:**
- Consumes: Four YAML files and four schemas from Task 1.
- Produces: `load_control_plane(root: Path) -> dict[str, Any]`, `validate_bundle(root: Path, context_path: Path | None) -> list[str]`, and `canonical_hash(value: Any) -> str`.

- [ ] **Step 1: Write failing validation and hash tests**

Test that `canonical_hash({"b": 2, "a": 1})` equals the hash of `{"a": 1, "b": 2}`, that all four control files validate, that an unknown top-level key fails, and that `validate --root .` returns JSON with `valid: true`.

Use this loader in `tests/helpers.py`:

```python
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load_engine():
    spec = importlib.util.spec_from_file_location("policy_engine", ROOT / "scripts/policy-engine.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module
```

- [ ] **Step 2: Run the tests and observe the missing-engine failure**

```bash
.venv/bin/python -m unittest tests.test_policy_validate -v
```

Expected: FAIL because `scripts/policy-engine.py` does not exist.

- [ ] **Step 3: Implement the validation core**

The engine must:

```python
CONTROL_FILES = {
    "project": ".claude/project.yaml",
    "routing": ".claude/routing.yaml",
    "policy": ".claude/policy.yaml",
    "lifecycle": ".claude/lifecycle.yaml",
}

SCHEMA_FILES = {
    "project": ".claude/schemas/project.schema.json",
    "routing": ".claude/schemas/routing.schema.json",
    "policy": ".claude/schemas/policy.schema.json",
    "context": ".claude/schemas/context.schema.json",
}

def canonical_hash(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
```

Implement safe YAML loading, JSON Schema validation, duplicate/unknown route reference checks, required Markdown path checks, lifecycle reachability, and context validation. Return errors as stable strings prefixed `ERROR:`; never print tracebacks for user input failures.

- [ ] **Step 4: Implement the `validate` CLI**

Use `argparse` with:

```text
policy-engine.py validate --root PATH [--context PATH]
```

Write one JSON object to stdout. Exit `0` with `{"valid": true, ...}` and exit `1` with `{"valid": false, "errors": [...]}`.

- [ ] **Step 5: Run focused tests**

```bash
.venv/bin/python -m unittest tests.test_policy_validate -v
```

Expected: all validation/hash tests PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/policy-engine.py tests/helpers.py tests/test_policy_validate.py
git commit -m "feat(policy): validate control plane and contexts"
```

---

### Task 3: Implement deterministic evaluation

**Files:**
- Modify: `scripts/policy-engine.py`
- Create: `tests/test_policy_evaluate.py`
- Create: `tests/fixtures/contexts/maintenance-low.yaml`
- Create: `tests/fixtures/contexts/authorization-high.yaml`
- Create: `tests/fixtures/contexts/critical-migration.yaml`
- Create: `tests/fixtures/contexts/material-unknown.yaml`

**Interfaces:**
- Consumes: `load_control_plane`, validated context, policy tier/outcome ordering.
- Produces: `evaluate(bundle: dict, context: dict) -> dict` containing classifications, modules, workflows, risk, authority, clarifications, exceptions, resources, and three hashes.

Every fixture uses this context shape; omit only fields marked optional by
`context.schema.json`:

```yaml
schema_version: 1
change_id: maintenance-001
workflow_family: maintenance
action: local_implementation
current_state: UNCLASSIFIED
change_hash: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
facts:
  documentation_only:
    value: true
    source_type: diff_analysis
    source_ref: tests/fixtures/evidence/docs-diff.json
    extractor: repository-fact-extractor-v1
    confidence: 1.0
    observed_at_change: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
    corroboration: []
clarifications: []
exceptions: []
authority_constraints: []
evidence: {}
resources:
  repair_attempts: 0
  ci_reruns: 0
open_escalation: null
responses: []
```

Create each referenced evidence file under `tests/fixtures/evidence/`.

- [ ] **Step 1: Write failing table-driven evaluation tests**

Cover these exact outcomes:

```python
CASES = [
    ("maintenance-low.yaml", ["documentation_only"], "low", "autonomous"),
    ("authorization-high.yaml", ["security_sensitive", "production_impact"], "high", "autonomous_with_enhanced_gates"),
    ("critical-migration.yaml", ["data_sensitive", "production_impact"], "critical", "prohibited"),
]
```

Also test additive module de-duplication, unknown material fact rejection,
selective corroboration for a negative authorization claim, automatic critical
override, remote-disabled project precedence, exception expiry, clarification
triage, repair limit exhaustion, and outcome ordering.

- [ ] **Step 2: Run and observe failure**

```bash
.venv/bin/python -m unittest tests.test_policy_evaluate -v
```

Expected: FAIL because `evaluate` is undefined.

- [ ] **Step 3: Implement fact validation and additive routing**

Reject unknown fact names, invalid values, stale `observed_at_change`, missing
source references, contradictions, and missing corroboration only when the fact
catalog sets `corroborate_when_false: true`. Apply every matching
classification rule, then load `always.rules` plus every routed rule/workflow,
preserving manifest order while removing duplicates.

- [ ] **Step 4: Implement simple risk**

Select the maximum inherent tier using the configured tier order. Apply each
matching `raise_by` or `minimum` escalation once. Apply automatic critical facts
last. Emit:

```python
{
    "tier": "high",
    "inherent_factors": [{"fact": "modifies_authorization", "tier": "high"}],
    "modifiers": [{"rule": "authorization_in_production", "minimum": "high"}],
    "critical_overrides": [],
}
```

- [ ] **Step 5: Implement authority, clarifications, exceptions, and resources**

Collect outcomes from project safe defaults, action matrix, external/regulated
constraints in context, risk exceptions, and resource exhaustion. Select the
most restrictive by configured order. `instruction_system_change: true` must be
`human_required` after bootstrap. Expired exceptions fail; critical exceptions
are prohibited. Inferable clarifications resolve, reversible defaults apply the
configured choice, and material-business clarifications produce an escalation
packet.

- [ ] **Step 6: Add the three hashes**

`policy_hash` covers the four control files plus four schemas. `context_hash`
covers the validated context excluding generated decisions and responses.
`change_hash` comes from the context and is required. Store all three in every
decision record.

- [ ] **Step 7: Implement the `evaluate` CLI and run tests**

```text
policy-engine.py evaluate --root PATH --context PATH [--output PATH]
```

Without `--output`, write JSON to stdout. With `--output`, write the same
newline-terminated JSON and print only the output path.

```bash
.venv/bin/python -m unittest tests.test_policy_evaluate -v
```

Expected: all evaluation tests PASS.

- [ ] **Step 8: Commit**

```bash
git add scripts/policy-engine.py tests/test_policy_evaluate.py tests/fixtures/contexts
git commit -m "feat(policy): evaluate routing risk and authority"
```

---

### Task 4: Implement lifecycle transitions and bounded responses

**Files:**
- Modify: `scripts/policy-engine.py`
- Create: `tests/test_policy_lifecycle.py`
- Create: `tests/fixtures/contexts/escalation-open.yaml`
- Create: `tests/fixtures/contexts/response-option-2.yaml`

**Interfaces:**
- Consumes: current context, current decision record, lifecycle transitions, evidence flags.
- Produces: `transition(bundle, context, decision, target_state) -> dict` and `respond(bundle, context, response) -> dict`.

- [ ] **Step 1: Write failing lifecycle tests**

Test valid maintenance completion, invalid state skipping, missing evidence,
each of the code/release/deployment/maintenance terminal paths, exceptional-state
recovery presence, policy/context/change hash mismatch, response decision-ID
mismatch, invalid option, and successful option 2 response followed by
reevaluation.

- [ ] **Step 2: Run and observe failure**

```bash
.venv/bin/python -m unittest tests.test_policy_lifecycle -v
```

Expected: FAIL because `transition` and `respond` are undefined.

- [ ] **Step 3: Implement transition checks**

Find exactly one transition matching current/target state and active workflow.
Require every configured evidence key to be truthy. Recompute and compare all
three hashes. Return a new decision record; do not mutate input dictionaries or
silently write the source context.

- [ ] **Step 4: Implement response processing**

Require response keys `decision_id`, `selected_option`, `decided_by`,
`authority_basis`, `timestamp`, and `hashes`. Verify the packet is open, option
exists, hashes match, and action is not prohibited. Add the selected conditions
to a copy of context, mark the packet resolved, and call `evaluate` again.

- [ ] **Step 5: Implement CLIs**

```text
policy-engine.py transition --root PATH --context PATH --decision PATH --to STATE [--output PATH]
policy-engine.py respond --root PATH --context PATH --response PATH [--output PATH]
```

- [ ] **Step 6: Run lifecycle tests**

```bash
.venv/bin/python -m unittest tests.test_policy_lifecycle -v
```

Expected: all lifecycle/response tests PASS.

- [ ] **Step 7: Commit**

```bash
git add scripts/policy-engine.py tests/test_policy_lifecycle.py tests/fixtures/contexts
git commit -m "feat(policy): enforce lifecycle and responses"
```

---

### Task 5: Rewrite the compact root kernel and operating guide

**Files:**
- Modify: `CLAUDE.md`
- Create: `.claude/README.md`
- Create: `.specify/memory/constitution.md`
- Create: `implementation_status.md`
- Create: `tests/test_instruction_structure.py`

**Interfaces:**
- Consumes: four control files, approved authority/lifecycle doctrine.
- Produces: startup/router contract and durable sources of truth used by all modules.

- [ ] **Step 1: Write failing structure tests**

Assert root line count ≤350; headings for purpose, project identity, authority,
startup, invariants, lifecycle, routing, Git/PR/CI, exceptions, escalation, and
done; all lifecycle terms; exact CI-authoritative statement; links to the four
control files and `.claude/README.md`; no claim that status alone resolves the
feature; constitution exists; status contains all seven required states.

- [ ] **Step 2: Run and observe failures against the old root contract**

```bash
.venv/bin/python -m unittest tests.test_instruction_structure -v
```

- [ ] **Step 3: Rewrite `CLAUDE.md` as the kernel**

Use this authority hierarchy: external law/contract, constitution, approved
active artifacts, active project policy/modules, root kernel, implementation/
telemetry/data/consumer behavior as actual-state evidence, then conventional
practice. Add workflow-first/conditional-feature resolution, lifecycle,
universal invariants, deterministic routing, remote-safe defaults, human
escalation packet contract, exceptions, PR/CI minimums, and definition of done.
Keep detailed engineering/testing/security rules out of the root and link to
loaded modules. State that required CI on the exact merge candidate is
authoritative for merge.

- [ ] **Step 4: Create `.claude/README.md`**

Document the three layers, startup sequence, the four-file control plane,
schema/engine commands, project initialization, feature and maintenance context,
MVP/Phase 2/Deferred boundary, Spec Kit v0.13.0 design reference, and mapping:

```text
instructions.yaml + classification-rules.yaml -> routing.yaml
project-profile.yaml                           -> project.yaml
authority/risk/exception/resource policy       -> policy.yaml
evidence requirements + state transitions      -> lifecycle.yaml + context schema
```

- [ ] **Step 5: Create constitution and status templates**

The constitution must define autonomy-within-authority, spec-driven intent,
test-first evidence, security/privacy boundaries, deterministic policy,
reversible delivery, and amendment discipline. `implementation_status.md` must
include active change/branch/profile, open PRs, current gate, deliverables,
risks, deferred items, last verified main commit, last deployment, and the seven
states: not started, in progress, in review, merged, deployed, blocked, deferred.

- [ ] **Step 6: Run tests and commit**

```bash
.venv/bin/python -m unittest tests.test_instruction_structure -v
wc -l CLAUDE.md
git add CLAUDE.md .claude/README.md .specify/memory/constitution.md implementation_status.md tests/test_instruction_structure.py
git commit -m "docs(kernel): add autonomous instruction router"
```

Expected: structure tests PASS; root line count ≤350.

---

### Task 6: Add the twelve focused rule modules

**Files:**
- Create: `.claude/rules/engineering.md`
- Create: `.claude/rules/testing.md`
- Create: `.claude/rules/security.md`
- Create: `.claude/rules/architecture.md`
- Create: `.claude/rules/data-privacy.md`
- Create: `.claude/rules/production-readiness.md`
- Create: `.claude/rules/observability.md`
- Create: `.claude/rules/release-management.md`
- Create: `.claude/rules/compliance.md`
- Create: `.claude/rules/ownership.md`
- Create: `.claude/rules/ai-systems.md`
- Create: `.claude/rules/documentation.md`
- Modify: `tests/test_instruction_structure.py`

**Interfaces:**
- Consumes: route paths in `.claude/routing.yaml`.
- Produces: every mandatory routed rule file with a consistent evidence contract.

- [ ] **Step 1: Extend the failing structure test**

For every rule, assert these headings: Purpose, Applicability, Required inputs,
Mandatory controls, Evidence, Exceptions, Solo interpretation, Overlay notes,
and Completion checklist. Assert the topic lists in Steps 3–14 appear in their
owning files and no file claims template existence proves compliance.

- [ ] **Step 2: Run and observe missing-module failures**

```bash
.venv/bin/python -m unittest tests.test_instruction_structure -v
```

- [ ] **Step 3: Create `engineering.md`**

Cover reversible changes, strict tooling, boundary validation, typed errors,
dependency/configuration discipline, structured logging, unsafe casts,
complexity, generated code, branch/commit/PR traceability, brownfield
compatibility, and correctness/maintainability/regression/concurrency/
performance/contract review capabilities with tool-equivalent fallbacks.

- [ ] **Step 4: Create `testing.md`**

Cover red-before-green where practical, characterization tests, unit/contract/
integration/end-to-end/sandbox/production boundaries, acceptance and contract
mapping, schemas/migrations/rollback, snapshots, changed-code and risk coverage,
determinism, flaky tests, and performance/resilience triggers. Explicitly reject
unit-tests-for-every-function and live-production-test rules.

- [ ] **Step 5: Create `security.md`**

Cover threat triggers, trust boundaries, validation, authN/authZ, least
privilege, secrets, SSRF/injection/traversal/deserialization, crypto,
dependencies/actions, SAST/dependency/secret scans, SBOM/provenance/signing,
container/IaC triggers, findings/exceptions, access/break-glass, and high-risk
solo adversarial review.

- [ ] **Step 6: Create `architecture.md`**

Cover ADR triggers, simplicity, technology selection, buy/build/adopt,
service/module/data boundaries, API/event compatibility, versioning,
dependency direction, failures, resilience, capacity, cost, reversibility,
brownfield reconciliation, and diagram proportionality.

- [ ] **Step 7: Create `data-privacy.md`**

Cover classification, minimization, purpose, retention/deletion, encryption,
access/audit, masking, residency, production-data restrictions, test data, PII
logging, privacy assessment, processors, AI data, and data-flow evidence.

- [ ] **Step 8: Create `production-readiness.md`**

Define levels 0–3 and proportional controls for environments, IaC,
configuration, migrations, compatibility, flags, health, deployment, rollback,
backup, capacity, recovery, runbooks, ownership, verification, monitoring,
decommissioning, and break-glass.

- [ ] **Step 9: Create `observability.md`**

Differentiate minor feature, critical journey, new service, and regulated flow;
cover logs, metrics, traces, correlation, audit events, SLI/SLO/error budgets,
dashboards, alerts, ownership, cost/cardinality, retention, redaction, testing,
and production verification.

- [ ] **Step 10: Create `release-management.md`**

Cover versioning, changelog/notes, policy authority, exact-commit CI, artifacts,
SBOM/provenance/signing, promotion, compatibility, migrations, progressive
delivery, rollback criteria, emergency release, validation, deprecation, and
release evidence.

- [ ] **Step 11: Create `compliance.md`**

Make it framework-neutral and profile-driven; cover declared control profiles,
requirement mapping, evidence, owners, exceptions/compensation, retention,
revalidation, external authority, example frameworks, and a prohibition on
template-based compliance claims.

- [ ] **Step 12: Create `ownership.md`**

Define product, architecture, development, review, security, data, release,
operations, and risk roles; explain solo collapse, team separation, AI advisory
status, policy-bounded autonomy, and regulated overrides.

- [ ] **Step 13: Create `ai-systems.md`**

Cover model/provider approval, prompt/version tracking, injection, tool
authorization, output validation, retention/training, cost/retries, evaluations,
goldens, hallucination handling, human authority, fallbacks, observability,
safety/abuse, reproducibility, and regional/vendor limits.

- [ ] **Step 14: Create `documentation.md`**

Cover documentation as done, decision/API/operations synchronization, runbooks,
generated docs, status, link-not-copy, durable versus volatile information,
Markdown quality, and broken links.

- [ ] **Step 15: Run tests and commit**

```bash
.venv/bin/python -m unittest tests.test_instruction_structure -v
git add .claude/rules tests/test_instruction_structure.py
git commit -m "docs(rules): add proportional delivery controls"
```

---

### Task 7: Add workflows, profiles, and reusable evidence templates

**Files:**
- Create: `.claude/workflows/project-initialization.md`
- Create: `.claude/workflows/instruction-system-change.md`
- Create: `.claude/workflows/feature-development.md`
- Create: `.claude/workflows/bug-fix.md`
- Create: `.claude/workflows/maintenance.md`
- Create: `.claude/workflows/dependency-update.md`
- Create: `.claude/workflows/brownfield-change.md`
- Create: `.claude/workflows/release.md`
- Create: `.claude/workflows/incident-hotfix.md`
- Create: `.claude/profiles/solo-developer.md`
- Create: `.claude/profiles/team.md`
- Create: `.claude/profiles/regulated.md`
- Create: `.claude/profiles/prototype.md`
- Create: `.claude/templates/feature-instruction-context.md`
- Create: `.claude/templates/adr-template.md`
- Create: `.claude/templates/threat-model-template.md`
- Create: `.claude/templates/privacy-assessment-template.md`
- Create: `.claude/templates/production-readiness-template.md`
- Create: `.claude/templates/observability-plan-template.md`
- Create: `.claude/templates/compliance-mapping-template.md`
- Create: `.claude/templates/risk-exception-template.md`
- Create: `.claude/templates/release-readiness-template.md`
- Create: `.claude/templates/incident-record-template.md`
- Create: `.claude/templates/maintenance-record-template.md`
- Modify: `tests/test_instruction_structure.py`

**Interfaces:**
- Consumes: lifecycle states, policy decisions, routed module names.
- Produces: deterministic human-readable procedures and evidence forms.

- [ ] **Step 1: Extend failing structure tests**

Assert every workflow has Entry criteria, Artifacts, Gates, Ordered steps,
Evidence, Exit criteria, Solo mode, and Stop/escalation conditions. Assert every
profile and template exists and contains the fields named in Steps 3–26. Assert
`regulated.md` says it may override solo allowances.

- [ ] **Step 2: Run and observe missing-file failures**

```bash
.venv/bin/python -m unittest tests.test_instruction_structure -v
```

- [ ] **Step 3: Create `project-initialization.md`**

Collect/derive every project field, preserve unknowns, validate the four files,
and prohibit remote/production actions and autonomous exceptions until the
configured profile passes.

- [ ] **Step 4: Create `instruction-system-change.md`**

Detect kernel/control/schema/module/engine/validator changes, require
`human_required` after the explicitly recorded bootstrap, validate before/after
files, and forbid the proposed policy from authorizing itself.

- [ ] **Step 5: Create `feature-development.md`**

Use constitution → specify → clarify → plan → checklist → tasks → analyze →
implement → converge, require context/evidence at each state, and route
material ambiguities through an escalation packet.

- [ ] **Step 6: Create `bug-fix.md`**

Distinguish simple regression, behavior clarification, security defect, and
incident follow-up; require a regression or characterization test and risk
reevaluation.

- [ ] **Step 7: Create `maintenance.md`**

Cover documentation, formatting, rename, non-behavioral refactor, and hygiene;
use a maintenance ID and reduced lifecycle without skipping validation/review.

- [ ] **Step 8: Create `dependency-update.md`**

Require reason, delta, changelog/security/license review, compatibility tests,
lockfile review, and rollback for major/runtime-critical changes.

- [ ] **Step 9: Create `brownfield-change.md`**

Require actual-behavior discovery, characterization tests, consumer impact,
telemetry/data evidence, spec reconciliation, and migration/deprecation.

- [ ] **Step 10: Create `release.md`**

Require release readiness, exact-commit CI, authority evaluation, rollback,
monitoring, and verification; note external execution is Phase 2.

- [ ] **Step 11: Create `incident-hotfix.md`**

Define stabilize-first, smallest safe change, explicit reduced gates, no silent
bypass, incident record, regression test, spec updates, restoration, and root
cause follow-up.

- [ ] **Step 12: Create `solo-developer.md`**

Allow one person to hold all roles; retain automated gates, risk-bounded review,
written exceptions, repeatable deployment, audit trail, optional separate-model
challenge, and no default second-human count.

- [ ] **Step 13: Create `team.md`**

Define CODEOWNERS, high-risk author/approver separation, path-sensitive
security/data/platform review, release authority, and emergency authority.

- [ ] **Step 14: Create `regulated.md`**

Make it an overlay with external control mapping, evidence retention, required
approvers, segregation overrides, exception authority, auditability, and no
unsupported certification claim.

- [ ] **Step 15: Create `prototype.md`**

Require non-production designation, no real regulated data, no production
secrets, no implied readiness, and explicit promotion exit criteria.

- [ ] **Step 16: Create `feature-instruction-context.md`**

Include profile/overlays/classifications, observable facts, risk, authority,
readiness/data/control profiles, policy/context/change hashes, lifecycle state,
loaded-module checklist, not-applicable table, evidence table, clarifications,
exceptions, and escalation status.

- [ ] **Step 17: Create `adr-template.md`**

Include title/status/date, context, decision, alternatives, consequences,
security/privacy, operations, cost, migration/reversal, and references.

- [ ] **Step 18: Create `threat-model-template.md`**

Include scope, assets, actors, trust boundaries, data flows, threats,
mitigations, residual risk, verification, and owner.

- [ ] **Step 19: Create `privacy-assessment-template.md`**

Include categories, purpose, collection, storage, retention, access,
processors/sharing, residency, deletion, non-production, logging, AI use, risks,
and controls.

- [ ] **Step 20: Create `production-readiness-template.md`**

Include level, environments, dependencies, configuration, migrations,
deployment, rollback, health, capacity, backups, recovery, runbooks, ownership,
verification, and residual risk.

- [ ] **Step 21: Create `observability-plan-template.md`**

Include journeys, SLIs, SLO/rationale, logs, metrics, traces, audit events,
dashboards, alerts, ownership, redaction, retention, cost/cardinality, and
verification.

- [ ] **Step 22: Create `compliance-mapping-template.md`**

Include control profile, requirement, implementation, evidence, owner, status,
exception, and revalidation date.

- [ ] **Step 23: Create `risk-exception-template.md`**

Include waived requirement, rationale, scope, tier, impact, compensation, owner,
policy authority, expiration, remediation/follow-up, and issue/PR/spec links.

- [ ] **Step 24: Create `release-readiness-template.md`**

Include version, scope, CI commit, artifacts, SBOM/provenance/signing,
compatibility, migrations, deployment, rollback, monitoring, authority, and
verification.

- [ ] **Step 25: Create `incident-record-template.md`**

Include timeline, impact, detection, containment, recovery, root cause,
contributors, corrective actions, regression tests, spec changes, and owner.

- [ ] **Step 26: Create `maintenance-record-template.md`**

Include change type/ID, scope, behavior impact, facts, risk, activated modules,
validation/review evidence, rollback, hashes, authority, and PR link.

- [ ] **Step 27: Run tests and commit**

```bash
.venv/bin/python -m unittest tests.test_instruction_structure -v
git add .claude/workflows .claude/profiles .claude/templates tests/test_instruction_structure.py
git commit -m "docs(workflows): add autonomous delivery playbooks"
```

---

### Task 8: Add the authoritative validator and negative fixtures

**Files:**
- Create: `scripts/validate-instructions.sh`
- Create: `scripts/validate-feature-context.sh`
- Create: `tests/test_validator_cli.py`

**Interfaces:**
- Consumes: `policy-engine validate`, completed Markdown structure, and root contract requirements.
- Produces: portable shell entry points with actionable exit status.

- [ ] **Step 1: Write failing CLI integration tests**

Use temporary copies to assert success on the repository, failure on a missing
rule, failure when `CLAUDE.md` exceeds 350 lines, failure on a broken local link,
failure on unsafe project defaults, and feature-context validation through the
compatibility wrapper.

- [ ] **Step 2: Run and observe missing-script failure**

```bash
.venv/bin/python -m unittest tests.test_validator_cli -v
```

- [ ] **Step 3: Implement the primary validator**

Start with:

```bash
#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
PYTHON="${POLICY_PYTHON:-$ROOT/.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then PYTHON="$(command -v python3 || true)"; fi
```

Check Python availability, call `policy-engine.py validate --root "$ROOT"`,
check the root line limit, required lifecycle terms, required CI-authoritative
wording, local Markdown links, all required modules/templates/profiles, script
executable bits, solo one-person wording, and regulated override wording. Print
`ERROR:`, `WARNING:`, and one final success line. Exit non-zero on any error.

- [ ] **Step 4: Implement the thin compatibility wrapper**

```bash
#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
if [[ $# -ne 1 ]]; then
  echo "Usage: scripts/validate-feature-context.sh <feature-directory>" >&2
  exit 2
fi
exec "$ROOT/scripts/validate-instructions.sh" --context "$1/instruction-context.yaml"
```

Add `--context` forwarding to the primary validator.

- [ ] **Step 5: Mark scripts executable and run tests**

```bash
chmod +x scripts/validate-instructions.sh scripts/validate-feature-context.sh scripts/policy-engine.py
.venv/bin/python -m unittest tests.test_validator_cli -v
```

Expected: integration tests PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts tests/test_validator_cli.py
git commit -m "feat(validation): enforce instruction contracts"
```

---

### Task 9: Run the complete MVP acceptance suite and synchronize evidence

**Files:**
- Modify: `implementation_status.md`
- Modify: `.claude/README.md` only if validation reveals a documented mismatch
- Modify: tests only to correct a proven contract mistake, never to weaken acceptance

**Interfaces:**
- Consumes: all previous tasks.
- Produces: a validated, reviewable MVP and accurate repository status.

- [ ] **Step 1: Run syntax and unit verification**

```bash
bash -n scripts/validate-instructions.sh
bash -n scripts/validate-feature-context.sh
.venv/bin/python -m py_compile scripts/policy-engine.py
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

Expected: all commands exit 0; all tests PASS.

- [ ] **Step 2: Run repository acceptance validation**

```bash
bash scripts/validate-instructions.sh
wc -l CLAUDE.md
git diff --check
```

Expected: validator success; `CLAUDE.md` ≤350; no whitespace errors.

- [ ] **Step 3: Exercise deliberate negative cases through tests**

Confirm tests prove missing files, malformed YAML/schema, material unknown fact,
uncorroborated high-risk negative claim, critical override, deny-overrides,
unsafe unconfigured remote action, invalid transition, stale policy/context/change
hash, replayed response, exhausted repair loop, broken link, and overlong root
contract all fail with actionable errors.

- [ ] **Step 4: Perform consistency review**

Check source hierarchy, control-file/schema references, route paths, lifecycle
reachability, safe defaults, solo/regulated compatibility, low-risk
proportionality, named-tool fallbacks, no live production tests, no invented
repository commands, no unsupported compliance/readiness claims, and no Phase 2
code or acceptance leakage.

- [ ] **Step 5: Update status without false claims**

Mark the implementation deliverables “In review,” not “Merged” or “Deployed.”
Record validation commands and results, remaining owner placeholders, current
branch, active solo/unconfigured profile, and no production deployment.

- [ ] **Step 6: Commit final MVP evidence**

```bash
git add .claude .specify CLAUDE.md implementation_status.md requirements-policy.txt scripts tests .gitignore
git commit -m "chore(validation): verify autonomous delivery MVP"
```

- [ ] **Step 7: Run final clean-tree verification**

```bash
bash scripts/validate-instructions.sh
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
git status --short --branch
```

Expected: validation/tests PASS. Only intentionally untracked user files, if
any, remain; `.DS_Store` is ignored. Do not merge or deploy.

---

## Post-Implementation Review Checkpoints

1. Correctness review: engine behavior, schema validation, and CLI exit codes.
2. Security review: safe YAML parsing, no `eval`, path containment, fail-closed
   unknowns, safe default authority, and no secret-bearing fixtures.
3. Test adequacy review: all sixteen MVP acceptance criteria map to tests.
4. Spec convergence review: implementation matches the approved phased design
   and contains no Phase 2 or Deferred execution framework.
5. Publication review: pushing, PR creation, and merge remain governed by the
   explicit user request and repository authority; no autonomous merge occurs
   while the template is unconfigured.
