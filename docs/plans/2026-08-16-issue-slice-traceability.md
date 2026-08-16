# Parent-Issue Slice Traceability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the parent GitHub issue a durable, dogfooded delivery ledger in
which every ordered slice links its tracked design, tracked implementation plan,
and pull request.

**Architecture:** Keep the process human-readable and repository-backed: a
GitHub issue template defines the ledger shape, the canonical feature workflow
defines update gates, and focused structural tests prevent either contract from
drifting. P0 issue #3 is the acceptance dogfood; no hosted sync service or new
runtime subsystem is introduced.

**Tech Stack:** Markdown, GitHub issue templates, the existing `.sdd/` to
`.claude/` compatibility renderer, Python 3.11 `unittest`, Git, and GitHub CLI.

**Spec:** `docs/design/2026-08-16-issue-slice-traceability.md`

## Global Constraints

- One existing parent issue retains the ordered slice list; do not create a
  GitHub sub-issue per slice.
- Every slice ledger has explicit `Design`, `Plan`, `PR`, and
  `Exit criterion advanced` fields.
- Designs are tracked under `docs/design/`; implementation plans are tracked
  under `docs/plans/`.
- A slice may show `pending` before an artifact exists, but implementation may
  not begin until design and plan links are populated.
- Mark a slice complete only after its pull request merges and the issue is
  updated.
- Material scope changes update design, plan, and issue before changed
  implementation proceeds.
- P0 issue #3 is the dogfood acceptance issue and receives no exception from
  the new contract.
- Backfilled Slice 1 artifacts must say they are retrospective reconstructions
  and must not claim to have preceded implementation.
- `.sdd/` is canonical; regenerate affected `.claude/` compatibility outputs
  instead of editing them directly.
- Keep this structural and local: no issue-sync daemon, GitHub API automation,
  machine-readable roadmap database, or generalized documentation inventory.
- Use TDD for structural contracts, independently review each implementation
  task, repair every required finding, run fresh final verification, push, and
  open a draft pull request.

## File Structure

- `.github/ISSUE_TEMPLATE/spec-driven-change.md` — reusable parent-issue body.
- `.sdd/modules/workflows/feature-development.md` — canonical issue, design,
  plan, PR, and post-merge update gates.
- `.sdd/README.md` — operating guidance for the issue-ledger lifecycle.
- `.claude/workflows/feature-development.md` and `.claude/README.md` — generated
  compatibility outputs.
- `.sdd/generated-files.json` — regenerated compatibility ownership digests.
- `README.md` — adopter-facing link to the process.
- `docs/design/2026-08-16-p0-package-baseline-retrospective.md` — reconstructed
  Slice 1 design record.
- `docs/plans/2026-08-16-p0-package-baseline-retrospective.md` — reconstructed
  Slice 1 implementation sequence.
- `docs/plans/2026-08-15-sdd-compatibility-projection.md` — preserved Slice 2
  plan promoted from local-only state.
- `docs/plans/2026-08-15-thin-root-agent-adapters.md` — preserved Slice 3 plan
  promoted from local-only state.
- `tests/test_issue_traceability.py` — focused structural and dogfood contracts.

---

### Task 1: Track the Completed P0 Slice Artifacts

**Files:**

- Create: `tests/test_issue_traceability.py`
- Create: `docs/design/2026-08-16-p0-package-baseline-retrospective.md`
- Create: `docs/plans/2026-08-16-p0-package-baseline-retrospective.md`
- Create: `docs/plans/2026-08-15-sdd-compatibility-projection.md`
- Create: `docs/plans/2026-08-15-thin-root-agent-adapters.md`

**Interfaces:**

- Consumes: merged PRs #12–#14, the P0 roadmap, tracked Slice 2–3 designs, and
  the preserved local Slice 2–3 plans.
- Produces: stable design/plan paths for every completed issue #3 slice and the
  `P0_COMPLETED_SLICE_ARTIFACTS` mapping consumed by Task 2 tests.

- [ ] **Step 1: Add the failing completed-slice artifact tests**

Create `tests/test_issue_traceability.py`:

