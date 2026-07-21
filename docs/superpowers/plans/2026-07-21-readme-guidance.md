# Root README Guidance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a clear, adoption-first root README for developers using GitHub's template flow.

**Architecture:** `README.md` is a non-normative onboarding layer that links to the existing behavioral kernel and operating guide instead of duplicating policy. A focused test locks its required sections, commands, safety language, compatibility claims, and local links.

**Tech Stack:** Markdown, Python 3.11+ `unittest`, existing shell validator.

## Global Constraints

- The primary audience is developers adopting the repository through GitHub's **Use this template** flow.
- Position the template as Claude-first and compatible with other coding agents only when they read and follow `CLAUDE.md` and `.claude/`.
- Keep `README.md` explanatory; `CLAUDE.md` and the validated control plane remain normative.
- Do not invent application install, test, lint, build, release, deploy, or rollback commands.
- State that the template is unconfigured, remote-disabled, and production-disabled by default.
- Describe Spec Kit as an optional compatible workflow reference, not bundled functionality or guaranteed compatibility.
- Do not claim certification, compliance, production readiness, deployment execution, or universal agent compatibility.

---

### Task 1: Add and validate the adoption guide

**Files:**
- Create: `README.md`
- Create: `tests/test_readme_guidance.py`
- Modify: `docs/superpowers/specs/2026-07-20-readme-guidance-design.md`

**Interfaces:**
- Consumes: `CLAUDE.md`, `.claude/README.md`, `.claude/project.yaml`, `requirements-policy.txt`, `scripts/validate-instructions.sh`, and the approved README design.
- Produces: a root onboarding entry point whose local links resolve and whose commands use only repository-supported tooling.

- [ ] **Step 1: Write the failing README contract test**

Create `tests/test_readme_guidance.py` with tests that:

```python
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"


class ReadmeGuidanceTest(unittest.TestCase):
    def setUp(self):
        self.text = README.read_text(encoding="utf-8") if README.exists() else ""

    def require_readme(self):
        self.assertTrue(README.exists(), "README.md must exist")

    def test_readme_has_adoption_first_sections_in_order(self):
        self.require_readme()
        headings = (
            "What this template provides",
            "Quick start",
            "Initialize the project policy",
            "Validate the template",
            "Start delivery work",
            "Authority and safe defaults",
            "Agent and Spec Kit compatibility",
            "Repository map",
            "Delivery scope",
            "Detailed guidance",
        )
        positions = [self.text.index(f"## {heading}") for heading in headings]
        self.assertEqual(positions, sorted(positions))

    def test_quick_start_uses_supported_commands(self):
        self.require_readme()
        for required in (
            "Use this template",
            "python3 -m venv .venv",
            "source .venv/bin/activate",
            "python -m pip install -r requirements-policy.txt",
            "bash scripts/validate-instructions.sh",
            ".claude/project.yaml",
        ):
            self.assertIn(required, self.text)

    def test_safety_and_compatibility_claims_are_bounded(self):
        self.require_readme()
        for required in (
            "project.lifecycle: unconfigured",
            "autonomous",
            "autonomous_with_enhanced_gates",
            "human_required",
            "prohibited",
            "most restrictive applicable outcome wins",
            "Claude-first",
            "not bundled",
            "Phase 2",
            "Deferred",
        ):
            self.assertIn(required, self.text)

    def test_local_markdown_links_resolve(self):
        self.require_readme()
        destinations = re.findall(r"\[[^]]+\]\(([^)]+)\)", self.text)
        for destination in destinations:
            if "://" in destination or destination.startswith("#"):
                continue
            path = destination.split("#", 1)[0]
            self.assertTrue((ROOT / path).exists(), destination)

    def test_readme_has_no_unresolved_authoring_markers(self):
        self.require_readme()
        self.assertNotRegex(self.text, r"\b(?:TBD|TODO|FIXME)\b")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the focused test and confirm the intended failure**

Run:

```bash
.venv/bin/python -m unittest tests.test_readme_guidance -v
```

Expected: FAIL because root `README.md` does not exist.

- [ ] **Step 3: Create the adoption-first `README.md`**

Use the exact ordered headings from Step 1. The quick start must contain:

```bash
git clone https://github.com/<your-account>/<your-repository>.git
cd <your-repository>
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-policy.txt
bash scripts/validate-instructions.sh
```

The initialization section must direct the reader to replace every placeholder
or `unknown` in `.claude/project.yaml` with repository or owner evidence, while
leaving remote and production permissions disabled until their mechanisms and
bounds are verified.

The authority section must define all four outcomes in a compact table and say:
"The most restrictive applicable outcome wins." The compatibility section must
state that the repository is Claude-first, that other agents must read and
follow the same files, and that Spec Kit is an optional design reference that is
not bundled or automatically compatibility-tested.

The repository map must link to the root kernel, operating guide, four YAML
control files, schemas, rules/workflows/profiles/templates, policy engine,
validator, and design document. The scope section must distinguish the current
MVP from Phase 2 and Deferred capabilities without promising remote adapters.

- [ ] **Step 4: Record written-spec approval**

Change the design status to:

```markdown
The README direction and written specification were approved by the user. The
implementation is authorized as of 2026-07-21.
```

Replace the superseded branch publication paragraph with:

```markdown
Implement the README on local `main`, commit only the approved documentation
and its focused contract test, then fast-forward `origin/main` as explicitly
authorized by the user. Preserve unrelated untracked files.
```

- [ ] **Step 5: Run focused and repository verification**

Run:

```bash
.venv/bin/python -m unittest tests.test_readme_guidance -v
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
bash scripts/validate-instructions.sh
bash -n scripts/validate-instructions.sh
bash -n scripts/validate-feature-context.sh
.venv/bin/python -m py_compile scripts/policy-engine.py
git diff --check
```

Expected: all tests and commands pass; the validator may emit its documented
repository-only warning when no live context is supplied.

- [ ] **Step 6: Commit and publish**

```bash
git add README.md tests/test_readme_guidance.py \
  docs/superpowers/specs/2026-07-20-readme-guidance-design.md \
  docs/superpowers/plans/2026-07-21-readme-guidance.md
git commit -m "docs: add repository adoption guide"
git push origin main
```

Expected: local `main`, `origin/main`, and GitHub's `main` all resolve to the
same commit. Preserve unrelated untracked files.
