# Parent-Issue Slice Traceability Design

Status: Approved

## Purpose

Make the parent GitHub issue the durable delivery ledger for spec-driven work.
Every ordered implementation slice must expose its design, implementation plan,
and pull request from the issue so a future maintainer can recover intent,
sequence, scope changes, and delivery evidence without reconstructing chat or
local agent state.

P0 issue #3 is the dogfood acceptance issue for this process: it must conform
to the same ledger contract being introduced, not receive a documentation-only
exception. The repository then makes the proven convention part of the reusable
feature-development process.

## Decisions

1. One existing parent issue retains the ordered slice list. Slices do not
   require separate GitHub sub-issues.
2. Each slice has three explicit references in its parent issue:
   `Design`, `Plan`, and `PR`.
3. Designs and plans are tracked repository artifacts. Local-only agent plans
   do not satisfy issue traceability.
4. A slice may show `pending` before an artifact exists, but implementation may
   not begin until its design and plan links are populated.
5. A slice is checked complete only after its PR merges and the issue entry is
   updated.
6. Material scope changes update the design, plan, and parent issue before the
   changed implementation proceeds.
7. P0 uses structural process enforcement only. A hosted issue-sync service,
   machine-readable roadmap database, and GitHub API automation are deferred.

## Artifact Locations

- Slice designs live under `docs/design/`.
- Slice implementation plans live under `docs/plans/`.
- The reusable issue body starts from
  `.github/ISSUE_TEMPLATE/spec-driven-change.md`.
- The canonical execution rules live in
  `.sdd/modules/workflows/feature-development.md` and `.sdd/README.md`.
- `.claude/` remains generated compatibility output and is never edited
  directly.

Designs and plans use stable, descriptive filenames. They may be shared by
multiple slices only when the parent issue states the exact section that governs
each slice. A PR description or chat transcript is delivery evidence, not a
replacement for either tracked artifact.

## Parent Issue Contract

A spec-driven parent issue contains:

- objective;
- scope and non-goals;
- exit criteria;
- dependencies and cross-cutting invariants; and
- an ordered slice checklist.

Every slice entry contains this compact ledger:

```markdown
- [ ] **Slice N — Name**
  - Design: [tracked design](...)
  - Plan: [tracked implementation plan](...)
  - PR: pending
  - Exit criterion advanced: ...
```

`pending` is honest pre-delivery state, not a link placeholder. Once an artifact
exists, replace `pending` with its link. Completed slices may not retain a
pending reference.

## Lifecycle

1. **Create issue.** Before slice design begins, create the parent issue with
   the objective, boundaries, exit criteria, invariants, and ordered slice
   skeleton.
2. **Document design.** Commit the approved slice design and add its link to the
   parent issue.
3. **Document plan.** After design approval, commit the slice implementation
   plan and add its link before implementation begins.
4. **Implement and review.** Execute the linked plan, retain test and review
   evidence, and update both tracked artifacts plus the issue before proceeding
   with a material deviation.
5. **Open PR.** Add the PR link and the exact parent exit criterion advanced.
6. **Merge and update.** After merge, check the slice complete, verify all three
   references resolve, record any durable review outcome in the artifacts or PR,
   and identify the next slice.
7. **Close parent.** Close the parent issue only when every slice and exit
   criterion is evidenced; a merged intermediate PR does not close it.

## P0 Issue #3 Backfill

Issue #3 predates this process but is its required dogfood target. Its completed
slices therefore require an explicit, honest backfill:

- Slice 1 receives retrospective design and implementation-plan records derived
  from the merged PR, roadmap, and repository state. Both records state that
  they were reconstructed after delivery and introduce no new decisions.
- Slice 2 links its tracked compatibility-projection design and promotes the
  preserved local implementation plan into `docs/plans/`.
- Slice 3 links its tracked thin-adapter design and promotes the preserved local
  implementation plan into `docs/plans/`; PR #14 is marked merged.
- Slices 4–8 retain explicit `pending` design, plan, and PR states. Slice 4 is
  identified as next, but its implementation cannot start until its design and
  plan links are populated.

The process change is not accepted until issue #3 itself satisfies the parent
contract, completed-slice links resolve, pending slices remain honest, and the
issue update is verified after publication.

The issue update uses stable repository or commit URLs. It does not link to
ephemeral worktree paths, local reports, or chat identifiers.

## Repository Changes

1. Add the reusable GitHub issue template with the parent contract and slice
   ledger.
2. Add the lifecycle and link gates to the canonical feature workflow.
3. Add concise operating guidance to `.sdd/README.md` and root `README.md`.
4. Track the Slice 1 retrospective design/plan and the preserved Slice 2–3
   implementation plans under canonical documentation paths.
5. Add focused structural tests for the issue template, workflow sequence,
   tracked artifact locations, completed-slice link rule, and generated
   compatibility parity.
6. Regenerate compatibility outputs from `.sdd/`.
7. Update issue #3 after the final artifact commit is pushed so all completed
   slice links resolve to stable GitHub content.

## Validation

- The issue template contains the required parent sections and per-slice
  `Design`, `Plan`, `PR`, and exit-criterion fields.
- The canonical feature workflow requires issue creation before design, design
  linkage before planning, plan linkage before implementation, PR linkage when
  opened, and completion only after merge/update.
- All referenced completed-slice design and plan files are tracked.
- Compatibility check reproduces `.claude/` exactly from `.sdd/`.
- Primary validation and the full test suite remain green.
- The final issue #3 body marks Slices 1–3 complete with three resolvable links
  each and keeps Slices 4–8 explicitly pending.
- Issue #3 passes as the dogfood example used by the structural documentation
  tests and the final manual GitHub verification.

## Non-Goals

- Creating a GitHub sub-issue for every slice.
- Automatically editing issues from CI or local validation.
- Treating PR descriptions as design or plan artifacts.
- Backdating retrospective documents as if they preceded delivery.
- Adding a generalized documentation inventory or generated status system;
  those remain later P0 slices.

## Failure and Recovery

- If a required artifact is absent, leave the issue reference `pending` and do
  not start the gated phase.
- If a link is wrong, repair the tracked artifact or issue before marking the
  slice complete.
- If scope changes materially after implementation starts, stop, amend design
  and plan, update the issue, then re-review the affected work.
- If GitHub is unavailable, complete local artifacts but defer the issue-state
  claim until the remote update can be verified.
