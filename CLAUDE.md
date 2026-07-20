# CLAUDE.md — Spec-Driven Development Operating Contract (Template)

> Persistent operating contract for any Claude-family agent working in this repository. Read at the start of **every** session before doing anything else. Replace `<placeholders>` when instantiating for a project.

> **Durability layering.** `CLAUDE.md` = durable doctrine. `.specify/memory/constitution.md` = supreme project principles. `specs/<NNN>-<feature>/` = per-feature volatile artifacts (spec, plan, tasks). `implementation_status.md` = volatile state (current feature, open PRs, test counts). When facts conflict, constitution wins, then spec artifacts, then this file.

---

## 1. Project Identity

| Field | Value |
|---|---|
| **Product name** | `<product>` |
| **Repository** | `<https://github.com/owner/repo>` |
| **License** | `<license>` |
| **Owner / final reviewer** | `<owner>` (`<email>`) |
| **Current feature** | _Volatile — see `implementation_status.md` and active `specs/` branch._ |

---

## 2. Source of Truth Hierarchy

Consult in order; first match wins.

1. **`.specify/memory/constitution.md`** — project constitution. Supreme. Never contradict it; amend it only via §4.
2. **Active feature artifacts** — `specs/<NNN>-<feature>/spec.md` → `plan.md` → `tasks.md` (plus `research.md`, `data-model.md`, `contracts/`). The spec defines *what/why*; the plan defines *how*; tasks define *execution order*.
3. **This file (`CLAUDE.md`)** — operating discipline.
4. **Conventional best practice** — fallback only.

Code is the *expression* of the spec, not the source of truth. When code and spec disagree, fix the spec first (or amend it deliberately), then regenerate/repair the code.

---

## 3. Spec-Driven Development Workflow (mandatory)

Every non-trivial change flows through the spec-kit lifecycle. No implementation code before its spec, plan, and tasks exist.

```text
/speckit.constitution → /speckit.specify → /speckit.clarify → /speckit.plan
        → validate plan → /speckit.tasks → /speckit.analyze → /speckit.implement
```

| Phase | Command | Output | Gate to pass before next phase |
|---|---|---|---|
| 0. Constitution | `/speckit.constitution` | `.specify/memory/constitution.md` | Exists, current, articles filled in |
| 1. Specify | `/speckit.specify` | `specs/<NNN>-<feature>/spec.md` | **Spec gate S1** (below) |
| 2. Clarify | `/speckit.clarify` | Clarifications section in spec | Zero `[NEEDS CLARIFICATION]` markers |
| 3. Plan | `/speckit.plan` | `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md` | **Spec gate S2** (Phase −1 gates) |
| 4. Tasks | `/speckit.tasks` | `tasks.md` | Tasks trace to contracts/entities/tests |
| 5. Analyze | `/speckit.analyze` | Cross-artifact consistency report | **Spec gate S3** — analyze clean |
| 6. Implement | `/speckit.implement` | Code, via PRs per §6 | All PR gates (§7) |

### Spec gates (pre-implementation, per feature)

- **S1 — Spec complete.** `spec.md` states *what* and *why* only (no tech stack, no APIs-as-design). Review & Acceptance checklist passed. Every requirement testable. All `[NEEDS CLARIFICATION]` markers resolved via `/speckit.clarify` — never by silent assumption.
- **S2 — Plan passes Phase −1 gates** (from the constitution):
  - *Simplicity gate*: ≤3 projects/modules for the initial cut; no speculative future-proofing. Violations documented in the plan's Complexity Tracking section with justification.
  - *Anti-abstraction gate*: use framework features directly; no wrapper layers; single model representation per concept.
  - *Integration-first gate*: contracts defined in `contracts/`; contract tests specified before implementation; realistic test environments (real DB/services) preferred over mocks.
  - *Security gate*: plan contains a threat-model section — trust boundaries, sensitive data flows, authN/authZ approach, secrets handling (§9). A plan without it fails S2.
- **S3 — Analyze clean.** `/speckit.analyze` reports no coverage gaps or cross-artifact inconsistencies between spec, plan, and tasks.

**Mid-implementation discoveries** that invalidate the spec or plan: stop, update the artifact, re-run `/speckit.analyze`, then resume. Do not let code drift ahead of its spec.

---

## 4. Constitution Discipline

