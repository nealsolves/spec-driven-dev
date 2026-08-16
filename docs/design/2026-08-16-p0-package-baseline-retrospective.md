# P0 Package Baseline Retrospective Design Record

## Provenance

This is a retrospective reconstruction created after PR #12 merged. It
introduces no new decision and does not claim to have preceded implementation.

This record is reconstructed from the [P0 roadmap](issue-2-p0-p8-roadmap.md),
[PR #12](https://github.com/nealsolves/spec-driven-dev/pull/12), and the
merged repository state at merge commit `43839f3`.

## Delivered problem and boundary

The P0 roadmap keeps the existing policy engine as the execution core while
building the trustworthy, adoptable baseline. Slice 1 supplied the package
baseline needed for that work: an installable `spec-driven-dev` distribution,
one authoritative package version, declared Python and policy-runtime
dependencies, and characterization coverage for the existing policy CLI.

The merged change did not introduce a new policy-engine interface, compatibility
projection, root-adapter renderer, hosted service, or release/deployment
automation. Those concerns belong to later P0 slices or later roadmap phases.

## Design reconstructed from evidence

The merged `pyproject.toml` declares the package metadata, setuptools build
backend, `src/` package discovery, Python `>=3.11` support, and bounded
`PyYAML` and `jsonschema` dependencies. `src/sdd/_version.py` is the
authoritative `0.1.0` version source; `src/sdd/__init__.py` exports that value.

The final repository tests demonstrate the delivered boundary. Package-baseline
tests build a wheel, install it into an isolated target, compare the installed
distribution version with `sdd.__version__`, and inspect wheel metadata for the
supported runtime and dependencies. Legacy CLI characterization tests preserve
the observed `validate`, `evaluate`, and invalid-command contracts of
`scripts/policy-engine.py`.

## Alternatives and non-goals

The evidence does not support claiming a different packaging design, a separate
version registry, or a replacement policy-engine CLI. The existing engine
remained the P0 execution core, and the P0 roadmap deferred the broader CLI,
durable records, remote execution, and other later-phase work.

This record does not backdate approval, reconstruct private review discussion,
or add requirements beyond the roadmap and merged change.

## Acceptance evidence

PR #12 merged as `43839f3` with the package metadata and source modules,
package-baseline and legacy-CLI tests, README update, test requirements, and
ignore rules. The resulting repository contains those files and the P0 roadmap
states that self-dogfood and package installation are part of the P0 exit
criteria.

## Retrospective limitation

The merged commit preserves final code and tests, not the original design
conversation, task order timestamps, RED output, or individual review-thread
details. This record therefore states only the decisions and delivered behavior
that the roadmap, PR #12, and merged repository state substantiate.
