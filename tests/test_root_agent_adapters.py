import json
import unittest
from pathlib import Path, PurePosixPath

from sdd.adapters.agent import (
    CONTROL_PATH,
    KERNEL_PATH,
    build_adapter_plan,
    check_agent_adapters,
    serialize_adapter_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
LEGACY_CLAUDE_SHA256 = "8f960d35d7ebf31cbd0a80c5f6cdc2a7b63c23a0c869a9e7a97fce5521c0ab70"


class RootAgentAdaptersTest(unittest.TestCase):
    def test_repository_outputs_and_manifest_match_the_adapter_plan(self):
        plan = build_adapter_plan(ROOT)

        self.assertEqual(check_agent_adapters(ROOT, plan), ())
        outputs = {item.target: item for item in plan.outputs}
        self.assertEqual(
            (ROOT / "AGENTS.md").read_bytes(),
            outputs[PurePosixPath("AGENTS.md")].payload,
        )
        self.assertEqual(
            (ROOT / "CLAUDE.md").read_bytes(),
            outputs[PurePosixPath("CLAUDE.md")].payload,
        )
        self.assertEqual(
            (ROOT / ".sdd/agent-adapters.generated.json").read_bytes(),
            serialize_adapter_manifest(plan),
        )
        self.assertLessEqual(max(item.line_count for item in plan.outputs), 180)
        self.assertLessEqual(max(item.byte_count for item in plan.outputs), 16384)

    def test_repository_migration_binds_legacy_and_generated_states(self):
        plan = build_adapter_plan(ROOT)
        migration_path = ROOT / ".sdd/migrations/0002-root-agent-adapters.json"
        self.assertTrue(migration_path.is_file(), "migration record is missing")
        raw = migration_path.read_bytes()
        record = json.loads(raw.decode("utf-8"))

        self.assertEqual(
            raw,
            (json.dumps(record, sort_keys=True, indent=2) + "\n").encode("utf-8"),
        )
        self.assertEqual(
            record,
            {
                "migration_id": "0002-root-agent-adapters",
                "new_outputs": {
                    output.target.as_posix(): output.sha256 for output in plan.outputs
                },
                "new_sources": {
                    CONTROL_PATH.as_posix(): plan.config_sha256,
                    KERNEL_PATH.as_posix(): plan.kernel_sha256,
                },
                "old_outputs": {
                    "AGENTS.md": None,
                    "CLAUDE.md": LEGACY_CLAUDE_SHA256,
                },
                "renderer": plan.renderer,
            },
        )


if __name__ == "__main__":
    unittest.main()
