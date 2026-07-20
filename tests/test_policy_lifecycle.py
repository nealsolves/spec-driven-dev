import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from tests.helpers import ROOT, load_engine


ENGINE_PATH = ROOT / "scripts/policy-engine.py"
CONTEXTS = ROOT / "tests/fixtures/contexts"
EVIDENCE_REF = "tests/fixtures/evidence/docs-diff.json"
ZERO_HASH = "0" * 64


def load_yaml(name):
    return yaml.safe_load((CONTEXTS / name).read_text(encoding="utf-8"))


class PolicyLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.engine = load_engine()
        self.bundle = self.engine.load_control_plane(ROOT)

    def fresh_decision(self, bundle, context):
        decision = self.engine.evaluate(bundle, context)
        for record in context["evidence"].values():
            record["hashes"] = copy.deepcopy(decision["hashes"])
        return self.engine.evaluate(bundle, context)

    def context_with_evidence(
        self, *, state, workflow, required, action=None, bundle=None
    ):
        bundle = bundle or self.bundle
        context = load_yaml("maintenance-low.yaml")
        context["current_state"] = state
        context["workflow_family"] = workflow
        if action is not None:
            context["action"] = action
        context["evidence"] = {
            name: {
                "satisfied": True,
                "source_ref": EVIDENCE_REF,
                "hashes": {
                    "policy_hash": ZERO_HASH,
                    "context_hash": ZERO_HASH,
                    "change_hash": context["change_hash"],
                },
            }
            for name in required
        }
        decision = self.fresh_decision(bundle, context)
        self.assertTrue(
            all(record["hashes"] == decision["hashes"] for record in context["evidence"].values())
        )
        return context, decision

    def open_escalation(self):
        context = load_yaml("escalation-open.yaml")
        current = self.refresh_open_escalation(context)
        response = load_yaml("response-option-2.yaml")
        response["hashes"] = copy.deepcopy(current["hashes"])
        return context, response, current

    def refresh_open_escalation(self, context, bundle=None):
        bundle = bundle or self.bundle
        for _ in range(2):
            current = self.engine.evaluate(bundle, context)
            self.assertEqual(len(current["escalations"]), 1)
            context["open_escalation"] = copy.deepcopy(current["escalations"][0])
        current = self.engine.evaluate(bundle, context)
        self.assertEqual(context["open_escalation"], current["escalations"][0])
        self.assertEqual(context["open_escalation"]["hashes"], current["hashes"])
        return current

    def open_authority_escalation(self):
        context, _ = self.context_with_evidence(
            state="REVIEWING",
            workflow="maintenance",
            required=["required_reviews_passed", "required_ci_passed"],
        )
        context["resources"]["repair_attempts"] = 3
        for _ in range(2):
            decision = self.fresh_decision(self.bundle, context)
            self.assertEqual(decision["authority"]["outcome"], "human_required")
            self.assertEqual(len(decision["escalations"]), 1)
            context["current_state"] = "HUMAN_DECISION_REQUIRED"
            context["open_escalation"] = copy.deepcopy(decision["escalations"][0])
        current = self.fresh_decision(self.bundle, context)
        context["open_escalation"] = copy.deepcopy(current["escalations"][0])
        current = self.fresh_decision(self.bundle, context)
        self.assertEqual(context["open_escalation"], current["escalations"][0])
        response = {
            "decision_id": context["open_escalation"]["decision_id"],
            "selected_option": "authorize_once",
            "decided_by": "owner@example.com",
            "authority_basis": "repository_owner",
            "timestamp": "2026-07-20T12:00:00Z",
            "hashes": copy.deepcopy(current["hashes"]),
            "conditions": copy.deepcopy(
                context["open_escalation"]["options"][0].get("conditions", [])
            ),
        }
        return context, response, current

    def test_valid_maintenance_completion_returns_new_decision_without_mutation(self):
        context, decision = self.context_with_evidence(
            state="REVIEWING",
            workflow="maintenance",
            required=["required_reviews_passed", "required_ci_passed"],
        )
        original_context = copy.deepcopy(context)
        original_decision = copy.deepcopy(decision)

        result = self.engine.transition(self.bundle, context, decision, "COMPLETE")

        self.assertEqual(result["previous_state"], "REVIEWING")
        self.assertEqual(result["current_state"], "COMPLETE")
        self.assertEqual(result["context"]["current_state"], "COMPLETE")
        self.assertNotEqual(result["hashes"]["context_hash"], decision["hashes"]["context_hash"])
        self.assertEqual(result["transition"]["workflow_path"], "maintenance")
        self.assertEqual(result["transition"]["authorized_by_hashes"], decision["hashes"])
        self.assertEqual(context, original_context)
        self.assertEqual(decision, original_decision)
        self.assertIsNot(result, decision)

    def test_transition_rejects_state_skips_and_edges_outside_active_path(self):
        context, decision = self.context_with_evidence(
            state="CLASSIFIED",
            workflow="maintenance",
            required=["maintenance_scope_recorded"],
        )
        with self.assertRaisesRegex(self.engine.PolicyInputError, "active maintenance path"):
            self.engine.transition(self.bundle, context, decision, "REVIEWING")

        context, decision = self.context_with_evidence(
            state="CONVERGING",
            workflow="maintenance",
            required=["convergence_passed"],
        )
        with self.assertRaisesRegex(self.engine.PolicyInputError, "active maintenance path"):
            self.engine.transition(self.bundle, context, decision, "COMPLETE")

    def test_transition_requires_satisfied_existing_fresh_structured_evidence(self):
        context, decision = self.context_with_evidence(
            state="REVIEWING",
            workflow="maintenance",
            required=["required_reviews_passed", "required_ci_passed"],
        )
        for mutation, message in (
            (lambda value: value["evidence"].pop("required_ci_passed"), "required_ci_passed"),
            (
                lambda value: value["evidence"]["required_ci_passed"].update(satisfied=False),
                "not satisfied",
            ),
            (
                lambda value: value["evidence"]["required_ci_passed"].update(
                    source_ref="tests/fixtures/evidence/missing.json"
                ),
                "does not exist",
            ),
            (
                lambda value: value["evidence"]["required_ci_passed"]["hashes"].update(
                    policy_hash="f" * 64
                ),
                "stale",
            ),
        ):
            with self.subTest(message=message):
                changed = copy.deepcopy(context)
                changed_decision = decision
                mutation(changed)
                if message in {"required_ci_passed", "not satisfied"}:
                    fresh = self.engine.evaluate(self.bundle, changed)
                    for record in changed["evidence"].values():
                        record["hashes"] = copy.deepcopy(fresh["hashes"])
                    changed_decision = self.engine.evaluate(self.bundle, changed)
                with self.assertRaisesRegex(self.engine.PolicyInputError, message):
                    self.engine.transition(
                        self.bundle, changed, changed_decision, "COMPLETE"
                    )

    def test_each_terminal_path_completes_only_its_declared_route(self):
        cases = [
            ("code", "feature", "CONVERGING", ["convergence_passed"], None),
            ("release", "release", "RELEASE_READY", ["release_artifact_verified"], None),
            (
                "deployment",
                "feature",
                "VERIFYING",
                ["production_verification_passed"],
                "deploy_production",
            ),
            (
                "maintenance",
                "maintenance",
                "REVIEWING",
                ["required_reviews_passed", "required_ci_passed"],
                None,
            ),
        ]
        for path_name, workflow, state, required, action in cases:
            with self.subTest(path=path_name):
                bundle = self.bundle
                if path_name == "deployment":
                    bundle = copy.deepcopy(self.bundle)
                    bundle["project"]["project"].update(
                        {
                            "name": "delivery-template",
                            "repository": "owner/repository",
                            "lifecycle": "configured",
                        }
                    )
                    bundle["project"]["delivery"].update(
                        {
                            "owner": "owner@example.com",
                            "escalation_owner": "owner@example.com",
                        }
                    )
                    bundle["project"]["data"].update(
                        {"classifications": ["internal"], "regulated_data": "none"}
                    )
                    bundle["project"]["commands"] = {
                        name: "not_applicable"
                        for name in bundle["project"]["commands"]
                    }
                    bundle["project"]["spec_kit"].update(
                        {
                            "enabled": False,
                            "tested_version": "not_applicable",
                            "minimum_version": "not_applicable",
                        }
                    )
                    bundle["project"]["environments"]["configured"] = ["production"]
                    bundle["project"]["remote_actions"]["repository"] = "owner/repository"
                    bundle["project"]["production_actions"].update(
                        {
                            "enabled": True,
                            "target": "production",
                            "deploy": True,
                            "rollback": True,
                            "deploy_command": "deploy-tool production",
                            "rollback_command": "deploy-tool rollback production",
                        }
                    )
                context, decision = self.context_with_evidence(
                    state=state,
                    workflow=workflow,
                    required=required,
                    action=action,
                    bundle=bundle,
                )
                result = self.engine.transition(bundle, context, decision, "COMPLETE")
                self.assertEqual(result["transition"]["workflow_path"], path_name)
                self.assertEqual(result["current_state"], "COMPLETE")

    def test_every_exceptional_state_has_a_declared_nonempty_recovery(self):
        exceptional = set(self.bundle["lifecycle"]["exceptional_states"])
        recoveries = self.bundle["lifecycle"]["recoveries"]

        self.assertEqual(exceptional, set(recoveries))
        self.assertTrue(all(isinstance(value, str) and value for value in recoveries.values()))

    def test_escalation_packet_requires_a_normal_resume_state(self):
        context = load_yaml("escalation-open.yaml")
        self.assertEqual(self.engine._context_value_errors(self.bundle, context), [])

        missing = copy.deepcopy(context)
        del missing["open_escalation"]["resume_state"]
        self.assertTrue(self.engine._context_value_errors(self.bundle, missing))

        exceptional = copy.deepcopy(context)
        exceptional["open_escalation"]["resume_state"] = "BLOCKED_POLICY"
        self.assertTrue(
            self.engine._context_value_errors(self.bundle, exceptional)
        )

    def test_transition_rejects_stale_policy_context_and_change_decisions(self):
        context, decision = self.context_with_evidence(
            state="REVIEWING",
            workflow="maintenance",
            required=["required_reviews_passed", "required_ci_passed"],
        )
        for key in ("policy_hash", "context_hash", "change_hash"):
            with self.subTest(hash=key):
                stale = copy.deepcopy(decision)
                stale["hashes"][key] = "f" * 64
                with self.assertRaisesRegex(self.engine.PolicyInputError, key):
                    self.engine.transition(self.bundle, context, stale, "COMPLETE")

        changed_bundle = copy.deepcopy(self.bundle)
        changed_bundle["project"]["project"]["name"] = "changed-project"
        with self.assertRaisesRegex(self.engine.PolicyInputError, "policy_hash"):
            self.engine.transition(changed_bundle, context, decision, "COMPLETE")

    def test_transition_does_not_treat_evidence_as_human_authority_override(self):
        bundle = copy.deepcopy(self.bundle)
        bundle["project"]["instruction_system"]["module_state"] = "complete"
        context, _ = self.context_with_evidence(
            state="CONVERGING",
            workflow="instruction_system",
            required=["convergence_passed"],
            bundle=bundle,
        )
        context["facts"] = {
            "instruction_system_change": {
                "value": True,
                "source_type": "diff_analysis",
                "source_ref": EVIDENCE_REF,
                "extractor": "repository-fact-extractor-v1",
                "confidence": 1.0,
                "observed_at_change": context["change_hash"],
                "corroboration": [],
            }
        }
        decision = self.fresh_decision(bundle, context)
        self.assertEqual(decision["authority"]["outcome"], "human_required")

        with self.assertRaisesRegex(self.engine.PolicyInputError, "human_required"):
            self.engine.transition(bundle, context, decision, "COMPLETE")

        exhausted, _ = self.context_with_evidence(
            state="REVIEWING",
            workflow="maintenance",
            required=["required_reviews_passed", "required_ci_passed"],
        )
        exhausted["resources"]["repair_attempts"] = 3
        exhausted_decision = self.fresh_decision(self.bundle, exhausted)
        self.assertEqual(
            exhausted_decision["authority"]["outcome"], "human_required"
        )
        with self.assertRaisesRegex(self.engine.PolicyInputError, "human_required"):
            self.engine.transition(
                self.bundle, exhausted, exhausted_decision, "COMPLETE"
            )

    def test_response_requires_schema_valid_current_decision_and_option(self):
        context, response, _ = self.open_escalation()

        missing = copy.deepcopy(response)
        del missing["authority_basis"]
        with self.assertRaisesRegex(self.engine.PolicyInputError, "authority_basis"):
            self.engine.respond(self.bundle, context, missing)

        wrong_id = copy.deepcopy(response)
        wrong_id["decision_id"] = "DEC-other"
        with self.assertRaisesRegex(self.engine.PolicyInputError, "decision_id"):
            self.engine.respond(self.bundle, context, wrong_id)

        invalid_option = copy.deepcopy(response)
        invalid_option["selected_option"] = "option_404"
        with self.assertRaisesRegex(self.engine.PolicyInputError, "selected_option"):
            self.engine.respond(self.bundle, context, invalid_option)

    def test_response_rejects_changed_context_and_prohibited_outcomes(self):
        context, response, _ = self.open_escalation()
        changed = copy.deepcopy(context)
        changed["resources"]["ci_reruns"] = 1
        with self.assertRaisesRegex(self.engine.PolicyInputError, "context_hash"):
            self.engine.respond(self.bundle, changed, response)

        prohibited = copy.deepcopy(response)
        prohibited["selected_option"] = "option_3"
        with self.assertRaisesRegex(self.engine.PolicyInputError, "prohibited"):
            self.engine.respond(self.bundle, context, prohibited)

        action_prohibited = copy.deepcopy(context)
        action_prohibited["action"] = "push_branch"
        current = self.engine.evaluate(self.bundle, action_prohibited)
        action_prohibited["open_escalation"] = current["escalations"][0]
        prohibited_response = copy.deepcopy(response)
        prohibited_response["hashes"] = current["hashes"]
        with self.assertRaisesRegex(self.engine.PolicyInputError, "action.*prohibited"):
            self.engine.respond(self.bundle, action_prohibited, prohibited_response)

    def test_response_requires_human_decision_state_and_declared_recovery(self):
        context, response, _ = self.open_escalation()
        for state in ("CLASSIFIED", "BLOCKED_POLICY"):
            with self.subTest(state=state):
                wrong_state = copy.deepcopy(context)
                wrong_state["current_state"] = state
                with self.assertRaisesRegex(
                    self.engine.PolicyInputError, "HUMAN_DECISION_REQUIRED"
                ):
                    self.engine.respond(self.bundle, wrong_state, response)

        invalid_recovery = copy.deepcopy(self.bundle)
        invalid_recovery["lifecycle"]["recoveries"][
            "HUMAN_DECISION_REQUIRED"
        ] = "manual_override"
        with self.assertRaisesRegex(self.engine.PolicyInputError, "validated_response"):
            self.engine.respond(invalid_recovery, context, response)

    def test_resume_state_tampering_stales_old_packet_and_response_hashes(self):
        context, response, _ = self.open_escalation()
        context["open_escalation"]["resume_state"] = "COMPLETE"

        with self.assertRaisesRegex(self.engine.PolicyInputError, "context_hash"):
            self.engine.respond(self.bundle, context, response)

    def test_recomputed_hashes_cannot_authorize_terminal_or_cross_path_resume(self):
        terminal, _, _ = self.open_escalation()
        terminal["open_escalation"]["resume_state"] = "COMPLETE"
        terminal_current = self.refresh_open_escalation(terminal)
        terminal_response = load_yaml("response-option-2.yaml")
        terminal_response["hashes"] = terminal_current["hashes"]

        with self.assertRaisesRegex(self.engine.PolicyInputError, "terminal.*COMPLETE"):
            self.engine.respond(self.bundle, terminal, terminal_response)

        cross_path, _, _ = self.open_escalation()
        cross_path["workflow_family"] = "maintenance"
        cross_path["open_escalation"]["resume_state"] = "SPECIFIED"
        cross_current = self.refresh_open_escalation(cross_path)
        cross_response = load_yaml("response-option-2.yaml")
        cross_response["hashes"] = cross_current["hashes"]

        with self.assertRaisesRegex(self.engine.PolicyInputError, "active maintenance path"):
            self.engine.respond(self.bundle, cross_path, cross_response)

    def test_option_2_response_resolves_copy_records_conditions_and_reevaluates(self):
        context, response, current = self.open_escalation()
        original_context = copy.deepcopy(context)
        original_response = copy.deepcopy(response)

        result = self.engine.respond(self.bundle, context, response)

        updated = result["context"]
        self.assertEqual(updated["open_escalation"]["status"], "resolved")
        self.assertEqual(updated["responses"][-1]["selected_option"], "option_2")
        self.assertEqual(
            updated["responses"][-1]["conditions"], ["retention_period_days=90"]
        )
        self.assertEqual(updated["clarifications"][0]["resolution"], "option_2")
        self.assertEqual(updated["current_state"], "CLASSIFIED")
        self.assertEqual(result["resolved_escalation"]["resume_state"], "CLASSIFIED")
        self.assertEqual(result["decision"]["escalations"], [])
        self.assertEqual(result["decision"]["authority"]["outcome"], "autonomous")
        self.assertEqual(
            result["decision"]["hashes"],
            self.engine.evaluate(self.bundle, updated)["hashes"],
        )
        self.assertNotEqual(result["decision"]["hashes"], current["hashes"])
        self.assertEqual(context, original_context)
        self.assertEqual(response, original_response)

    def test_generic_authority_response_is_scoped_fresh_and_allows_transition(self):
        context, response, _ = self.open_authority_escalation()

        result = self.engine.respond(self.bundle, context, response)

        updated = result["context"]
        self.assertEqual(updated["current_state"], "REVIEWING")
        self.assertEqual(updated["open_escalation"]["status"], "resolved")
        self.assertEqual(result["decision"]["escalations"], [])
        self.assertEqual(
            result["decision"]["authority"]["outcome"],
            "autonomous_with_enhanced_gates",
        )
        approvals = [
            item for item in updated["authority_constraints"] if "approval" in item
        ]
        self.assertEqual(len(approvals), 1)
        self.assertEqual(
            approvals[0]["approval"]["decision_id"], response["decision_id"]
        )

        with self.assertRaisesRegex(
            self.engine.PolicyInputError, "HUMAN_DECISION_REQUIRED"
        ):
            self.engine.respond(self.bundle, updated, response)

        stale_scope = copy.deepcopy(updated)
        stale_scope["resources"]["ci_reruns"] = 1
        reevaluated = self.engine.evaluate(self.bundle, stale_scope)
        self.assertEqual(reevaluated["authority"]["outcome"], "human_required")
        self.assertEqual(len(reevaluated["escalations"]), 1)

        for evidence in updated["evidence"].values():
            evidence["hashes"] = copy.deepcopy(result["decision"]["hashes"])
        fresh = self.engine.evaluate(self.bundle, updated)
        transitioned = self.engine.transition(
            self.bundle, updated, fresh, "COMPLETE"
        )
        self.assertEqual(transitioned["current_state"], "COMPLETE")

    def test_idless_material_clarification_round_trips_with_fallback_id(self):
        context = load_yaml("escalation-open.yaml")
        context["current_state"] = "CLASSIFIED"
        context["open_escalation"] = None
        del context["clarifications"][0]["id"]

        initial = self.engine.evaluate(self.bundle, context)
        self.assertEqual(
            initial["escalations"][0]["decision"]["clarification_id"],
            "clarification-1",
        )
        self.assertEqual(initial["escalations"][0]["resume_state"], "CLASSIFIED")

        context["current_state"] = "HUMAN_DECISION_REQUIRED"
        context["open_escalation"] = initial["escalations"][0]
        current = self.engine.evaluate(self.bundle, context)
        context["open_escalation"] = current["escalations"][0]
        response = load_yaml("response-option-2.yaml")
        response["decision_id"] = "DEC-retention-001-clarification-1"
        response["hashes"] = current["hashes"]

        result = self.engine.respond(self.bundle, context, response)

        self.assertEqual(result["context"]["current_state"], "CLASSIFIED")
        self.assertEqual(
            result["context"]["clarifications"][0]["resolution"], "option_2"
        )
        self.assertEqual(result["decision"]["escalations"], [])

    def test_cli_transition_and_respond_preserve_json_and_output_contracts(self):
        context, decision = self.context_with_evidence(
            state="REVIEWING",
            workflow="maintenance",
            required=["required_reviews_passed", "required_ci_passed"],
        )
        escalation_context, response, _ = self.open_escalation()
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            context_path = temp / "context.yaml"
            decision_path = temp / "decision.json"
            escalation_path = temp / "escalation.yaml"
            response_path = temp / "response.yaml"
            context_path.write_text(yaml.safe_dump(context, sort_keys=False))
            decision_path.write_text(json.dumps(decision) + "\n")
            escalation_path.write_text(yaml.safe_dump(escalation_context, sort_keys=False))
            response_path.write_text(yaml.safe_dump(response, sort_keys=False))

            transition_command = [
                sys.executable,
                str(ENGINE_PATH),
                "transition",
                "--root",
                str(ROOT),
                "--context",
                str(context_path),
                "--decision",
                str(decision_path),
                "--to",
                "COMPLETE",
            ]
            transition_result = subprocess.run(
                transition_command, check=False, capture_output=True, text=True
            )
            self.assertEqual(transition_result.returncode, 0, transition_result.stderr)
            self.assertEqual(transition_result.stderr, "")
            self.assertEqual(transition_result.stdout.count("\n"), 1)
            self.assertEqual(json.loads(transition_result.stdout)["current_state"], "COMPLETE")

            output = temp / "response-decision.json"
            respond_result = subprocess.run(
                [
                    sys.executable,
                    str(ENGINE_PATH),
                    "respond",
                    "--root",
                    str(ROOT),
                    "--context",
                    str(escalation_path),
                    "--response",
                    str(response_path),
                    "--output",
                    str(output),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(respond_result.returncode, 0, respond_result.stderr)
            self.assertEqual(respond_result.stdout, f"{output}\n")
            self.assertEqual(json.loads(output.read_text())["decision"]["escalations"], [])

    def test_public_cli_surface_is_exactly_four_commands(self):
        result = subprocess.run(
            [sys.executable, str(ENGINE_PATH), "--help"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("{validate,evaluate,transition,respond}", result.stdout)
        self.assertNotIn("Traceback", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