- The constitution's core articles are non-negotiable defaults: **Library-first** (features start as standalone libraries), **CLI/text interface** (observability via text I/O), **Test-first (NON-NEGOTIABLE)**, **Simplicity**, **Anti-abstraction**, **Integration-first testing**. Project-specific articles (security boundaries, observability, versioning) fill the open slots.
- **Amendments** require: written rationale, owner approval, backwards-compatibility assessment, and a dated entry in the constitution's amendment log. Mirror a one-line summary to §13 here. Never "temporarily ignore" an article — amend or comply.

---

## 5. PR-Based Development — Strict, Non-Negotiable

Every change ships through a pull request. No direct pushes to `origin/main`.

### 5.0 Canonical workflow

```text
feature branch → PR (non-draft) → review gates → security review
             → rebase + local-main staging merge → merge to origin/main
```

```bash
git switch main && git pull --ff-only
git switch -c feat/<NNN>-<slug>        # NNN = spec ID from specs/
# ... implement tasks ...
git push -u origin feat/<NNN>-<slug>
gh pr create --base main
```

### 5.1 Branching

- `origin/main` is protected: linear history, required review(s), required status checks. The **authoritative gate-1 signal is the local triple** `<test> && <lint> && <typecheck>` — CI may be red/unrun for environmental reasons without blocking a locally-green branch; when they disagree, investigate and note the cause in the PR body.
- Branch names: `<type>/<NNN>-<short-slug>` (e.g. `feat/003-user-auth`), where `NNN` is the spec ID — this keeps spec traceability and type classification. Branch off `main` only; never off another feature branch. Point spec-kit scripts at the existing branch rather than letting them create a bare `NNN-slug` branch.

### 5.2 Commits

- **Conventional Commits.** `<type>(<scope>): <subject>`. Types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `perf`, `build`, `ci`, `revert`.
- Subject ≤72 chars, imperative mood. Body explains the **why** and references the spec: `Implements specs/003-user-auth/tasks.md T7–T9.`
- One logical change per commit. Squash trivial fixups before pushing. Test-first ordering visible in history where practical (tests commit precedes or accompanies implementation).

### 5.3 PR scope — slice by task group

- One concern per PR; target **≤400 lines of diff**. A feature spec spans **multiple PRs**: implement `tasks.md` as a sequence of small PRs (per user story or task group), each independently gated. Larger PRs require justification in the PR body.
- Every PR must be **atomically revertable**: main builds, lints, and tests green after `git revert <merge-sha>`.
- PR body requires: **What**, **Why** (link spec/plan section), **How**, **Test plan**, **Security notes**, **Risks / follow-ups**, **Spec reference** (`specs/<NNN>-.../tasks.md` task IDs).

### 5.4 Reviews and merge

- Self-review first. One reviewer approval required. **Squash-and-merge** default; squash subject = PR title in Conventional Commit form.
- **After merge:** `git switch main && git pull --ff-only`, re-run the gate-1 triple, delete the feature branch (local and remote). Cut the next branch from this verified `main`.

### 5.5 Hard rules

- **No commit to main. Ever.** No direct push to `origin/main`. If about to, stop — branch + PR instead.
- **No implementation without spec artifacts** (S1–S3 passed) for non-trivial work. Mechanical changes (rename, dep bump, typo) may skip the spec phases but never the PR gates.
- **No force-pushed tags.** Releases tag from merged main only.

---

## 6. GitHub Actions / CI Best Practices

- CI runs on every PR: test, lint, typecheck, build, plus **CodeQL (or equivalent SAST)**, **dependency review**, and **secret scanning**. Enable push protection for secrets at the repo level.
- **Pin third-party actions to a full commit SHA**, not a tag. Review action updates like dependency updates.
- **Least-privilege `GITHUB_TOKEN`**: set `permissions:` explicitly per workflow (default `contents: read`); grant write scopes only where needed.
- Never put secrets in workflow files or logs; use encrypted secrets/environments. Never expose secrets to workflows triggered by `pull_request_target` on untrusted code.
- CI never hits live external providers; use recorded fixtures. Keep workflows deterministic and cache-safe.
- Dependabot (or equivalent) enabled for deps and actions; security updates auto-opened as PRs that flow through the normal gates.

---

## 7. Mandatory Pre-Merge Review Gates

For a **code PR**, none are optional. If a gate's skill is unavailable, do not claim the PR is ready — flag the blocker in the PR body and continue safe local work only.

**Non-code PR carve-out.** The review-skill gates — **4 (`/code-review:code-review`), 5 (`/codex:adversarial-review`), 6 (`/security-review`)** — are **skipped** when a PR's diff is confined to documentation (`*.md`, `docs/**`, `specs/**`, `LICENSE`, `NOTICE`) and/or non-executable hygiene config (`.gitignore`, `.prettierignore`, `.editorconfig`). The moment it touches `src/**`, `tests/**`, `package.json`/lockfiles, CI/workflow files, or any build/runtime file, it is a code PR and every gate applies. Gates **1, 2, 3, 7, 8 apply to every PR.** State `gates 4/5/6 skipped — docs-only / ignore-only PR` in the PR body.

