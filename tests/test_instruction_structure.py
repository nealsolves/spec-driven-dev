import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class InstructionStructureTest(unittest.TestCase):
    def test_root_kernel_is_compact_and_has_required_sections(self):
        root = read("CLAUDE.md")
        self.assertLessEqual(len(root.splitlines()), 350)
        for heading in (
            "Purpose and Scope",
            "Project Identity",
            "Authority Hierarchy",
            "Startup Protocol",
            "Universal Invariants",
            "Lifecycle",
            "Deterministic Routing",
            "Git, Pull Requests, and CI",
            "Exceptions",
            "Human Escalation",
            "Definition of Done",
        ):
            self.assertRegex(root, rf"(?m)^## (?:\d+\. )?{re.escape(heading)}$")

    def test_root_names_every_lifecycle_state(self):
        root = read("CLAUDE.md")
        states = (
            "UNCLASSIFIED",
            "CLASSIFIED",
            "SPECIFIED",
            "CLARIFIED",
            "PLANNED",
            "TASKED",
            "ANALYZED",
            "IMPLEMENTING",
            "VALIDATING",
            "REVIEWING",
            "CONVERGING",
            "RELEASE_READY",
            "DEPLOYING",
            "VERIFYING",
            "COMPLETE",
            "BLOCKED_REQUIREMENT",
            "BLOCKED_POLICY",
            "BLOCKED_TECHNICAL",
            "HUMAN_DECISION_REQUIRED",
            "ROLLBACK_REQUIRED",
            "INCIDENT",
        )
        for state in states:
            self.assertIn(state, root)

    def test_root_has_exact_ci_authority_and_policy_gated_publication(self):
        root = read("CLAUDE.md")
        self.assertIn(
            "Required CI on the exact merge candidate is authoritative for merge.",
            root,
        )
        self.assertIn("only when the authority policy permits", root)
        self.assertNotIn("will be committed and pushed", root.lower())

    def test_root_links_control_plane_and_operating_guide(self):
        root = read("CLAUDE.md")
        for target in (
            ".claude/project.yaml",
            ".claude/routing.yaml",
            ".claude/policy.yaml",
            ".claude/lifecycle.yaml",
            ".claude/README.md",
        ):
            self.assertRegex(root, rf"\[[^\]]+\]\({re.escape(target)}\)")

    def test_root_selects_workflow_before_optional_feature(self):
        root = read("CLAUDE.md")
        self.assertIn("Determine the workflow family before resolving a feature", root)
        self.assertIn("implementation_status.md does not select the active feature", root)

    def test_authority_hierarchy_is_complete_and_ordered(self):
        root = read("CLAUDE.md")
        hierarchy = (
            "External law and contract",
            "Constitution",
            "Approved active artifacts",
            "Active project policy and loaded modules",
            "Root kernel",
            "Implementation, telemetry, data, and consumer behavior",
            "Conventional practice",
        )
        positions = [root.index(item) for item in hierarchy]
        self.assertEqual(positions, sorted(positions))

    def test_root_states_safe_defaults_and_decision_outcomes(self):
        root = read("CLAUDE.md")
        self.assertIn("unconfigured", root)
        self.assertIn("remote and production actions are disabled", root)
        for outcome in (
            "autonomous",
            "autonomous_with_enhanced_gates",
            "human_required",
            "prohibited",
        ):
            self.assertIn(outcome, root)

    def test_root_governs_post_bootstrap_instruction_changes(self):
        root = read("CLAUDE.md")
        self.assertIn(
            "every instruction-system change is\n  `human_required` in the MVP",
            root,
        )
        self.assertIn("a proposed policy cannot approve its own revision", root)

    def test_operating_guide_documents_current_scope_and_compatibility(self):
        guide = read(".claude/README.md")
        for heading in (
            "Three Layers",
            "Startup Sequence",
            "Four-File Control Plane",
            "Schemas and Policy Engine",
            "Project Initialization",
            "Feature and Maintenance Context",
            "Delivery Boundary",
            "Legacy Manifest Mapping",
        ):
            self.assertRegex(guide, rf"(?m)^## {re.escape(heading)}$")
        for command in ("validate", "evaluate", "transition", "respond"):
            self.assertIn(f"policy-engine.py {command}", guide)
        self.assertIn("Spec Kit v0.13.0", guide)
        self.assertIn("design reference", guide.lower())
        self.assertIn("MVP", guide)
        self.assertIn("Phase 2", guide)
        self.assertIn("Deferred", guide)
        for old, new in (
            ("instructions.yaml + classification-rules.yaml", "routing.yaml"),
            ("project-profile.yaml", "project.yaml"),
            ("authority/risk/exception/resource policy", "policy.yaml"),
            (
                "evidence requirements + state transitions",
                "lifecycle.yaml + context schema",
            ),
        ):
            self.assertRegex(guide, rf"(?s){re.escape(old)}.*{re.escape(new)}")
        self.assertNotRegex(
            guide.lower(),
            r"(implements|provides) (vendor|github|deployment|release) (adapter|orchestrator)",
        )

    def test_constitution_defines_required_governing_principles(self):
        constitution = read(".specify/memory/constitution.md")
        for principle in (
            "Autonomy Within Authority",
            "Spec-Driven Intent",
            "Test-First Evidence",
            "Security and Privacy Boundaries",
            "Deterministic Policy",
            "Reversible Delivery",
            "Amendment Discipline",
        ):
            self.assertIn(principle, constitution)

    def test_status_template_has_required_fields_and_states(self):
        status = read("implementation_status.md")
        for field in (
            "Active change",
            "Active branch",
            "Active profile",
            "Open pull requests",
            "Current gate",
            "Deliverables",
            "Risks",
            "Deferred items",
            "Last verified main commit",
            "Last deployment",
        ):
            self.assertIn(field, status)
        for state in (
            "not started",
            "in progress",
            "in review",
            "merged",
            "deployed",
            "blocked",
            "deferred",
        ):
            self.assertRegex(status.lower(), rf"\b{re.escape(state)}\b")


if __name__ == "__main__":
    unittest.main()
