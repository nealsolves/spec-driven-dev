import json
import unittest
from pathlib import Path

from sdd.adapters.compatibility import build_projection, check_projection, load_manifest


ROOT = Path(__file__).resolve().parents[1]


class CanonicalProjectionTest(unittest.TestCase):
    def test_repository_has_exact_45_file_projection(self):
        plan = build_projection(ROOT)
        self.assertEqual(len(plan.entries), 45)
        self.assertEqual(check_projection(ROOT, plan), ())
        self.assertEqual(load_manifest(ROOT), plan)

    def test_every_output_matches_its_canonical_source_and_executable_state(self):
        plan = build_projection(ROOT)
        for entry in plan.entries:
            source = ROOT / entry.source
            target = ROOT / entry.target
            with self.subTest(target=entry.target.as_posix()):
                self.assertEqual(target.read_bytes(), source.read_bytes())
                self.assertEqual(bool(target.stat().st_mode & 0o111), entry.executable)

    def test_migration_record_is_stable_and_machine_independent(self):
        record = json.loads(
            (ROOT / ".sdd/migrations/0001-claude-to-sdd.json").read_text("utf-8")
        )
        self.assertEqual(record["migration_id"], "0001-claude-to-sdd")
        self.assertEqual(
            record["baseline_commit"],
            "43839f372501de7453beef9e3df7f35f03f9b251",
        )
        self.assertEqual(
            record["manifest_sha256"],
            "2d4be624cc96d4852a4ba23fcf4f652cf61e1083ae97a73358d795f81e77e851",
        )
        self.assertNotIn("timestamp", record)
        self.assertNotIn(str(ROOT), json.dumps(record))