1. **Branch green — local is authoritative.** `<test> && <lint> && <typecheck>` all pass locally. Test-first evidence: new behavior has tests that were observed red before implementation (§10). `tasks.md` checkboxes and `implementation_status.md` updated per §12.
2. **Open PR non-draft** against `origin/main`. This is the target all gates comment on.
3. **Classify the PR: docs-only/ignore-only or code PR.** Record the classification (and any gate skips) in the PR body.
4. **`/code-review:code-review` — single pass.** Surfaces ≥80-confidence findings; of those surfaced, resolve or dismiss **every finding rated >50 confidence** with a written reason in the PR body. Do not re-trigger; exception: substantial new code added after gate 6 fixes or the gate-7 merge earns one fresh pass.
5. **`/codex:adversarial-review` (conditional).** Required if diff >400 lines **or** the PR touches security-sensitive or boundary paths: authN/authZ, crypto, input parsing/validation, `contracts/` implementations, schema boundaries, CI workflows. Address every finding; record invocation in the PR body.
6. **`/security-review`.** Address every finding and push fixes. Runs **after** gates 4–5 so it reviews the post-fix code.
7. **Rebase + local-main staging merge — final integration gate.** Rebase if the branch is >5 commits behind `origin/main` or >3 days old (`git fetch origin && git rebase origin/main`), re-run gate-1 checks; then merge into local `main` and re-run gate-1 checks. Do not push local `main`. **Guard:** this gate runs after security review, so if the rebase/merge required any non-trivial conflict resolution (anything beyond a clean replay of existing commits), re-run `/security-review` — and gate 4 if the delta is substantial — on the changed hunks before proceeding.
8. **Hand off to Owner.** Gates 4–7 (as applicable) clean.

**PR readiness checklist** (docs-only / ignore-only PRs skip gates 4/5/6 — note the skip in the PR body):
```text
[ ] Branch green: test + lint + typecheck; test-first evidence; status updated     (gate 1)
[ ] PR opened NON-DRAFT against origin/main                                        (gate 2)
[ ] Classified: docs-only or code PR — skips recorded in PR body                   (gate 3)
[ ] /code-review:code-review run once: >50-confidence findings resolved/dismissed  (gate 4, code PR)
[ ] /codex:adversarial-review clean — if >400 lines OR security/boundary paths     (gate 5, code PR)
[ ] /security-review clean                                                         (gate 6, code PR)
[ ] Rebased if stale; local-main staging merge green; re-review if conflicts       (gate 7)
[ ] Hand off to Owner                                                              (gate 8)
```

**Why the staging merge is last:** review fixes pushed for gates 4–6 would invalidate an earlier staging merge, forcing a redo. Running it once, after all reviews, means every review sees near-final code and the merge validates exactly what ships. The gate-7 guard covers the one risk (unreviewed conflict resolutions).

### 7.1 Rollback and hotfix

If a merged PR breaks `origin/main`: open `fix/<NNN>-hotfix-<slug>`, `git revert <squash-merge-sha>`, open the revert as a PR immediately. Gates 4 and 6 still run; gate 5 only if applicable. A pure revert may state "pure revert of `<sha>`" in lieu of new tests. Once main is green, fix forward on a fresh branch with a regression test covering the failure — and update the spec/plan if the failure exposed a spec gap.

---

## 8. Coding Standards

- **Strict compiler/linter settings.** (e.g. TypeScript `"strict": true`; no implicit any; lint errors fail CI.)
- **Validate every boundary.** Schema validation (e.g. Zod/pydantic) on all tool inputs, API payloads, file artifacts, env config. Parse, don't assume.
- **Functional core, imperative shell.** Side effects (I/O, network) live at the edges.
- **No unsafe casts / `any`** except behind a `// safety:` comment justifying it.
- **Errors are typed.** Never throw bare strings. **No silent catches** — catching means deciding what to log, record, and surface.
- **No `console.log`/print in committed code.** Structured logger only.
- **Deterministic where possible.** Record model/prompt-hash/seed for any LLM-touching path; prefer byte-stable outputs in tests.

---

## 9. Secure Coding Practices

