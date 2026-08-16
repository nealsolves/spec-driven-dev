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
            ".sdd/controls/project.yaml",
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

    def test_readme_identifies_canonical_and_generated_boundaries(self):
        for required in (
            "`.sdd/` is the authoritative source",
            "`.claude/` is generated compatibility output; do not edit it directly.",
            "scripts/render-compatibility.py --root . --check",
            "scripts/render-compatibility.py --root . --write",
            "The P0 legacy policy engine still reads `.claude/`.",
        ):
            self.assertIn(required, self.text)

    def test_authoring_links_target_canonical_sources(self):
        for required in (
            ".sdd/README.md",
            ".sdd/controls/project.yaml",
            ".sdd/modules/workflows/project-initialization.md",
            ".sdd/modules/templates/feature-instruction-context.md",
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
