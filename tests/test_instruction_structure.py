import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]

POSITIVE_TEMPLATE_COMPLIANCE_CLAIM = re.compile(
    r"\b(?:this |the |a )?template(?: (?:existence|presence))? "
    r"(?:proves?|demonstrates?|establishes?|ensures?|guarantees?) compliance\b",
    re.IGNORECASE,
)

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

WORKFLOW_HEADINGS = (
    "Entry criteria",
    "Artifacts",
    "Gates",
    "Ordered steps",
    "Evidence",
    "Exit criteria",
    "Solo mode",
    "Stop/escalation conditions",
)

WORKFLOW_TOPICS = {
    "project-initialization.md": (
        "project identity",
        "repository target",
        "project lifecycle",
        "allowed environments",
        "install, test, lint, typecheck, build, and release commands",
        "data classifications",
        "base profile",
        "regulated overlay",
        "financial limits",
        "remote-action permissions",
        "production permissions",
        "deployment mechanism",
        "rollback mechanism",
        "spec kit compatibility",
        "escalation owner",
        "external obligations",
        "preserve unknown",
        "autonomous risk exceptions",
    ),
    "instruction-system-change.md": (
        "prior trusted policy",
        "before and after",
        "sensitive weakening",
        "control-plane version increment",
        "cannot authorize itself",
        "human_required",
        "bootstrap",
    ),
    "feature-development.md": (
        "constitution",
        "specify",
        "clarify",
        "plan",
        "checklist",
        "tasks",
        "analyze",
        "implement",
        "converge",
        "material_business",
        "escalation packet",
    ),
    "bug-fix.md": (
        "simple regression",
        "behavior clarification",
        "security defect",
        "incident follow-up",
        "regression test",
        "characterization test",
        "risk reevaluation",
    ),
    "maintenance.md": (
        "documentation",
        "formatting",
        "rename",
        "non-behavioral refactor",
        "hygiene",
        "maintenance id",
        "reduced lifecycle",
        "validation",
        "review",
    ),
    "dependency-update.md": (
        "reason",
        "version delta",
        "changelog",
        "security",
        "license",
        "compatibility tests",
        "lockfile",
        "rollback",
        "runtime-critical",
    ),
    "brownfield-change.md": (
        "actual behavior",
        "characterization tests",
        "consumer impact",
        "telemetry",
        "data evidence",
        "spec reconciliation",
        "migration",
        "deprecation",
    ),
    "release.md": (
        "release readiness",
        "exact-commit ci",
        "authority evaluation",
        "rollback",
        "monitoring",
        "verification",
        "phase 2",
    ),
    "incident-hotfix.md": (
        "stabilize first",
        "smallest safe change",
        "reduced gates",
        "no silent bypass",
        "incident record",
        "regression test",
        "spec updates",
        "restoration",
        "root cause",
    ),
}

PROFILE_TOPICS = {
    "solo-developer.md": (
        "base profile",
        "one person",
        "automated gates",
        "risk-bounded review",
        "written exceptions",
        "repeatable deployment",
        "audit trail",
        "separate-model challenge",
        "no default second-human",
    ),
    "team.md": (
        "base profile",
        "codeowners",
        "author/approver separation",
        "path-sensitive",
        "security",
        "data",
        "platform",
        "release authority",
        "emergency authority",
    ),
    "regulated.md": (
        "overlay",
        "external control mapping",
        "evidence retention",
        "required approvers",
        "segregation",
        "override solo allowances",
        "exception authority",
        "auditability",
        "does not claim certification",
    ),
    "prototype.md": (
        "base profile",
        "non-production",
        "no real regulated data",
        "no production secrets",
        "no implied readiness",
        "promotion exit criteria",
    ),
}

