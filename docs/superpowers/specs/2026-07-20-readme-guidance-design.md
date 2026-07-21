# Root README Guidance Design

## Status

The README direction was approved in conversation on 2026-07-20. This written
specification awaits final user review before implementation.

## Purpose

Create a root `README.md` that helps a developer adopt this repository through
GitHub's **Use this template** flow and reach a safe, validated project setup
without first reading the full control-plane documentation.

The README is an onboarding document, not another policy source. Normative
behavior remains in `CLAUDE.md`, the four control-plane files, and their linked
modules.

## Audience and Positioning

The primary audience is developers adopting the reusable repository template.
The README is Claude-first: it explains that the repository is organized around
`CLAUDE.md` and `.claude/`, while noting that another coding agent can use the
template when it reads and follows those files.

The document assumes the reader understands Git and GitHub but does not assume
prior knowledge of this repository, Spec Kit, the authority model, or the
lifecycle state machine.

## Selected Approach

Use an adoption-first README. Lead with the outcome and a short quick start,
then explain only the concepts required to initialize and operate the template
safely. Link to `.claude/README.md` and the approved architecture document for
the deeper reference material.

This is preferred over a reference-first README, which delays onboarding, and a
minimal launcher, which would omit required initialization and safety context.

## Information Architecture

The README will use this sequence:

1. Project name and concise value proposition.
2. What the template provides and who should use it.
3. Quick start using GitHub's **Use this template** action.
4. Local setup and policy-runtime dependency installation.
5. Required project initialization in `.claude/project.yaml`.
6. Repository validation commands.
7. The first feature or maintenance workflow.
8. Safe defaults and the four authority outcomes.
9. Claude-first compatibility and the Spec Kit relationship.
10. A compact repository map.
11. MVP, Phase 2, and deferred boundaries.
12. Links to detailed operating and design guidance.

## Quick-Start Behavior

The quick start must:

- begin with GitHub's **Use this template** flow;
- show commands with placeholders that are visibly intended for replacement;
- direct the developer to create and activate a Python virtual environment;
- install `requirements-policy.txt` rather than inventing application
  dependencies;
- instruct the developer to replace project placeholders and explicit
  `unknown` values with repository evidence;
- keep remote and production permissions disabled until initialization is
  complete;
- run `bash scripts/validate-instructions.sh` before beginning delivery work;
- explain that application-specific install, test, lint, build, release,
  deploy, and rollback commands must come from the instantiated repository.

The README will not claim that cloning alone makes a project production-ready.

## Guidance Boundaries

The root README will summarize, not duplicate:

- the complete authority hierarchy;
- every lifecycle transition and evidence prerequisite;
- each rule module's detailed controls;
- schema definitions or full YAML examples;
- the complete policy engine command reference;
- advanced Phase 2 or deferred architecture.

Those details remain linked from `.claude/README.md`, `CLAUDE.md`, and the
design document. This prevents the onboarding document from becoming a second
policy implementation that can drift.

## Safety and Accuracy

The README must state that the reusable template starts with:

- `project.lifecycle: unconfigured`;
- remote actions disabled;
- production actions disabled;
- unresolved commands, owners, data posture, and environments represented
  explicitly rather than guessed.

It must describe the authority outcomes in plain language:
`autonomous`, `autonomous_with_enhanced_gates`, `human_required`, and
`prohibited`. It must also state the doctrine that the most restrictive
applicable outcome wins.

The README must not claim certification, compliance, production readiness,
deployment support, autonomous GitHub execution, or universal compatibility.

## Validation

Implementation will be accepted when:

1. `README.md` exists at the repository root and all local links resolve.
2. The quick start uses the GitHub template flow and copyable commands.
3. Initialization and safe defaults are explicit.
4. Claude-first and conditional other-agent compatibility are stated
   accurately.
5. Spec Kit is described as an optional compatible workflow reference, not a
   bundled or guaranteed runtime.
6. The repository map matches the files actually present.
7. MVP, Phase 2, and deferred scope match the approved system design.
8. The README contains no unresolved `TBD`, `TODO`, or fake project commands.
9. The full unit suite and `bash scripts/validate-instructions.sh` pass.
10. `git diff --check` reports no whitespace errors.

## Publication

Implement the README on `agent/readme-guidance`, commit only the approved
documentation and any narrowly required documentation tests, and push that
branch to `nealsolves/spec-driven-dev`. Opening or merging another pull request
is outside this request unless separately authorized.