```python
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
P0_COMPLETED_SLICE_ARTIFACTS = {
    1: (
        "docs/design/2026-08-16-p0-package-baseline-retrospective.md",
        "docs/plans/2026-08-16-p0-package-baseline-retrospective.md",
    ),
    2: (
        "docs/design/2026-08-15-sdd-compatibility-projection.md",
        "docs/plans/2026-08-15-sdd-compatibility-projection.md",
    ),
    3: (
        "docs/design/2026-08-15-thin-root-agent-adapters.md",
        "docs/plans/2026-08-15-thin-root-agent-adapters.md",
    ),
}

class IssueTraceabilityTest(unittest.TestCase):
    def test_completed_p0_slice_artifacts_are_present_and_tracked(self):
        paths = [path for pair in P0_COMPLETED_SLICE_ARTIFACTS.values() for path in pair]
        for path in paths:
            self.assertTrue((ROOT / path).is_file(), path)
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", *paths], cwd=ROOT,
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_slice_one_backfill_is_explicitly_retrospective(self):
        for path in P0_COMPLETED_SLICE_ARTIFACTS[1]:
            content = (ROOT / path).read_text(encoding="utf-8").lower()
            self.assertIn("retrospective reconstruction", content)
            self.assertIn("introduces no new decision", content)
```

- [ ] **Step 2: Run the focused tests and record RED**

```bash
PYTHONPATH=src ../../.venv/bin/python -m unittest \
  tests.test_issue_traceability -v
```

Expected: failure because the four new artifact paths are absent or untracked.

- [ ] **Step 3: Create the honest Slice 1 retrospective records**

Create the design record with these exact sections:

```text
Provenance
Delivered problem and boundary
Design reconstructed from evidence
Alternatives and non-goals
Acceptance evidence
Retrospective limitation
```

Create the plan record with these exact sections:

```text
Provenance
Reconstructed ordered work
Verification performed
Deviations and review outcome
Retrospective limitation
```

Both `Provenance` sections must state:

```text
This is a retrospective reconstruction created after PR #12 merged. It
introduces no new decision and does not claim to have preceded implementation.
```

Ground all claims in the roadmap, PR #12, and merged repository state. The plan
records the actual order—package/version skeleton, characterization, package
installation tests, docs/ignores, review repair, publication—and contains no
unchecked tasks or invented RED output.

- [ ] **Step 4: Promote the preserved Slice 2 and Slice 3 plans unchanged**

Mechanically copy these files byte-for-byte:

```text
../p0-canonical-projections/docs/superpowers/plans/2026-08-15-sdd-compatibility-projection.md
  -> docs/plans/2026-08-15-sdd-compatibility-projection.md
../p0-thin-agent-adapters/docs/superpowers/plans/2026-08-15-thin-root-agent-adapters.md
  -> docs/plans/2026-08-15-thin-root-agent-adapters.md
```

Verify each source/destination SHA-256 pair is identical; do not rewrite the
approved task content.

- [ ] **Step 5: Stage, run GREEN, and commit**

```bash
git add tests/test_issue_traceability.py docs/design/ docs/plans/
PYTHONPATH=src ../../.venv/bin/python -m unittest tests.test_issue_traceability -v
git diff --cached --check
git commit -m "docs: track completed P0 slice artifacts"
```

Expected: both tests pass and the promoted plan hashes match their sources.

---

### Task 2: Require the Parent-Issue Lifecycle

**Files:**

- Create: `.github/ISSUE_TEMPLATE/spec-driven-change.md`
- Modify: `.sdd/modules/workflows/feature-development.md`
- Modify: `.sdd/README.md`
- Modify: `README.md`
- Modify: `tests/test_issue_traceability.py`
- Regenerate: `.claude/workflows/feature-development.md`
- Regenerate: `.claude/README.md`
- Regenerate: `.sdd/generated-files.json`

**Interfaces:**

- Consumes: `P0_COMPLETED_SLICE_ARTIFACTS` and the existing compatibility
  renderer.
- Produces: the reusable issue template and ordered workflow gates, with exact
  `.sdd/` to `.claude/` parity.

- [ ] **Step 1: Add failing template and lifecycle tests**

