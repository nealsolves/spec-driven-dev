import copy
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import yaml

from tests.helpers import ROOT, load_engine, temporary_repository


ENGINE_PATH = ROOT / "scripts/policy-engine.py"
CONTEXTS = ROOT / "tests/fixtures/contexts"
HASH_A = "a" * 64


def load_context(name):
    return yaml.safe_load((CONTEXTS / name).read_text(encoding="utf-8"))


def fact(value, source_ref, change_hash=HASH_A, corroboration=None):
    return {
        "value": value,
        "source_type": "diff_analysis",
        "source_ref": source_ref,
        "extractor": "repository-fact-extractor-v1",
        "confidence": 1.0,
        "observed_at_change": change_hash,
        "corroboration": corroboration or [],
    }


class PolicyEvaluationTest(unittest.TestCase):
    CASES = [
        ("maintenance-low.yaml", ["documentation_only"], "low", "autonomous"),
        (
            "authorization-high.yaml",
            ["security_sensitive", "production_impact"],
            "high",
            "autonomous_with_enhanced_gates",
        ),
        (
            "critical-migration.yaml",
            ["data_sensitive", "production_impact"],
            "critical",
            "prohibited",
        ),
    ]

    def setUp(self):
        self.engine = load_engine()
        self.bundle = self.engine.load_control_plane(ROOT)

    def test_table_driven_evaluation_outcomes(self):
        for filename, classifications, tier, outcome in self.CASES:
            with self.subTest(filename=filename):
                result = self.engine.evaluate(self.bundle, load_context(filename))

                self.assertTrue(result["valid"])
                for classification in classifications:
                    self.assertIn(classification, result["classifications"])
                self.assertEqual(result["risk"]["tier"], tier)
                self.assertEqual(result["authority"]["outcome"], outcome)
                self.assertEqual(
                    set(result["hashes"]),
                    {"policy_hash", "context_hash", "change_hash"},
                )
                self.assertTrue(
                    all(len(value) == 64 for value in result["hashes"].values())
                )

    def test_routes_are_additive_ordered_and_deduplicated(self):
        result = self.engine.evaluate(
            self.bundle, load_context("authorization-high.yaml")
        )

        self.assertEqual(
            result["classifications"],
            [
                "security_sensitive",
                "production_impact",
                "observability_impact",
                "release",
            ],
        )
        self.assertEqual(
            result["modules"],
            [
                "rules/engineering.md",
                "rules/testing.md",
                "rules/documentation.md",
                "rules/security.md",
                "rules/production-readiness.md",
                "rules/observability.md",
                "rules/release-management.md",
            ],
        )
        self.assertEqual(
            result["workflows"],
            ["workflows/feature-development.md", "workflows/release.md"],
        )

    def test_material_unknown_fact_fails_closed(self):
        with self.assertRaisesRegex(
            self.engine.PolicyInputError,
            "material fact 'modifies_authorization' is unknown",
        ):
            self.engine.evaluate(self.bundle, load_context("material-unknown.yaml"))

    def test_invalid_fact_value_fails_schema_validation(self):
        context = load_context("maintenance-low.yaml")
        context["facts"]["documentation_only"]["value"] = 7

        with self.assertRaisesRegex(
            self.engine.PolicyInputError, "context.facts.documentation_only.value"
        ):
            self.engine.evaluate(self.bundle, context)

    def test_stale_fact_evidence_fails_closed(self):
        context = load_context("maintenance-low.yaml")
        context["facts"]["documentation_only"]["observed_at_change"] = "f" * 64

        with self.assertRaisesRegex(
            self.engine.PolicyInputError, "documentation_only.*stale"
        ):
            self.engine.evaluate(self.bundle, context)

    def test_missing_or_escaping_evidence_path_fails_closed(self):
        for source_ref in ("tests/fixtures/evidence/missing.json", "../outside.json"):
            with self.subTest(source_ref=source_ref):
                context = load_context("maintenance-low.yaml")
                context["facts"]["documentation_only"]["source_ref"] = source_ref

                with self.assertRaises(self.engine.PolicyInputError):
                    self.engine.evaluate(self.bundle, context)

    def test_documentation_only_contradiction_fails_closed(self):
        context = load_context("maintenance-low.yaml")
        context["facts"]["modifies_runtime_code"] = fact(
            True, "tests/fixtures/evidence/authorization-diff.json"
        )

        with self.assertRaisesRegex(
            self.engine.PolicyInputError, "documentation_only.*contradicts"
        ):
            self.engine.evaluate(self.bundle, context)

    def test_negative_material_claim_requires_selective_corroboration(self):
        context = load_context("maintenance-low.yaml")
        context["facts"] = {
            "modifies_authorization": fact(
                False, "tests/fixtures/evidence/authorization-diff.json"
            )
        }

        with self.assertRaisesRegex(
            self.engine.PolicyInputError, "modifies_authorization.*corroboration"
        ):
            self.engine.evaluate(self.bundle, context)

        context["facts"]["modifies_authorization"]["corroboration"] = [
            {
                "source_type": "diff_analysis",
                "source_ref": "tests/fixtures/evidence/authorization-diff.json",
                "extractor": "repository-fact-extractor-v1",
                "confidence": 1.0,
                "observed_at_change": HASH_A,
            }
        ]
        with self.assertRaisesRegex(
            self.engine.PolicyInputError, "modifies_authorization.*independent"
        ):
            self.engine.evaluate(self.bundle, context)

        context["facts"]["modifies_authorization"]["corroboration"][0][
            "source_ref"
        ] = "./tests/fixtures/evidence/authorization-diff.json"
        with self.assertRaisesRegex(
            self.engine.PolicyInputError, "modifies_authorization.*independent"
        ):
            self.engine.evaluate(self.bundle, context)

        with temporary_repository() as root:
            evidence_dir = root / "evidence"
            evidence_dir.mkdir()
            primary = evidence_dir / "authorization.json"
            primary.write_text("{}\n")
            (evidence_dir / "authorization-alias.json").symlink_to(primary)
            bundle = self.engine.load_control_plane(root)
            aliased = load_context("maintenance-low.yaml")
            aliased["facts"] = {
                "modifies_authorization": fact(
                    False,
                    "evidence/authorization.json",
                    corroboration=[
                        {
                            "source_type": "path_analysis",
                            "source_ref": "evidence/authorization-alias.json",
                            "extractor": "repository-fact-extractor-v1",
                            "confidence": 0.99,
                            "observed_at_change": HASH_A,
                        }
                    ],
                )
            }
            with self.assertRaisesRegex(
                self.engine.PolicyInputError, "modifies_authorization.*independent"
            ):
                self.engine.evaluate(bundle, aliased)

        context["facts"]["modifies_authorization"]["corroboration"] = [
            {
                "source_type": "path_analysis",
                "source_ref": "tests/fixtures/evidence/authorization-corroboration.json",
                "extractor": "repository-fact-extractor-v1",
                "confidence": 0.97,
                "observed_at_change": HASH_A,
            }
        ]
        result = self.engine.evaluate(self.bundle, context)
        self.assertEqual(result["risk"]["tier"], "low")

    def test_risk_modifier_and_automatic_critical_override(self):
        authorization = self.engine.evaluate(
            self.bundle, load_context("authorization-high.yaml")
        )
        self.assertEqual(
            authorization["risk"]["modifiers"],
            [{"rule": "authorization_in_production", "minimum": "high"}],
        )

        context = load_context("maintenance-low.yaml")
        context["facts"] = {
            "writes_customer_data": fact(
                True, "tests/fixtures/evidence/authorization-diff.json"
            ),
            "adds_external_dependency": fact(
                True, "tests/fixtures/evidence/schema-diff.json"
            ),
        }
        raised = self.engine.evaluate(self.bundle, context)
        self.assertEqual(raised["risk"]["tier"], "critical")
        self.assertEqual(
            raised["risk"]["modifiers"],
            [{"rule": "customer_write_external", "raise_by": 1}],
        )

        context = load_context("maintenance-low.yaml")
        context["facts"] = {
            "credential_exposure": fact(
                True, "tests/fixtures/evidence/credential-scan.json"
            )
        }
        result = self.engine.evaluate(self.bundle, context)
        self.assertEqual(result["risk"]["tier"], "critical")
        self.assertEqual(
            result["risk"]["critical_overrides"], ["credential_exposure"]
        )

    def test_remote_disabled_project_overrides_autonomous_action_matrix(self):
        context = load_context("maintenance-low.yaml")
        context["action"] = "push_branch"

        result = self.engine.evaluate(self.bundle, context)

        self.assertEqual(result["authority"]["outcome"], "prohibited")
        self.assertIn(
            {
                "source": "project",
                "outcome": "prohibited",
                "rule": "remote_actions_disabled",
            },
            result["authority"]["applicable"],
        )

    def test_unconfigured_lifecycle_prohibits_enabled_remote_and_production_actions(self):
        remote_bundle = copy.deepcopy(self.bundle)
        remote_bundle["project"]["remote_actions"].update(
            {"enabled": True, "repository": "owner/repository", "push_branch": True}
        )
        push_context = load_context("maintenance-low.yaml")
        push_context["action"] = "push_branch"

        push_result = self.engine.evaluate(remote_bundle, push_context)

        self.assertEqual(push_result["authority"]["outcome"], "prohibited")
        self.assertTrue(
            any(
                item["rule"] == "unconfigured_remote_actions_disabled"
                for item in push_result["authority"]["applicable"]
            )
        )

        production_bundle = copy.deepcopy(self.bundle)
        production_bundle["project"]["production_actions"].update(
            {"enabled": True, "target": "production", "deploy": True}
        )
        deploy_context = load_context("maintenance-low.yaml")
        deploy_context["action"] = "deploy_production"

        deploy_result = self.engine.evaluate(production_bundle, deploy_context)

        self.assertEqual(deploy_result["authority"]["outcome"], "prohibited")
        self.assertTrue(
            any(
                item["rule"] == "unconfigured_production_actions_disabled"
                for item in deploy_result["authority"]["applicable"]
            )
        )

    def test_deny_overrides_selects_most_restrictive_outcome(self):
        context = load_context("maintenance-low.yaml")
        context["authority_constraints"] = [
            {
                "source": "workflow",
                "outcome": "autonomous",
                "rule": "workflow-default",
            },
            {
                "source": "regulated_overlay",
                "outcome": "human_required",
                "rule": "regulated-review",
            },
            {
                "source": "external_obligation",
                "outcome": "prohibited",
                "rule": "contractual-prohibition",
            },
        ]

        result = self.engine.evaluate(self.bundle, context)

        self.assertEqual(result["authority"]["outcome"], "prohibited")
        self.assertEqual(
            result["authority"]["selected"]["rule"], "contractual-prohibition"
        )

    def test_expired_exception_fails_and_critical_exception_is_prohibited(self):
        context = load_context("maintenance-low.yaml")
        context["exceptions"] = [
            {
                "id": "EXP-OLD",
                "tier": "low",
                "expires_at": "2000-01-01T00:00:00Z",
                "rationale": "Temporary compatibility gap.",
                "owner": "owner@example.com",
                "remediation_task": "ISSUE-1",
                "no_security_boundary_impact": True,
                "no_regulatory_impact": True,
            }
        ]
        with self.assertRaisesRegex(self.engine.PolicyInputError, "EXP-OLD.*expired"):
            self.engine.evaluate(self.bundle, context)

        context["exceptions"] = [
            {
                "id": "EXP-CRITICAL",
                "tier": "critical",
                "expires_at": "2099-01-01T00:00:00Z",
            }
        ]
        result = self.engine.evaluate(self.bundle, context)
        self.assertEqual(result["authority"]["outcome"], "prohibited")
        self.assertEqual(result["exceptions"][0]["outcome"], "prohibited")

    def test_unconfigured_project_prohibits_autonomous_low_risk_exception(self):
        context = load_context("maintenance-low.yaml")
        context["exceptions"] = [
            {
                "id": "EXP-LOW",
                "tier": "low",
                "expires_at": "2026-07-25T00:00:00Z",
                "rationale": "Temporary documentation compatibility gap.",
                "owner": "owner@example.com",
                "remediation_task": "ISSUE-2",
                "no_security_boundary_impact": True,
                "no_regulatory_impact": True,
            }
        ]

        result = self.engine.evaluate(
            self.bundle,
            context,
            now=datetime(2026, 7, 20, tzinfo=timezone.utc),
        )

        self.assertEqual(result["exceptions"][0]["outcome"], "autonomous")
        self.assertEqual(result["authority"]["outcome"], "prohibited")
        self.assertTrue(
            any(
                item["rule"] == "unconfigured_risk_exceptions_disabled"
                for item in result["authority"]["applicable"]
            )
        )

    def test_clarification_triage_resolves_defaults_and_escalates(self):
        context = load_context("maintenance-low.yaml")
        context["clarifications"] = [
            {
                "id": "CLAR-1",
                "class": "inferable",
                "question": "Which documentation convention applies?",
                "resolution": "Use the repository README convention.",
                "source_ref": "tests/fixtures/evidence/docs-diff.json",
            },
            {
                "id": "CLAR-2",
                "class": "reversible_default",
                "question": "Which local filename should be used?",
                "configured_default": "status.md",
                "reversal_path": "Rename before publication.",
            },
            {
                "id": "CLAR-3",
                "class": "material_business",
                "question": "How long should customer documents be retained?",
                "options": [
                    {
                        "id": "30-days",
                        "label": "30 days",
                        "consequence": "Lower privacy exposure with more user inconvenience.",
                    },
                    {
                        "id": "90-days",
                        "label": "90 days",
                        "consequence": "Balanced retention and storage cost.",
                    },
                ],
                "recommended_option": "90-days",
            },
        ]

        result = self.engine.evaluate(self.bundle, context)

        self.assertEqual(
            [item["action"] for item in result["clarifications"]],
            ["resolve_and_record", "apply_configured_default", "human_required"],
        )
        self.assertEqual(result["authority"]["outcome"], "human_required")
        packet = result["escalations"][0]
        self.assertEqual(packet["decision_id"], "DEC-maintenance-001-CLAR-3")
        self.assertEqual(packet["status"], "open")
        self.assertEqual(packet["hashes"], result["hashes"])
        self.assertEqual(packet["options"], context["clarifications"][2]["options"])
        self.assertEqual(packet["recommended_option"], "90-days")
        self.assertEqual(packet["resume_state"], "UNCLASSIFIED")
        self.assertTrue(packet["required_response"])

    def test_material_clarification_requires_actionable_unique_options(self):
        base = load_context("maintenance-low.yaml")
        material = {
            "id": "CLAR-MATERIAL",
            "class": "material_business",
            "question": "Choose a retention period.",
            "options": [
                {"id": "30-days", "consequence": "Lower privacy exposure."},
                {"id": "90-days", "consequence": "Higher storage cost."},
            ],
            "recommended_option": "90-days",
        }

        missing = copy.deepcopy(base)
        missing["clarifications"] = [
            {
                "id": "CLAR-MISSING",
                "class": "material_business",
                "question": "Choose a retention period.",
            }
        ]
        with self.assertRaisesRegex(
            self.engine.PolicyInputError, "'options' is a required property"
        ):
            self.engine.evaluate(self.bundle, missing)

        duplicate = copy.deepcopy(base)
        duplicate_material = copy.deepcopy(material)
        duplicate_material["options"][1]["id"] = "30-days"
        duplicate["clarifications"] = [duplicate_material]
        with self.assertRaisesRegex(
            self.engine.PolicyInputError, "option IDs must be unique"
        ):
            self.engine.evaluate(self.bundle, duplicate)

        invalid_recommendation = copy.deepcopy(base)
        invalid_material = copy.deepcopy(material)
        invalid_material["recommended_option"] = "indefinite"
        invalid_recommendation["clarifications"] = [invalid_material]
        with self.assertRaisesRegex(
            self.engine.PolicyInputError,
            "recommended_option.*does not name a supplied option",
        ):
            self.engine.evaluate(self.bundle, invalid_recommendation)

    def test_resource_limit_exhaustion_requires_human_authority(self):
        context = load_context("maintenance-low.yaml")
        context["resources"]["repair_attempts"] = 3

        result = self.engine.evaluate(self.bundle, context)

        self.assertEqual(result["resources"]["exhausted"], ["repair_attempts"])
        self.assertEqual(result["authority"]["outcome"], "human_required")

    def test_post_bootstrap_instruction_system_change_requires_human(self):
        bundle = copy.deepcopy(self.bundle)
        bundle["project"]["instruction_system"]["module_state"] = "complete"
        context = load_context("maintenance-low.yaml")
        context["facts"] = {
            "instruction_system_change": fact(
                True, "tests/fixtures/evidence/docs-diff.json"
            )
        }

        result = self.engine.evaluate(bundle, context)

        self.assertEqual(result["authority"]["outcome"], "human_required")
        self.assertTrue(
            any(
                item["rule"] == "post_bootstrap_instruction_system_change"
                for item in result["authority"]["applicable"]
            )
        )

    def test_policy_context_and_change_hash_boundaries(self):
        context = load_context("maintenance-low.yaml")
        baseline = self.engine.evaluate(self.bundle, context)

        with_response = copy.deepcopy(context)
        with_response["responses"] = [
            {
                "decision_id": "DEC-1",
                "selected_option": "option-1",
                "decided_by": "owner@example.com",
                "authority_basis": "repository_owner",
                "timestamp": "2026-07-20T12:00:00Z",
                "hashes": {
                    "policy_hash": "1" * 64,
                    "context_hash": "2" * 64,
                    "change_hash": HASH_A,
                },
            }
        ]
        response_result = self.engine.evaluate(self.bundle, with_response)
        self.assertNotEqual(
            baseline["hashes"]["context_hash"],
            response_result["hashes"]["context_hash"],
        )

        response_fields = {
            "selected_option": "option-2",
            "decided_by": "delegate@example.com",
            "authority_basis": "product_owner",
            "timestamp": "2026-07-20T13:00:00Z",
            "conditions": ["retention_period_days=90"],
        }
        for field, value in response_fields.items():
            with self.subTest(response_field=field):
                changed_response = copy.deepcopy(with_response)
                changed_response["responses"][0][field] = value
                changed_result = self.engine.evaluate(self.bundle, changed_response)
                self.assertNotEqual(
                    response_result["hashes"]["context_hash"],
                    changed_result["hashes"]["context_hash"],
                )

        prior_hashes_only = copy.deepcopy(with_response)
        prior_hashes_only["responses"][0]["hashes"] = {
            "policy_hash": "3" * 64,
            "context_hash": "4" * 64,
            "change_hash": "5" * 64,
        }
        prior_hashes_result = self.engine.evaluate(self.bundle, prior_hashes_only)
        self.assertEqual(
            response_result["hashes"]["context_hash"],
            prior_hashes_result["hashes"]["context_hash"],
        )

        changed_bundle = copy.deepcopy(self.bundle)
        changed_bundle["schemas"]["context"]["title"] += " updated"
        changed_policy = self.engine.evaluate(changed_bundle, context)
        self.assertNotEqual(
            baseline["hashes"]["policy_hash"],
            changed_policy["hashes"]["policy_hash"],
        )
        self.assertEqual(baseline["hashes"]["change_hash"], HASH_A)

    def test_context_hash_normalizes_embedded_evidence_hashes_only(self):
        context = load_context("maintenance-low.yaml")
        context["evidence"] = {
            "review_passed": {
                "satisfied": True,
                "source_ref": "tests/fixtures/evidence/docs-diff.json",
                "hashes": {
                    "policy_hash": "1" * 64,
                    "context_hash": "2" * 64,
                    "change_hash": HASH_A,
                },
            }
        }
        baseline = self.engine.evaluate(self.bundle, context)

        fixed_point = copy.deepcopy(context)
        fixed_point["evidence"]["review_passed"]["hashes"] = baseline["hashes"]
        fixed_point_result = self.engine.evaluate(self.bundle, fixed_point)
        self.assertEqual(
            baseline["hashes"]["context_hash"],
            fixed_point_result["hashes"]["context_hash"],
        )

        replaced_hashes = copy.deepcopy(context)
        replaced_hashes["evidence"]["review_passed"]["hashes"] = {
            "policy_hash": "3" * 64,
            "context_hash": "4" * 64,
            "change_hash": "5" * 64,
        }
        replaced = self.engine.evaluate(self.bundle, replaced_hashes)
        self.assertEqual(
            baseline["hashes"]["context_hash"], replaced["hashes"]["context_hash"]
        )

        changed_satisfaction = copy.deepcopy(context)
        changed_satisfaction["evidence"]["review_passed"]["satisfied"] = False
        satisfaction_result = self.engine.evaluate(
            self.bundle, changed_satisfaction
        )
        self.assertNotEqual(
            baseline["hashes"]["context_hash"],
            satisfaction_result["hashes"]["context_hash"],
        )

        changed_source = copy.deepcopy(context)
        changed_source["evidence"]["review_passed"][
            "source_ref"
        ] = "tests/fixtures/evidence/schema-diff.json"
        source_result = self.engine.evaluate(self.bundle, changed_source)
        self.assertNotEqual(
            baseline["hashes"]["context_hash"],
            source_result["hashes"]["context_hash"],
        )

    def test_lifecycle_evidence_references_must_exist_inside_repository(self):
        context = load_context("maintenance-low.yaml")
        template = {
            "satisfied": True,
            "source_ref": "tests/fixtures/evidence/docs-diff.json",
            "hashes": {
                "policy_hash": "1" * 64,
                "context_hash": "2" * 64,
                "change_hash": HASH_A,
            },
        }
        for source_ref in ("tests/fixtures/evidence/missing.json", "../outside.json"):
            with self.subTest(source_ref=source_ref):
                evidence = copy.deepcopy(template)
                evidence["source_ref"] = source_ref
                context["evidence"] = {"review_passed": evidence}

                with self.assertRaises(self.engine.PolicyInputError):
                    self.engine.evaluate(self.bundle, context)

    def test_constitutional_orders_are_schema_fixed_for_validation_and_evaluation(self):
        for section, key in (("risk", "tiers"), ("authority", "outcomes")):
            with self.subTest(validation=f"{section}.{key}"):
                with temporary_repository() as root:
                    policy_path = root / ".claude/policy.yaml"
                    policy = yaml.safe_load(policy_path.read_text())
                    policy[section][key].reverse()
                    policy_path.write_text(yaml.safe_dump(policy, sort_keys=False))

                    errors = self.engine.validate_bundle(root, None)

                self.assertTrue(
                    any(f"policy.{section}.{key}" in error for error in errors),
                    errors,
                )

        for key in ("tiers", "outcomes"):
            with self.subTest(key=key):
                bundle = copy.deepcopy(self.bundle)
                if key == "tiers":
                    bundle["policy"]["risk"][key].reverse()
                else:
                    bundle["policy"]["authority"][key].reverse()
                with self.assertRaisesRegex(
                    self.engine.PolicyInputError,
                    f"policy.(risk|authority).{key}",
                ):
                    self.engine.evaluate(
                        bundle, load_context("maintenance-low.yaml")
                    )

    def test_authority_constraint_action_uses_declared_action_vocabulary(self):
        context = load_context("maintenance-low.yaml")
        context["authority_constraints"] = [
            {
                "source": "external_obligation",
                "action": "pus_branch",
                "outcome": "prohibited",
                "rule": "typo-must-not-be-ignored",
            }
        ]

        with self.assertRaisesRegex(
            self.engine.PolicyInputError, r"authority_constraints\[0\].action"
        ):
            self.engine.evaluate(self.bundle, context)

    def test_evaluate_cli_stdout_output_file_and_input_error_contracts(self):
        command = [
            sys.executable,
            str(ENGINE_PATH),
            "evaluate",
            "--root",
            str(ROOT),
            "--context",
            str(CONTEXTS / "maintenance-low.yaml"),
        ]
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(payload["valid"])
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.stdout.count("\n"), 1)

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "decision.json"
            file_result = subprocess.run(
                command + ["--output", str(output)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(file_result.returncode, 0, file_result.stderr)
            self.assertEqual(file_result.stdout, f"{output}\n")
            self.assertEqual(json.loads(output.read_text()), payload)
            self.assertTrue(output.read_text().endswith("\n"))

        error_result = subprocess.run(
            command[:-1] + [str(CONTEXTS / "material-unknown.yaml")],
            check=False,
            capture_output=True,
            text=True,
        )
        error_payload = json.loads(error_result.stdout)
        self.assertEqual(error_result.returncode, 1)
        self.assertFalse(error_payload["valid"])
        self.assertNotIn("Traceback", error_result.stdout + error_result.stderr)
        self.assertEqual(error_result.stdout.count("\n"), 1)

    def test_public_cli_surface_rejects_undeclared_commands(self):
        result = subprocess.run(
            [sys.executable, str(ENGINE_PATH), "reconcile", "--root", str(ROOT)],
            check=False,
            capture_output=True,
            text=True,
        )

        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(payload["valid"])
        self.assertIn("ERROR: argument command", payload["errors"][0])
        self.assertNotIn("Traceback", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
