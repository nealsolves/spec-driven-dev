import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

import yaml

from tests.helpers import ROOT, load_engine, temporary_repository


ENGINE_PATH = ROOT / "scripts/policy-engine.py"


class PolicyValidationTest(unittest.TestCase):
    def setUp(self):
        self.engine = load_engine()

    def test_canonical_hash_is_independent_of_mapping_order(self):
        expected = hashlib.sha256(b'{"a":1,"b":2}').hexdigest()

        self.assertEqual(self.engine.canonical_hash({"b": 2, "a": 1}), expected)
        self.assertEqual(
            self.engine.canonical_hash({"b": 2, "a": 1}),
            self.engine.canonical_hash({"a": 1, "b": 2}),
        )

    def test_load_control_plane_returns_all_controls_and_schemas(self):
        bundle = self.engine.load_control_plane(ROOT)

        self.assertEqual(
            set(bundle),
            {"root", "project", "routing", "policy", "lifecycle", "schemas"},
        )
        self.assertEqual(set(bundle["schemas"]), {"project", "routing", "policy", "context"})

    def test_repository_control_plane_is_valid(self):
        self.assertEqual(self.engine.validate_bundle(ROOT, None), [])

    def test_unknown_top_level_control_key_fails_actionably(self):
        with temporary_repository() as root:
            project_path = root / ".claude/project.yaml"
            project = yaml.safe_load(project_path.read_text())
            project["unexpected"] = True
            project_path.write_text(yaml.safe_dump(project, sort_keys=False))

            errors = self.engine.validate_bundle(root, None)

        self.assertTrue(errors)
        self.assertTrue(all(error.startswith("ERROR:") for error in errors))
        self.assertTrue(any("project" in error and "unexpected" in error for error in errors))

    def test_duplicate_yaml_key_fails_actionably(self):
        with temporary_repository() as root:
            project_path = root / ".claude/project.yaml"
            project_path.write_text(project_path.read_text() + "schema_version: 1\n")

            errors = self.engine.validate_bundle(root, None)

        self.assertEqual(len(errors), 1)
        self.assertIn("project: invalid YAML", errors[0])
        self.assertIn("duplicate key 'schema_version'", errors[0])

    def test_unknown_classification_route_fails(self):
        with temporary_repository() as root:
            routing_path = root / ".claude/routing.yaml"
            routing = yaml.safe_load(routing_path.read_text())
            routing["classification_rules"][0]["add"] = ["missing_route"]
            routing_path.write_text(yaml.safe_dump(routing, sort_keys=False))

            errors = self.engine.validate_bundle(root, None)

        self.assertIn(
            "ERROR: routing.classification_rules[0].add: unknown route 'missing_route'",
            errors,
        )

    def test_unknown_overlay_route_fails(self):
        with temporary_repository() as root:
            routing_path = root / ".claude/routing.yaml"
            routing = yaml.safe_load(routing_path.read_text())
            routing["overlay_rules"] = [
                {"overlay": "regulated", "add": ["missing_route"]}
            ]
            routing_path.write_text(yaml.safe_dump(routing, sort_keys=False))

            errors = self.engine.validate_bundle(root, None)

        self.assertIn(
            "ERROR: routing.overlay_rules[0].add: unknown route 'missing_route'",
            errors,
        )

    def test_unknown_authority_fact_outcome_reference_fails(self):
        with temporary_repository() as root:
            policy_path = root / ".claude/policy.yaml"
            policy = yaml.safe_load(policy_path.read_text())
            policy["authority"]["fact_outcomes"] = {
                "missing_fact": "human_required"
            }
            policy_path.write_text(yaml.safe_dump(policy, sort_keys=False))

            errors = self.engine.validate_bundle(root, None)

        self.assertIn(
            "ERROR: policy.authority.fact_outcomes: unknown fact 'missing_fact'",
            errors,
        )

    def test_duplicate_route_reference_fails(self):
        with temporary_repository() as root:
            routing_path = root / ".claude/routing.yaml"
            routing = yaml.safe_load(routing_path.read_text())
            routing["routes"]["security_sensitive"]["rules"] = [
                "rules/security.md",
                "rules/security.md",
            ]
            routing_path.write_text(yaml.safe_dump(routing, sort_keys=False))

            errors = self.engine.validate_bundle(root, None)

        self.assertTrue(any("non-unique elements" in error for error in errors), errors)

    def test_existing_markdown_namespace_requires_referenced_files(self):
        with temporary_repository() as root:
            rules_directory = root / ".claude/rules"
            for path in rules_directory.iterdir():
                path.unlink()

            errors = self.engine.validate_bundle(root, None)

        self.assertIn(
            "ERROR: routing markdown path does not exist: .claude/rules/engineering.md",
            errors,
        )

    def test_bootstrapping_allows_not_yet_created_markdown_namespaces(self):
        with temporary_repository() as root:
            project_path = root / ".claude/project.yaml"
            project = yaml.safe_load(project_path.read_text())
            project["instruction_system"]["module_state"] = "bootstrapping"
            project_path.write_text(yaml.safe_dump(project, sort_keys=False))
            rules_directory = root / ".claude/rules"
            for path in rules_directory.iterdir():
                path.unlink()
            rules_directory.rmdir()

            errors = self.engine.validate_bundle(root, None)

        self.assertEqual(errors, [])

    def test_complete_module_state_requires_all_markdown_references(self):
        with temporary_repository() as root:
            (root / ".claude/rules/engineering.md").unlink()
            (root / ".claude/workflows/maintenance.md").unlink()
            project_path = root / ".claude/project.yaml"
            project = yaml.safe_load(project_path.read_text())
            project.setdefault("instruction_system", {})["module_state"] = "complete"
            project_path.write_text(yaml.safe_dump(project, sort_keys=False))

            errors = self.engine.validate_bundle(root, None)

        self.assertIn(
            "ERROR: routing markdown path does not exist: .claude/rules/engineering.md",
            errors,
        )
        self.assertIn(
            "ERROR: routing markdown path does not exist: .claude/workflows/maintenance.md",
            errors,
        )

    def test_lifecycle_path_requires_declared_transition(self):
        with temporary_repository() as root:
            lifecycle_path = root / ".claude/lifecycle.yaml"
            lifecycle = yaml.safe_load(lifecycle_path.read_text())
            lifecycle["transitions"] = [
                transition
                for transition in lifecycle["transitions"]
                if not (
                    transition["from"] == "CLASSIFIED"
                    and transition["to"] == "VALIDATING"
                )
            ]
            lifecycle_path.write_text(yaml.safe_dump(lifecycle, sort_keys=False))

            errors = self.engine.validate_bundle(root, None)

        self.assertIn(
            "ERROR: lifecycle.paths.maintenance: transition CLASSIFIED -> VALIDATING is not declared",
            errors,
        )

    def test_reachable_normal_state_must_have_completion_path(self):
        with temporary_repository() as root:
            lifecycle_path = root / ".claude/lifecycle.yaml"
            lifecycle = yaml.safe_load(lifecycle_path.read_text())
            lifecycle["exceptional_states"].remove("INCIDENT")
            lifecycle["normal_states"].append("INCIDENT")
            lifecycle["transitions"].append(
                {
                    "from": "UNCLASSIFIED",
                    "to": "INCIDENT",
                    "requires": ["incident_detected"],
                }
            )
            lifecycle_path.write_text(yaml.safe_dump(lifecycle, sort_keys=False))

            errors = self.engine.validate_bundle(root, None)

        self.assertIn(
            "ERROR: lifecycle.normal_states: state INCIDENT cannot reach COMPLETE",
            errors,
        )

    def test_workflow_vocabulary_must_match_context_schema(self):
        with temporary_repository() as root:
            routing_path = root / ".claude/routing.yaml"
            routing = yaml.safe_load(routing_path.read_text())
            routing["workflow_rules"]["experimental"] = "workflows/maintenance.md"
            routing_path.write_text(yaml.safe_dump(routing, sort_keys=False))

            errors = self.engine.validate_bundle(root, None)

        self.assertIn(
            "ERROR: vocabulary.workflow_family: configured-only values: experimental",
            errors,
        )

    def test_action_vocabulary_must_match_context_schema(self):
        with temporary_repository() as root:
            policy_path = root / ".claude/policy.yaml"
            policy = yaml.safe_load(policy_path.read_text())
            del policy["authority"]["actions"]["risk_exception"]
            policy_path.write_text(yaml.safe_dump(policy, sort_keys=False))

            errors = self.engine.validate_bundle(root, None)

        self.assertIn(
            "ERROR: vocabulary.action: schema-only values: risk_exception",
            errors,
        )

    def test_context_is_schema_validated(self):
        with temporary_repository() as root:
            context_path = root / "context.yaml"
            context_path.write_text("schema_version: 1\nunexpected: true\n")

            errors = self.engine.validate_bundle(root, context_path)

        self.assertTrue(any("context" in error and "unexpected" in error for error in errors))

    def test_valid_cli_emits_one_json_object(self):
        result = subprocess.run(
            [sys.executable, str(ENGINE_PATH), "validate", "--root", str(ROOT)],
            check=False,
            capture_output=True,
            text=True,
        )

        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["errors"], [])
        self.assertEqual(result.stdout.count("\n"), 1)

    def test_invalid_cli_input_emits_json_without_traceback(self):
        result = subprocess.run(
            [
                sys.executable,
                str(ENGINE_PATH),
                "validate",
                "--root",
                str(ROOT / "does-not-exist"),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(payload["valid"])
        self.assertTrue(all(error.startswith("ERROR:") for error in payload["errors"]))
        self.assertNotIn("Traceback", result.stdout + result.stderr)
        self.assertEqual(result.stdout.count("\n"), 1)

    def test_malformed_yaml_cli_emits_json_without_traceback(self):
        with temporary_repository() as root:
            (root / ".claude/project.yaml").write_text("project: [\n")
            result = subprocess.run(
                [sys.executable, str(ENGINE_PATH), "validate", "--root", str(root)],
                check=False,
                capture_output=True,
                text=True,
            )

        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(payload["valid"])
        self.assertIn("ERROR: project: invalid YAML", payload["errors"][0])
        self.assertNotIn("Traceback", result.stdout + result.stderr)
        self.assertEqual(result.stdout.count("\n"), 1)

    def test_broken_local_schema_ref_cli_fails_as_one_json_object(self):
        with temporary_repository() as root:
            schema_path = root / ".claude/schemas/project.schema.json"
            schema = json.loads(schema_path.read_text())
            schema["properties"]["schema_version"] = {"$ref": "#/$defs/missing"}
            schema_path.write_text(json.dumps(schema))
            result = subprocess.run(
                [sys.executable, str(ENGINE_PATH), "validate", "--root", str(root)],
                check=False,
                capture_output=True,
                text=True,
            )

        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(payload["valid"])
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.stdout.count("\n"), 1)
        self.assertIn(
            "ERROR: project schema: unresolved local reference #/$defs/missing "
            "at #/properties/schema_version/$ref",
            payload["errors"],
        )
        self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_dormant_context_ref_is_preflighted_without_context(self):
        with temporary_repository() as root:
            schema_path = root / ".claude/schemas/context.schema.json"
            schema = json.loads(schema_path.read_text())
            schema["$defs"]["dormant"] = {"$ref": "#/$defs/missing"}
            schema_path.write_text(json.dumps(schema))

            errors = self.engine.validate_bundle(root, None)

        self.assertIn(
            "ERROR: context schema: unresolved local reference #/$defs/missing "
            "at #/$defs/dormant/$ref",
            errors,
        )

    def test_local_pointer_escaping_is_supported(self):
        with temporary_repository() as root:
            schema_path = root / ".claude/schemas/context.schema.json"
            schema = json.loads(schema_path.read_text())
            schema["$defs"]["slash/key"] = {"type": "string"}
            schema["$defs"]["tilde~key"] = {"$ref": "#/$defs/slash~1key"}
            schema["$defs"]["escaped"] = {"$ref": "#/$defs/tilde~0key"}
            schema_path.write_text(json.dumps(schema))

            errors = self.engine.validate_bundle(root, None)

        self.assertEqual(errors, [])

    def test_non_local_schema_ref_fails_closed(self):
        with temporary_repository() as root:
            schema_path = root / ".claude/schemas/context.schema.json"
            schema = json.loads(schema_path.read_text())
            schema["$defs"]["external"] = {
                "$ref": "https://example.invalid/schema.json"
            }
            schema_path.write_text(json.dumps(schema))

            errors = self.engine.validate_bundle(root, None)

        self.assertIn(
            "ERROR: context schema: unsupported non-local reference "
            "'https://example.invalid/schema.json' at #/$defs/external/$ref",
            errors,
        )

    def test_self_referential_schema_cli_fails_without_traceback(self):
        with temporary_repository() as root:
            schema_path = root / ".claude/schemas/project.schema.json"
            schema = json.loads(schema_path.read_text())
            schema["properties"]["schema_version"] = {
                "$ref": "#/properties/schema_version"
            }
            schema_path.write_text(json.dumps(schema))
            result = subprocess.run(
                [sys.executable, str(ENGINE_PATH), "validate", "--root", str(root)],
                check=False,
                capture_output=True,
                text=True,
            )

        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(payload["valid"])
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.stdout.count("\n"), 1)
        self.assertIn(
            "ERROR: project schema: reference cycle detected: "
            "#/properties/schema_version -> #/properties/schema_version",
            payload["errors"],
        )
        self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_nested_indirect_reference_cycle_is_rejected(self):
        with temporary_repository() as root:
            schema_path = root / ".claude/schemas/project.schema.json"
            schema = json.loads(schema_path.read_text())
            schema["$defs"] = {
                "a": {"$ref": "#/$defs/b"},
                "b": {"anyOf": [{"$ref": "#/$defs/a"}]},
            }
            schema_path.write_text(json.dumps(schema))

            errors = self.engine.validate_bundle(root, None)

        self.assertIn(
            "ERROR: project schema: reference cycle detected: "
            "#/$defs/b -> #/$defs/a -> #/$defs/b",
            errors,
        )

    def test_excessive_schema_nesting_cli_fails_without_traceback(self):
        with temporary_repository() as root:
            schema_path = root / ".claude/schemas/project.schema.json"
            depth = 1500
            schema_path.write_text(
                '{"allOf":[' * depth + '{"type":"object"}' + "]}" * depth
            )
            result = subprocess.run(
                [sys.executable, str(ENGINE_PATH), "validate", "--root", str(root)],
                check=False,
                capture_output=True,
                text=True,
            )

        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(payload["valid"])
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.stdout.count("\n"), 1)
        self.assertIn(
            "ERROR: project schema: validation resource limit exceeded",
            payload["errors"],
        )
        self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_transition_public_command_requires_complete_inputs(self):
        result = subprocess.run(
            [sys.executable, str(ENGINE_PATH), "transition", "--root", str(ROOT)],
            check=False,
            capture_output=True,
            text=True,
        )

        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(payload["valid"])
        self.assertIn("--context, --decision, --to", payload["errors"][0])
        self.assertNotIn("Traceback", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
