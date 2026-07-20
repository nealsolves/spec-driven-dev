# Implementation Status

> Operational ledger only. The selected workflow, explicit intent, and approved
> active artifacts resolve feature identity; this file does not do so by itself.
> Update claims only after their specific evidence exists.

## Active Work

| Field | Current value |
|---|---|
| Active change | `<change-id or none>` |
| Active branch | `<branch or none>` |
| Active profile | `solo / unconfigured` |
| Open pull requests | `none recorded` |
| Current gate | `project initialization not completed` |

## Deliverables

| Deliverable | Status | Evidence or next gate |
|---|---|---|
| Project initialization | not started | Complete the initialization workflow and validate all project fields. |
| Specification and plan | not started | Link approved artifacts when the selected workflow requires them. |
| Implementation | not started | Link commits and test-first evidence. |
| Validation | not started | Record configured local commands and results. |
| Review and convergence | not started | Record policy-activated reviews and resolved findings. |
| Pull request and merge | not started | Record exact merge-candidate CI and remote references. |
| Release and deployment | not started | Record separate authority, rollback, and verification evidence. |

## Risks

- Project identity, repository commands, environments, data classification, and
  operational authority remain unconfigured.
- Remote and production actions are disabled until initialization passes.

## Deferred items

- Phase 2 operational automation is deferred until the MVP has been exercised
  on several real changes.
- Advanced assurance is deferred until observed failure modes justify it.

## Verification History

| Field | Current value |
|---|---|
| Last verified main commit | `unknown` |
| Last deployment | `none` |
| Last policy validation | `not run for an instantiated project` |
| Last full test result | `not run for an instantiated project` |

## Status Vocabulary

Use exactly one of these states for each deliverable:

- **not started** — no qualifying work or evidence exists.
- **in progress** — implementation or evidence collection is underway.
- **in review** — implementation is complete and required review is pending.
- **merged** — the reviewed change is integrated into its target branch.
- **deployed** — the authorized target reports successful verification.
- **blocked** — a named requirement, policy, technical, or authority condition
  prevents progress.
- **deferred** — work is intentionally postponed with a recorded reason.

`merged` does not imply `deployed`; `in review` does not imply merge authority.
