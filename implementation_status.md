# Implementation Status

> This ledger describes capabilities derivable from tracked repository artifacts.
> It does not select the active change, record transient delivery coordinates, or
> replace fresh command evidence.

## Capability Status

| Capability | State | Stable basis |
|---|---|---|
| Canonical instruction source | available | `.sdd/` is authoritative. `.sdd/adapters/root-kernel.md` is the authored normative root kernel, and `.sdd/controls/adapters.yaml` owns only fixed renderer paths and budgets. |
| Generated root adapters | managed | `CLAUDE.md` and `AGENTS.md` are generated from fixed host preambles plus identical normative kernel bytes. Direct edits are rejected. |
| Compatibility projection | available | The canonical `.sdd/` controls and modules project to the legacy `.claude/` bundle through the compatibility renderer; adapter-only canonical artifacts are not projected. |
| Policy engine | available | The local command surface supports validation, evaluation, lifecycle transition, and bounded response generation from canonical controls and schemas. |
| Primary validation | available | Repository validation checks canonical compatibility, root-adapter parity, structure, links, executable inventory, policy inputs, and supported package behavior. |
| Project configuration | unconfigured | The reusable template intentionally leaves project identity, commands, environments, owners, data posture, and operational authority unresolved. |

The root-adapter commands are:

```text
.venv/bin/python scripts/render-agent-adapters.py --root . --check
.venv/bin/python scripts/render-agent-adapters.py --root . --write
```

P0 establishes deterministic generation and identical normative bytes across
the Claude and Codex root adapters. Richer normalized rule models, semantic
comparison, and renderer extensibility remain assigned to P6 and P7.

## Deliverables

| Deliverable | Status | Capability boundary |
|---|---|---|
| Project initialization | not started | Configure identity, repository commands, environments, owners, data classification, and authority when instantiating the template. |
| Specification and plan | deferred | Planning artifacts are intentionally local and ignored; tracked operating requirements live in the canonical `.sdd/` tree and constitution. |
| Instruction architecture | in review | Canonical controls, schemas, routed modules, the shared root kernel, generated adapters, compatibility projection, and validators form the P0 baseline. |
| Local validation | in progress | Every delivery must supply fresh evidence from the supported commands; this file intentionally carries no historical pass claims. |
| Integration | not started | Integration remains an explicit, policy-gated action outside this capability ledger. |
| Release and deployment | deferred | External execution belongs to the later operational-autonomy roadmap. |

## Validation Interface

Fresh validation is obtained from the repository commands, including:

```text
bash -n scripts/validate-instructions.sh scripts/validate-feature-context.sh
.venv/bin/python scripts/render-compatibility.py --root . --check
.venv/bin/python scripts/render-agent-adapters.py --root . --check
POLICY_PYTHON=.venv/bin/python bash scripts/validate-instructions.sh
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
git diff --check
```

Command output is the evidence for a specific delivery attempt. This document
records the durable validation surface, not a past result.

## Risks

- Project identity, repository commands, environments, deployment and rollback
  mechanisms, data classification, owners, external obligations, and
  operational authority remain unconfigured placeholders.
- Remote and production actions remain disabled until project initialization
  and the applicable policy gates pass.
- A generated adapter is trustworthy only when its canonical sources, fixed
  inventory, ownership manifest, output bytes, modes, and durability checks all
  converge.

## Deferred items

- Phase 2 operational autonomy is deferred: remote integration, release and
  deployment adapters, targeted idempotency, stronger response identity,
  sensitive policy comparison, and targeted invalidation.
- Advanced assurance is deferred: granular dependency invalidation, per-record
  schemas, dimensional or weighted risk, broad corroboration policy, complete
  external-action reconciliation, general semantic policy comparison, and
  policy-version migration.

## Status Vocabulary

Use exactly one of these states for roadmap deliverables:

- **not started** — no qualifying capability or evidence exists.
- **in progress** — implementation or fresh evidence collection is underway.
- **in review** — implementation exists and required review is pending.
- **merged** — reviewed changes are integrated into their target.
- **deployed** — the authorized target reports successful verification.
- **blocked** — a named requirement, policy, technical, or authority condition
  prevents progress.
- **deferred** — work is intentionally postponed with a recorded reason.

`merged` does not imply `deployed`; `in review` does not imply integration
authority.
