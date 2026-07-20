import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

RULE_HEADINGS = (
    "Purpose",
    "Applicability",
    "Required inputs",
    "Mandatory controls",
    "Evidence",
    "Exceptions",
    "Solo interpretation",
    "Overlay notes",
    "Completion checklist",
)

RULE_TOPICS = {
    "engineering.md": (
        "reversible changes",
        "strict tooling",
        "boundary validation",
        "typed errors",
        "dependency and configuration discipline",
        "structured logging",
        "unsafe casts",
        "complexity",
        "generated code",
        "branch, commit, and pull request traceability",
        "brownfield compatibility",
        "correctness review",
        "maintainability review",
        "regression review",
        "concurrency review",
        "performance review",
        "contract review",
        "tool-equivalent fallback",
    ),
    "testing.md": (
        "red before green",
        "characterization tests",
        "unit tests",
        "contract tests",
        "integration tests",
        "end-to-end tests",
        "sandbox boundaries",
        "production boundaries",
        "acceptance and contract mapping",
        "schemas, migrations, and rollback",
        "snapshots",
        "changed-code coverage",
        "risk coverage",
        "determinism",
        "flaky tests",
        "performance and resilience triggers",
        "unit tests for every function",
        "live production tests",
    ),
    "security.md": (
        "threat triggers",
        "trust boundaries",
        "authentication and authorization",
        "least privilege",
        "secrets",
        "ssrf",
        "injection",
        "path traversal",
        "deserialization",
        "cryptography",
        "dependencies and actions",
        "sast",
        "dependency scan",
        "secret scan",
        "sbom",
        "provenance",
        "signing",
        "container and iac triggers",
        "findings and exceptions",
        "break-glass",
        "solo adversarial review",
    ),
    "architecture.md": (
        "adr triggers",
        "simplicity",
        "technology selection",
        "buy, build, or adopt",
        "service, module, and data boundaries",
        "api and event compatibility",
        "versioning",
        "dependency direction",
        "failure modes",
        "resilience",
        "capacity",
        "cost",
        "reversibility",
        "brownfield reconciliation",
        "diagram proportionality",
    ),
    "data-privacy.md": (
        "data classification",
        "minimization",
        "purpose limitation",
        "retention and deletion",
        "encryption",
        "access and audit",
        "masking",
        "residency",
        "production-data restrictions",
        "test data",
        "pii logging",
        "privacy assessment",
        "processors",
        "ai data",
        "data-flow evidence",
    ),
    "production-readiness.md": (
        "level 0",
        "level 1",
        "level 2",
        "level 3",
        "environments",
        "infrastructure as code",
        "configuration",
        "migrations",
        "compatibility",
        "feature flags",
        "health checks",
        "deployment",
        "rollback",
        "backup",
        "capacity",
        "recovery",
        "runbooks",
        "ownership",
        "verification",
        "monitoring",
        "decommissioning",
        "break-glass",
    ),
    "observability.md": (
        "minor feature",
        "critical journey",
        "new service",
        "regulated flow",
        "logs",
        "metrics",
        "traces",
        "correlation",
        "audit events",
        "sli",
        "slo",
        "error budget",
        "dashboards",
        "alerts",
        "ownership",
        "cost and cardinality",
        "retention",
        "redaction",
        "testing",
        "production verification",
    ),
    "release-management.md": (
        "versioning",
        "changelog and release notes",
        "policy authority",
        "exact-commit ci",
        "artifacts",
        "sbom",
        "provenance",
        "signing",
        "promotion",
        "compatibility",
        "migrations",
        "progressive delivery",
        "rollback criteria",
        "emergency release",
        "validation",
        "deprecation",
        "release evidence",
    ),
    "compliance.md": (
        "framework-neutral",
        "profile-driven",
        "declared control profiles",
        "requirement mapping",
        "evidence",
        "owners",
        "exceptions and compensating controls",
        "retention",
        "revalidation",
        "external authority",
        "soc 2",
        "iso 27001",
        "hipaa",
        "pci dss",
        "template presence does not prove compliance",
    ),
    "ownership.md": (
        "product role",
        "architecture role",
        "development role",
        "review role",
        "security role",
        "data role",
        "release role",
        "operations role",
        "risk role",
        "solo role collapse",
        "team separation",
        "ai advisory status",
        "policy-bounded autonomy",
        "regulated overrides",
    ),
    "ai-systems.md": (
        "model and provider approval",
        "prompt and version tracking",
        "prompt injection",
        "tool authorization",
        "output validation",
        "retention and training",
        "cost and retries",
        "evaluations",
        "goldens",
        "hallucination handling",
        "human authority",
        "fallbacks",
        "observability",
        "safety and abuse",
        "reproducibility",
        "regional and vendor limits",
    ),
    "documentation.md": (
        "documentation as done",
        "decision, api, and operations synchronization",
        "runbooks",
        "generated documentation",
        "status",
        "link, do not copy",
        "durable versus volatile information",
        "markdown quality",
        "broken links",
    ),
}


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class InstructionStructureTest(unittest.TestCase):
    def test_rule_directory_matches_routing_manifest(self):
        routing_paths = set(
            re.findall(r"rules/[a-z0-9-]+\.md", read(".claude/routing.yaml"))
        )
        expected_paths = {f"rules/{name}" for name in RULE_TOPICS}
        actual_paths = {
            f"rules/{path.name}" for path in (ROOT / ".claude/rules").glob("*.md")
        }
        self.assertEqual(routing_paths, expected_paths)
        self.assertEqual(actual_paths, expected_paths)

    def test_rule_modules_have_required_contracts_and_topics(self):
        prohibited_claim = re.compile(
            r"template (?:existence|presence).*?(?:proves?|demonstrates?|establishes?) "
            r"compliance",
            re.IGNORECASE | re.DOTALL,
        )
        for name, topics in RULE_TOPICS.items():
            with self.subTest(rule=name):
                content = read(f".claude/rules/{name}")
                self.assertEqual(
                    tuple(re.findall(r"(?m)^## (.+)$", content)),
                    RULE_HEADINGS,
                    f"{name}: structural headings must match the rule contract",
                )
                for heading in RULE_HEADINGS:
                    self.assertRegex(
                        content,
                        rf"(?m)^## {re.escape(heading)}$",
                        f"{name}: missing {heading}",
                    )
                lowered = re.sub(r"\s+", " ", content.lower())
                for topic in topics:
                    self.assertIn(topic, lowered, f"{name}: missing {topic}")
                if name != "compliance.md":
                    self.assertIsNone(prohibited_claim.search(content), name)

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