TEMPLATE_FIELDS = {
    "feature-instruction-context.md": (
        "Profile and overlays",
        "Classifications",
        "Observable facts",
        "Risk",
        "Authority",
        "Readiness profile",
        "Data profile",
        "Control profile",
        "Policy hash",
        "Context hash",
        "Change hash",
        "Lifecycle state",
        "Loaded-module checklist",
        "Not-applicable table",
        "Evidence table",
        "Clarifications",
        "Exceptions",
        "Escalation status",
    ),
    "adr-template.md": (
        "Title",
        "Status",
        "Date",
        "Context",
        "Decision",
        "Alternatives",
        "Consequences",
        "Security and privacy",
        "Operations",
        "Cost",
        "Migration and reversal",
        "References",
    ),
    "threat-model-template.md": (
        "Scope",
        "Assets",
        "Actors",
        "Trust boundaries",
        "Data flows",
        "Threats",
        "Mitigations",
        "Residual risk",
        "Verification",
        "Owner",
    ),
    "privacy-assessment-template.md": (
        "Categories",
        "Purpose",
        "Collection",
        "Storage",
        "Retention",
        "Access",
        "Processors and sharing",
        "Residency",
        "Deletion",
        "Non-production",
        "Logging",
        "AI use",
        "Risks",
        "Controls",
    ),
    "production-readiness-template.md": (
        "Level",
        "Environments",
        "Dependencies",
        "Configuration",
        "Migrations",
        "Deployment",
        "Rollback",
        "Health",
        "Capacity",
        "Backups",
        "Recovery",
        "Runbooks",
        "Ownership",
        "Verification",
        "Residual risk",
    ),
    "observability-plan-template.md": (
        "Journeys",
        "SLIs",
        "SLO and rationale",
        "Logs",
        "Metrics",
        "Traces",
        "Audit events",
        "Dashboards",
        "Alerts",
        "Ownership",
        "Redaction",
        "Retention",
        "Cost and cardinality",
        "Verification",
    ),
    "compliance-mapping-template.md": (
        "Control profile",
        "Requirement",
        "Implementation",
        "Evidence",
        "Owner",
        "Status",
        "Exception",
        "Revalidation date",
    ),
    "risk-exception-template.md": (
        "Waived requirement",
        "Rationale",
        "Scope",
        "Tier",
        "Impact",
        "Compensation",
        "Owner",
        "Policy authority",
        "Expiration",
        "Remediation and follow-up",
        "Issue, PR, and spec links",
    ),
    "release-readiness-template.md": (
        "Version",
        "Scope",
        "CI commit",
        "Artifacts",
        "SBOM, provenance, and signing",
        "Compatibility",
        "Migrations",
        "Deployment",
        "Rollback",
        "Monitoring",
        "Authority",
        "Verification",
    ),
    "incident-record-template.md": (
        "Timeline",
        "Impact",
        "Detection",
        "Containment",
        "Recovery",
        "Root cause",
        "Contributors",
        "Corrective actions",
        "Regression tests",
        "Spec changes",
        "Owner",
    ),
    "maintenance-record-template.md": (
        "Change type and ID",
        "Scope",
        "Behavior impact",
        "Facts",
        "Risk",
        "Activated modules",
        "Validation and review evidence",
        "Rollback",
        "Policy hash",
        "Context hash",
        "Change hash",
        "Authority",
        "PR link",
    ),
}


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class InstructionStructureTest(unittest.TestCase):
    def test_workflow_directory_matches_routing_manifest(self):
        routing = yaml.safe_load(read(".claude/routing.yaml"))
        routing_paths = set(routing["workflow_rules"].values())
        for route in routing["routes"].values():
            routing_paths.update(route.get("workflows", []))
        expected_paths = {f"workflows/{name}" for name in WORKFLOW_TOPICS}
        workflow_root = ROOT / ".claude/workflows"
        actual_paths = (
            {f"workflows/{path.name}" for path in workflow_root.glob("*.md")}
            if workflow_root.is_dir()
            else set()
        )
        self.assertEqual(routing_paths, expected_paths)
        self.assertEqual(actual_paths, expected_paths)

    def test_workflows_have_required_contracts_and_topics(self):
        for name, topics in WORKFLOW_TOPICS.items():
            with self.subTest(workflow=name):
                content = read(f".claude/workflows/{name}")
                self.assertEqual(
                    tuple(re.findall(r"(?m)^## (.+)$", content)),
                    WORKFLOW_HEADINGS,
                    f"{name}: structural headings must match the workflow contract",
                )
                lowered = re.sub(r"\s+", " ", content.lower())
                for topic in topics:
                    self.assertIn(topic.lower(), lowered, f"{name}: missing {topic}")

    def test_project_initialization_names_every_project_field(self):
        project = yaml.safe_load(read(".claude/project.yaml"))

        def leaf_paths(value, prefix=""):
            paths = []
            if isinstance(value, dict):
                for key, item in value.items():
                    path = f"{prefix}.{key}" if prefix else key
                    paths.extend(leaf_paths(item, path))
            else:
                paths.append(prefix)
            return paths

        initialization = read(".claude/workflows/project-initialization.md")
        for path in leaf_paths(project):
            self.assertIn(f"`{path}`", initialization, f"missing project field {path}")

    def test_profiles_are_complete_and_distinguish_base_from_overlay(self):
        profile_root = ROOT / ".claude/profiles"
        actual = (
            {path.name for path in profile_root.glob("*.md")}
            if profile_root.is_dir()
            else set()
        )
        self.assertEqual(actual, set(PROFILE_TOPICS))
        for name, topics in PROFILE_TOPICS.items():
            with self.subTest(profile=name):
                content = re.sub(
                    r"\s+", " ", read(f".claude/profiles/{name}").lower()
                )
                for topic in topics:
                    self.assertIn(topic.lower(), content, f"{name}: missing {topic}")

    def test_templates_are_fillable_and_have_required_fields(self):
        template_root = ROOT / ".claude/templates"
        actual = (
            {path.name for path in template_root.glob("*.md")}
            if template_root.is_dir()
            else set()
        )
        self.assertEqual(actual, set(TEMPLATE_FIELDS))
        for name, fields in TEMPLATE_FIELDS.items():
            with self.subTest(template=name):
                content = read(f".claude/templates/{name}")
                self.assertIn("<", content, f"{name}: template must be fillable")
                for field in fields:
                    self.assertRegex(
                        content,
                        rf"(?im)^\*\*{re.escape(field)}:\*\*",
                        f"{name}: missing form field {field}",
                    )
                normalized = content.lower().replace(" ", "_")
                for freshness_hash in ("policy_hash", "context_hash", "change_hash"):
                    self.assertIn(
                        freshness_hash,
                        normalized,
                        f"{name}: missing {freshness_hash}",
                    )

    def test_completed_module_installation_is_non_bypassable(self):
        project = yaml.safe_load(read(".claude/project.yaml"))
        self.assertEqual(project["instruction_system"]["module_state"], "complete")

    def test_rule_directory_matches_routing_manifest(self):
        routing = yaml.safe_load(read(".claude/routing.yaml"))
        routing_paths = set(routing["always"]["rules"])
        for route in routing["routes"].values():
            routing_paths.update(route.get("rules", []))
        expected_paths = {f"rules/{name}" for name in RULE_TOPICS}
        actual_paths = {
            f"rules/{path.name}" for path in (ROOT / ".claude/rules").glob("*.md")
        }
        self.assertEqual(routing_paths, expected_paths)
        self.assertEqual(actual_paths, expected_paths)

    def test_rule_modules_have_required_contracts_and_topics(self):
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
                self.assertIsNone(
                    POSITIVE_TEMPLATE_COMPLIANCE_CLAIM.search(lowered), name
                )

    def test_template_compliance_check_distinguishes_negation_from_claim(self):
        self.assertIsNone(
            POSITIVE_TEMPLATE_COMPLIANCE_CLAIM.search(
                "Template presence does not prove compliance."
            )
        )
        for positive_claim in (
            "This template proves compliance.",
            "Template presence demonstrates compliance.",
            "A template guarantees compliance.",
        ):
            with self.subTest(positive_claim=positive_claim):
                self.assertIsNotNone(
                    POSITIVE_TEMPLATE_COMPLIANCE_CLAIM.search(positive_claim)
                )

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