Extend `IssueTraceabilityTest`:

```python
    def test_issue_template_has_parent_and_slice_contract(self):
        content = (ROOT / ".github/ISSUE_TEMPLATE/spec-driven-change.md").read_text(
            encoding="utf-8"
        )
        for heading in (
            "## Objective", "## Scope", "## Non-goals", "## Exit criteria",
            "## Dependencies", "## Cross-cutting invariants",
            "## Ordered implementation slices",
        ):
            self.assertIn(heading, content)
        for field in ("Design:", "Plan:", "PR:", "Exit criterion advanced:"):
            self.assertIn(field, content)

    def test_feature_workflow_orders_issue_design_plan_pr_and_merge_updates(self):
        workflow = (ROOT / ".sdd/modules/workflows/feature-development.md").read_text(
            encoding="utf-8"
        )
        markers = (
            "Create or verify the parent issue",
            "Commit and link the approved slice design",
            "Commit and link the implementation plan",
            "Implementation begins only after",
            "Add the pull request link",
            "After merge, check the slice complete",
        )
        positions = [workflow.index(marker) for marker in markers]
        self.assertEqual(positions, sorted(positions))

    def test_operating_guides_explain_parent_issue_traceability(self):
        for path in ("README.md", ".sdd/README.md"):
            content = (ROOT / path).read_text(encoding="utf-8")
            self.assertIn("spec-driven parent issue", content.lower())
            self.assertIn("docs/design/", content)
            self.assertIn("docs/plans/", content)
            self.assertIn("Design`, `Plan`, and `PR", content)
```

- [ ] **Step 2: Run focused tests and record RED**

```bash
PYTHONPATH=src ../../.venv/bin/python -m unittest tests.test_issue_traceability -v
```

Expected: artifact tests pass; the three new tests fail because the template and
lifecycle language do not exist.

- [ ] **Step 3: Create the reusable issue template**

Create `.github/ISSUE_TEMPLATE/spec-driven-change.md` with this front matter:

```yaml
---
name: Spec-driven parent issue
about: Track an objective through ordered design, plan, and pull-request slices
title: ""
labels: ""
assignees: ""
---
```

Add all asserted headings. Under `Ordered implementation slices`, add:

```markdown
- [ ] **Slice 1 — Name**
  - Design: pending
  - Plan: pending
  - PR: pending
  - Exit criterion advanced: State the exact parent criterion.
```

An adjacent HTML comment states: link design before planning, link plan before
implementation, link PR when opened, and complete only after merge and issue
update. Do not require sub-issues.

- [ ] **Step 4: Update the canonical feature workflow**

In `.sdd/modules/workflows/feature-development.md`:

- add the parent issue and slice ledger to `Artifacts`;
- add tracked `docs/design/` and `docs/plans/` link gates;
- revise `Ordered steps` so the six test markers occur in lifecycle order;
- update design, plan, and issue before material deviation work continues;
- link the PR at publication and complete a slice only after merge; and
- name P0 issue #3 as the dogfood example without volatile delivery claims.

Preserve the existing headings and policy-engine, clarification, test-first,
review, convergence, solo-mode, and escalation rules.

- [ ] **Step 5: Update operating guidance and regenerate compatibility**

Add `Spec-Driven Parent Issue` guidance to `.sdd/README.md` and a concise
discoverability section to root `README.md`. Link `docs/design/`, `docs/plans/`,
the issue template, and the canonical feature workflow. State that every slice
exposes `Design`, `Plan`, and `PR`, and that issue #3 is the dogfood example.

Then run:

```bash
PYTHONPATH=src ../../.venv/bin/python scripts/render-compatibility.py --root . --write
cmp .sdd/README.md .claude/README.md
cmp .sdd/modules/workflows/feature-development.md \
  .claude/workflows/feature-development.md
```

Inspect `.sdd/generated-files.json`; only the README and feature-workflow
source/output digest pairs may change.

- [ ] **Step 6: Run GREEN, full verification, and commit**