Security is a spec-time concern (the plan's threat model, §3 S2) enforced at code time:

- **Input handling:** validate and normalize all untrusted input at the boundary (schema-first). Parameterized queries only; no string-built SQL/shell. Encode output per sink (HTML/URL/shell). Guard path traversal (`resolve` + prefix check) and SSRF (allowlist outbound targets). Safe deserialization only.
- **Secrets:** never in code, config committed to git, logs, or error messages. Load from env/secret manager; `.env` files gitignored. Rotate on any suspected exposure. Secret scanning + push protection enabled (§6).
- **AuthN/AuthZ:** deny by default; enforce authorization at every entry point (not just the UI); least privilege for tokens, DB roles, and service accounts.
- **Dependencies:** pin exact versions via lockfile; review new dependencies before adding (license + maintenance + typosquat check); `npm audit`/`pip-audit` (or equivalent) clean or triaged in the PR body; new dependencies require owner approval (§11).
- **Crypto:** platform/battle-tested libraries only; no home-rolled crypto; current algorithms (e.g. AES-GCM, argon2/bcrypt for passwords); TLS for all transport.
- **Error handling & logging:** fail closed; user-facing errors carry no stack traces, paths, or internal identifiers; logs exclude secrets and PII.
- **LLM-specific (if applicable):** treat model output as untrusted input; validate against schemas before acting on it; guard prompt-injection paths on any tool that fetches external content; hard, configurable caps on cost/retry loops — never loop unbounded.

Every code PR passes `/security-review` (gate 6). Findings are fixed, not argued away; a dismissed finding needs a written justification in the PR body.

---

## 10. Testing Discipline — Test-First (NON-NEGOTIABLE)

- **Red before green.** For every new behavior: write the test, run it, observe it fail, then implement. Contract tests are written from `contracts/` **before** implementation code exists (constitution Article III).
- **Order of creation:** contracts → contract tests → integration tests → unit tests → implementation.
- **Test layers:** unit tests for every core function; schema tests round-tripping fixtures; contract tests against declared interfaces via a stub client; integration tests preferring real environments (real DB, real services) over mocks — mock only at trust boundaries you don't own.
- **Golden/snapshot tests** for generated artifacts; refresh requires `git diff` of the goldens in the PR body.
- **External services in CI:** recorded fixtures only; never live calls.
- Coverage targets: unit ≥80%, schemas 100%, every contract has a contract test. Acceptance criteria in `spec.md` map 1:1 to tests — `/speckit.analyze` (S3) checks this mapping.

---

## 11. When to Stop and Ask

**Proceed without asking** when the task is covered by the constitution, an approved spec/plan, or is mechanical (rename, refactor, dep bump within policy, test/doc improvement).

**Stop conditions override proceed conditions.** Stop and ask when:

- Spec, plan, and constitution conflict, or a constitutional amendment seems needed.
- A `[NEEDS CLARIFICATION]` marker cannot be resolved from existing artifacts.
- A new dependency is needed that isn't already approved.
- A security finding would be dismissed rather than fixed, or the threat model must change.
- The PR scope is growing past the 400-line guideline.
- A planned approach is blocked by an environment issue (missing key, broken toolchain, schema breakage).

When stopping, leave the branch clean: last commit green, no half-applied edits.

---

## 12. Implementation Status Tracking

`implementation_status.md` (repo root) is the single source of truth for done vs. missing. Per-feature progress lives in `specs/<NNN>-<feature>/tasks.md` checkboxes.

Before opening any PR: tick completed tasks in `tasks.md`, update `implementation_status.md` for everything the PR delivers, and commit it as its own `docs(status): ...` commit immediately before the PR. Flip deliverables ⬜→✅ only when landed; record deferrals with a reason. In-progress notes and TODOs belong in the spec artifacts, not the tracker.

---

## 13. Memory Changelog

Newer entries at top; one line each, linking to the constitution amendment, spec, or PR for detail. Volatile status belongs in `implementation_status.md`, not here.

- `<YYYY-MM-DD>: <one-line durable decision or amendment summary>`

---

## 14. Quick Reference

```bash
# Spec lifecycle (per feature)
/speckit.specify … → /speckit.clarify → /speckit.plan → /speckit.tasks
/speckit.analyze                      # must be clean before implementing

# Local dev
<install> && <test> && <lint> && <typecheck>

# Branching
git switch main && git pull --ff-only
git switch -c feat/<NNN>-<slug>
git push -u origin feat/<NNN>-<slug>
gh pr create --fill --base main

# Release (from merged main only)
git tag v<version> && git push origin v<version>
```

---

## 15. The One-Line Reminder

**Constitution first, spec before code, tests before implementation, PR everything, security review before the final merge — never push to main.**