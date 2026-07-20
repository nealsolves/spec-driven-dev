import json
import unittest
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / ".claude/schemas"
PAIRS = {
    "project": (".claude/project.yaml", ".claude/schemas/project.schema.json"),
    "routing": (".claude/routing.yaml", ".claude/schemas/routing.schema.json"),
    "policy": (".claude/policy.yaml", ".claude/schemas/policy.schema.json"),
    "lifecycle": (".claude/lifecycle.yaml", ".claude/schemas/policy.schema.json"),
}


def load_schema(name):
    return json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text())


def load_control_file(name):
    return yaml.safe_load((ROOT / ".claude" / f"{name}.yaml").read_text())


def representative_context():
    hashes = {
        "policy_hash": "a" * 64,
        "context_hash": "b" * 64,
        "change_hash": "c" * 64,
    }
    return {
        "schema_version": 1,
        "change_id": "maintenance-001",
        "workflow_family": "maintenance",
        "action": "local_implementation",
        "current_state": "UNCLASSIFIED",
        "change_hash": hashes["change_hash"],
        "facts": {
            "documentation_only": {
                "value": True,
                "source_type": "diff_analysis",
                "source_ref": "evidence/diff-analysis.json",
                "extractor": "repository-fact-extractor-v1",
                "confidence": 1.0,
                "observed_at_change": hashes["change_hash"],
                "corroboration": [],
            }
        },
        "clarifications": [],
        "exceptions": [],
        "authority_constraints": [],
        "evidence": {
            "evaluation_passed": {
                "satisfied": True,
                "source_ref": "evidence/evaluation.json",
                "hashes": hashes,
            }
        },
        "resources": {"repair_attempts": 0, "ci_reruns": 0},
        "open_escalation": None,
        "responses": [],
    }


class ControlPlaneContractsTest(unittest.TestCase):
    def test_required_control_files_exist(self):
        for data_path, schema_path in PAIRS.values():
            self.assertTrue((ROOT / data_path).is_file(), data_path)
            self.assertTrue((ROOT / schema_path).is_file(), schema_path)

    def test_yaml_is_schema_valid(self):
        schema_map = {
            "project": "project.schema.json",
            "routing": "routing.schema.json",
            "policy": "policy.schema.json",
        }
        for name, schema_name in schema_map.items():
            data_path, _ = PAIRS[name]
            data = yaml.safe_load((ROOT / data_path).read_text())
            schema = json.loads((SCHEMA_DIR / schema_name).read_text())
            jsonschema.Draft202012Validator(schema).validate(data)

    def test_lifecycle_validates_via_public_policy_schema_reference(self):
        policy_schema = load_schema("policy")
        validator = jsonschema.Draft202012Validator(policy_schema).evolve(
            schema={"$ref": "#/$defs/lifecycle"}
        )

        validator.validate(load_control_file("lifecycle"))

    def test_context_schema_exists(self):
        self.assertTrue((SCHEMA_DIR / "context.schema.json").is_file())

    def test_context_schema_is_valid_draft_2020_12(self):
        jsonschema.Draft202012Validator.check_schema(load_schema("context"))

    def test_representative_context_is_schema_valid(self):
        validator = jsonschema.Draft202012Validator(load_schema("context"))

        validator.validate(representative_context())

    def test_lifecycle_evidence_rejects_bare_booleans(self):
        context = representative_context()
        context["evidence"]["evaluation_passed"] = True
        validator = jsonschema.Draft202012Validator(load_schema("context"))

        with self.assertRaises(jsonschema.ValidationError):
            validator.validate(context)

    def test_lifecycle_evidence_requires_all_hashes(self):
        context = representative_context()
        del context["evidence"]["evaluation_passed"]["hashes"]["context_hash"]
        validator = jsonschema.Draft202012Validator(load_schema("context"))

        with self.assertRaises(jsonschema.ValidationError):
            validator.validate(context)

    def test_rule_lists_reject_workflow_paths(self):
        routing = load_control_file("routing")
        routing["always"]["rules"][0] = "workflows/maintenance.md"
        validator = jsonschema.Draft202012Validator(load_schema("routing"))

        with self.assertRaises(jsonschema.ValidationError):
            validator.validate(routing)

    def test_workflow_lists_reject_rule_paths(self):
        routing = load_control_file("routing")
        routing["routes"]["documentation_only"]["workflows"][0] = "rules/testing.md"
        validator = jsonschema.Draft202012Validator(load_schema("routing"))

        with self.assertRaises(jsonschema.ValidationError):
            validator.validate(routing)

    def test_unconfigured_defaults_are_safe(self):
        project = yaml.safe_load((ROOT / ".claude/project.yaml").read_text())
        self.assertEqual(project["project"]["lifecycle"], "unconfigured")
        self.assertEqual(
            project["instruction_system"]["module_state"], "complete"
        )
        self.assertFalse(project["remote_actions"]["enabled"])
        self.assertFalse(project["production_actions"]["enabled"])


if __name__ == "__main__":
    unittest.main()
