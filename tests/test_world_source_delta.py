"""Portable append-only source-change reports, including real mixed-source files."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from monde.source_delta import source_delta
from monde.world import WorldMini
from monde.csv_points import documents_from_manifest
from tests.test_world_map_source_manifest_layers import sample

ROOT = Path(__file__).resolve().parents[1]


def document(evidence_id, assertion_id, *, source="survey", known="2026-01-02T12:00:00Z",
             supersedes=None, value=1):
    return {"schema_version": 1,
            "evidence": [{
                "id": evidence_id, "source_id": source,
                "locator": "dataset://" + source,
                "captured_at": known, "source_event_at": "2026-01-01T00:00:00Z",
            }],
            "assertions": [{
                "id": assertion_id, "entity": "site-a", "attribute": "status",
                "value": value, "evidence_id": evidence_id, "kind": "CLAIM",
                "known_at": known, "valid_from": "2026-01-01T00:00:00Z",
                "valid_to": None, "supersedes": supersedes,
            }]}


class SnapshotDeltaTests(unittest.TestCase):
    def test_append_only_correction_preserves_original_source_and_time(self):
        before = WorldMini.from_document(document("e1", "a1"))
        after = WorldMini.from_document(before.export())
        after.append_document(document("e2", "a2", known="2026-01-03T12:00:00Z",
                                       supersedes="a1", value=2))
        report = source_delta(before, after)
        self.assertEqual(report["added"], {
            "evidence": 1, "assertions": 1, "corrections": 1})
        self.assertEqual(report["sources"][0]["affected_entities"], ["site-a"])
        self.assertEqual(report["sources"][0]["source_id"], "survey")
        self.assertEqual(report["new_reports"][0]["supersedes"], "a1")
        self.assertEqual(report["new_reports"][0]["known_at"], "2026-01-03T12:00:00Z")
        self.assertEqual(before.export()["assertions"][0]["value"], 1)

    def test_identical_snapshots_have_no_new_reports(self):
        before = WorldMini.from_document(document("e1", "a1"))
        result = source_delta(before, WorldMini.from_document(before.export()))
        self.assertEqual(result["added"]["evidence"], 0)
        self.assertEqual(result["added"]["assertions"], 0)
        self.assertEqual(result["sources"], [])
        self.assertEqual(result["new_reports"], [])

    def test_distinct_sources_remain_distinct_without_truth_reconciliation(self):
        before = WorldMini.from_document(document("e1", "a1"))
        after = WorldMini.from_document(before.export())
        after.append_document(document("e2", "a2", source="independent",
                                       known="2026-01-04T12:00:00Z", value=9))
        out = source_delta(before, after)
        self.assertEqual([x["source_id"] for x in out["sources"]], ["independent"])
        self.assertEqual(out["new_reports"][0]["kind"], "CLAIM")
        self.assertNotIn("estimated_truth", out)

    def test_rewritten_missing_or_reordered_history_is_rejected(self):
        original = document("e1", "a1")
        before = WorldMini.from_document(original)
        later = WorldMini.from_document(before.export())
        later.append_document(document("e2", "a2", source="other",
                                       known="2026-01-04T12:00:00Z"))
        tampered = later.export()
        tampered["assertions"][0]["value"] = "forged"
        with self.assertRaisesRegex(ValueError, "diverged"):
            source_delta(before, WorldMini.from_document(tampered))
        with self.assertRaisesRegex(ValueError, "diverged"):
            source_delta(later, before)
        reordered = later.export()
        reordered["evidence"].reverse()
        with self.assertRaisesRegex(ValueError, "diverged"):
            source_delta(before, WorldMini.from_document(reordered))

    def test_cli_reads_disk_snapshots_and_reports_failure_without_overwriting(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root)
            original = WorldMini.from_document(document("e1", "a1"))
            newer = WorldMini.from_document(original.export())
            newer.append_document(document("e2", "a2", known="2026-01-04T12:00:00Z"))
            before, after = p / "before.json", p / "after.json"
            original.save(before)
            newer.save(after)
            command = [sys.executable, "-m", "monde.source_delta",
                       "--before", str(before), "--after", str(after)]
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            result = subprocess.run(command, env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["added"]["assertions"], 1)
            input_bytes = before.read_bytes(), after.read_bytes()
            failed = subprocess.run([sys.executable, "-m", "monde.source_delta",
                                     "--before", str(after), "--after", str(before)],
                                    env=env, text=True, capture_output=True)
            self.assertEqual(failed.returncode, 2)
            self.assertIn("diverged", failed.stderr)
            self.assertEqual((before.read_bytes(), after.read_bytes()), input_bytes)

    def test_real_geopackage_and_geojson_manifest_yield_per_source_delta(self):
        with tempfile.TemporaryDirectory() as root:
            manifest, _, _, _ = sample(root)
            paths, total = documents_from_manifest(manifest, output_path=Path(root) / "out.json")
            before = WorldMini()
            after = WorldMini()
            after.append_documents(paths)
            out = source_delta(before, after)
            self.assertEqual(out["added"]["evidence"], total)
            self.assertEqual(out["added"]["assertions"],
                             sum(len(doc["assertions"]) for doc in paths))
            self.assertEqual(out["added"]["corrections"], 0)
            self.assertEqual(len(out["sources"]), 4)
            self.assertEqual(sum(x["assertions_added"] for x in out["sources"]),
                             sum(len(doc["assertions"]) for doc in paths))
            self.assertEqual({x["source_id"] for x in out["sources"]},
                             {"survey:survey_points", "survey:survey_mixed",
                              "survey:survey_duplicate", "note"})


if __name__ == "__main__":
    unittest.main()
