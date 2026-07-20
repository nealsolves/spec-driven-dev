import json
import unittest
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
PAIRS = {
    "project": (".claude/project.yaml", ".claude/schemas/project.schema.json"),
    "routing": (".claude/routing.yaml", ".claude/schemas/routing.schema.json"),
    "policy": (".claude/policy.yaml", ".claude/schemas/policy.schema.json"),
    "lifecycle": (".claude/lifecycle.yaml", ".claude/schemas/policy.schema.json"),
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
            "lifecycle": "policy.schema.json",
        }
        for name, (data_path, _) in PAIRS.items():
            data = yaml.safe_load((ROOT / data_path).read_text())
            schema = json.loads((ROOT / ".claude/schemas" / schema_map[name]).read_text())
            if name == "lifecycle":
                schema = schema["$defs"]["lifecycle"]
            jsonschema.Draft202012Validator(schema).validate(data)

    def test_unconfigured_defaults_are_safe(self):
        project = yaml.safe_load((ROOT / ".claude/project.yaml").read_text())
        self.assertEqual(project["project"]["lifecycle"], "unconfigured")
        self.assertFalse(project["remote_actions"]["enabled"])
        self.assertFalse(project["production_actions"]["enabled"])


if __name__ == "__main__":
    unittest.main()