```bash
PYTHONPATH=src ../../.venv/bin/python -m unittest tests.test_issue_traceability -v
PYTHONPATH=src ../../.venv/bin/python scripts/render-compatibility.py --root . --check
PYTHONPATH=src ../../.venv/bin/python scripts/render-agent-adapters.py --root . --check
POLICY_PYTHON=../../.venv/bin/python bash scripts/validate-instructions.sh
PYTHONPATH=src ../../.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
git diff --check
git add .github/ISSUE_TEMPLATE/spec-driven-change.md \
  .sdd/modules/workflows/feature-development.md .sdd/README.md README.md \
  .claude/workflows/feature-development.md .claude/README.md \
  .sdd/generated-files.json tests/test_issue_traceability.py
git commit -m "feat: require issue slice traceability"
```

Expected: all checks pass with only the two existing filesystem skips.

---

### Task 3: Review, Publish, and Dogfood Issue #3

**Files and remote state:**

- Review: `origin/main..HEAD`
- Verify: all files changed by Tasks 1–2
- Update: GitHub issue `nealsolves/spec-driven-dev#3`
- Create: draft PR from `codex/issue-slice-traceability` to `main`

**Interfaces:**

- Consumes: final reviewed artifact paths, PRs #12–#14, issue #3's existing
  non-slice content, and the final branch commit SHA.
- Produces: a pushed branch, draft PR, and verified dogfood issue with complete
  design/plan/PR traceability for Slices 1–3.

- [ ] **Step 1: Run fresh controller verification**

```bash
bash -n scripts/validate-instructions.sh scripts/validate-feature-context.sh
PYTHONPATH=src ../../.venv/bin/python scripts/render-compatibility.py --root . --check
PYTHONPATH=src ../../.venv/bin/python scripts/render-agent-adapters.py --root . --check
POLICY_PYTHON=../../.venv/bin/python bash scripts/validate-instructions.sh
PYTHONPATH=src ../../.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
git diff --check origin/main...HEAD
git status --short --branch
```

- [ ] **Step 2: Review, repair, and re-review**

Request independent whole-branch review emphasizing:

```text
one parent issue remains the durable ledger
design and plan are tracked before implementation
slice completion occurs only after merge and issue update
P0 issue #3 receives no dogfood exception
Slice 1 provenance is honestly retrospective
Slice 2–3 plans are byte-identical promotions
only intended compatibility outputs regenerate
no hosted sync service or volatile documentation claims
```

Fix every Critical and Important finding with focused RED/GREEN evidence and
repeat review until none remain. Record any safe-to-defer Minor finding.

- [ ] **Step 3: Rerun fresh final verification and publish**

Repeat Step 1 against the exact reviewed HEAD, push the branch, and open a draft
PR against `main`. The PR links issue #3, names it as the dogfood target,
summarizes review repairs, and includes fresh verification evidence. Preserve
the worktree for feedback.

- [ ] **Step 4: Update issue #3 from its current remote body**

Fetch the current body immediately before editing and preserve its objective,
scope, delivery notes, exit criteria, dependencies, and invariant. Update only
the delivery ledger and add a concise process-dogfood entry:

- Slices 1–3 are checked complete and each has resolvable `Design`, `Plan`,
  `PR`, and `Exit criterion advanced` entries.
- Slice 1 links the retrospective records and PR #12.
- Slice 2 links the compatibility design, promoted plan, and PR #13.
- Slice 3 links the thin-adapter design, promoted plan, and PR #14.
- Slices 4–8 explicitly show `Design: pending`, `Plan: pending`, and
  `PR: pending`; Slice 4 is identified as next.
- `Process dogfood` links this change's design, plan, and draft PR.

Use immutable final-commit URLs for newly tracked artifacts and canonical PR
URLs for #12–#14.

- [ ] **Step 5: Verify the remote dogfood state**

Refetch issue #3 and verify:

```text
Slices 1–3: checked, all four fields present, no pending reference
Slices 4–8: unchecked, Design/Plan/PR explicitly pending
Slice 4: identified as next
Process dogfood: design + plan + current PR linked
All completed-slice and process artifact URLs resolve
```

Repair any failed write or link before reporting completion. Do not claim the
repository process is published merely because its PR is open.

