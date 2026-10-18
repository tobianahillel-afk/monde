"""Original two-source temporal CSV: real snapshots and subprocess verification."""
import csv
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from monde.source_pair_changes import (
    compare_source_pair, compare_source_pair_world_time, comparison_csv,
)
from tests.test_world_source_pair_changes import fixture_world, AT, BEFORE, AFTER
from tests.test_world_source_pair_world_changes import sample, EARLY, LATE, KNOWN


def rows(doc):
    return list(csv.DictReader(io.StringIO(comparison_csv(doc))))


class SourcePairCsvTests(unittest.TestCase):
    def test_world_cutoffs_keep_original_assertion_evidence_and_coordinates(self):
        result = rows(compare_source_pair_world_time(
            sample(), "survey-a", "survey-b", EARLY, LATE, KNOWN))
        self.assertEqual(len(result), 2)
        early, later = result
        self.assertEqual((early["comparison_axis"], early["period"],
                          early["world_at"], early["knowledge_at"]),
                         ("world", "earlier", EARLY, KNOWN))
        self.assertEqual((later["period"], later["world_at"]), ("later", LATE))
        self.assertEqual(json.loads(early["source_b_assertion_ids"]), ["a-b-old"])
        self.assertEqual(json.loads(later["source_b_evidence_ids"]), ["e-b-new"])
        self.assertEqual(json.loads(later["source_a_coordinates"]), [[0.0, 0.0]])
        self.assertEqual(json.loads(later["source_b_coordinates"]), [[1.0, 0.0]])
        self.assertEqual(early["change_nearest_km"], "")
        self.assertLess(float(later["change_nearest_km"]), -100)

    def test_knowledge_cutoffs_reuse_original_evidence(self):
        early, late = rows(compare_source_pair(
            fixture_world(), "survey-a", "survey-b", AT, BEFORE, AFTER))
        self.assertEqual(early["comparison_axis"], "knowledge")
        self.assertEqual((early["world_at"], early["knowledge_at"]), (AT, BEFORE))
        self.assertEqual((late["world_at"], late["knowledge_at"]), (AT, AFTER))
        self.assertEqual(json.loads(early["source_b_assertion_ids"]), ["a-b1"])
        self.assertEqual(json.loads(late["source_b_assertion_ids"]), ["a-b2"])
        self.assertEqual(json.loads(late["source_b_evidence_ids"]), ["e-b2"])

    def test_missing_joint_report_is_unknown_not_zero(self):
        early, later = rows(compare_source_pair_world_time(
            sample(old=False), "survey-a", "survey-b", EARLY, LATE, KNOWN))
        self.assertEqual(early["status"], "NOT_JOINTLY_REPORTED")
        self.assertEqual(early["nearest_km"], "")
        self.assertEqual(early["farthest_km"], "")
        self.assertEqual(early["change_nearest_km"], "")
        self.assertEqual(json.loads(early["source_b_assertion_ids"]), [])
        self.assertEqual(later["status"], "JOINTLY_REPORTED")
        self.assertNotEqual(later["nearest_km"], "")
        self.assertEqual(later["change_nearest_km"], "")

    def test_geographic_antimeridian_uses_existing_distance_model(self):
        old, new = rows(compare_source_pair_world_time(
            sample(dateline=True), "survey-a", "survey-b", EARLY, LATE, KNOWN))
        self.assertLess(float(old["nearest_km"]), 25)
        self.assertLess(float(new["nearest_km"]), 20)
        self.assertEqual(json.loads(old["source_a_coordinates"]), [[-179.9, 0.0]])
        self.assertEqual(json.loads(old["source_b_coordinates"]), [[179.9, 0.0]])

    def test_spreadsheet_formula_names_are_escaped_without_source_mutation(self):
        document = {
            "schema": "MONDE_SOURCE_PAIR_WORLD_CHANGE_V1",
            "source_a": "=DANGEROUS()", "source_b": "+SUM(1,1)",
            "from_at": EARLY, "to_at": LATE, "known_at": KNOWN,
            "entities": [{"entity": "@name,with comma",
                          "earlier": {"status": "NOT_JOINTLY_REPORTED",
                                      "source_a_original_reports": [],
                                      "source_b_original_reports": [],
                                      "separation": None},
                          "later": {"status": "NOT_JOINTLY_REPORTED",
                                    "source_a_original_reports": [],
                                    "source_b_original_reports": [],
                                    "separation": None},
                          "earlier_to_later_change_km": None}],
        }
        first, second = rows(document)
        for item in (first, second):
            self.assertTrue(item["entity"].startswith("'@"))
            self.assertEqual(item["source_a"], "'=DANGEROUS()")
            self.assertEqual(item["source_b"], "'+SUM(1,1)")
        self.assertEqual(document["source_a"], "=DANGEROUS()")

    def test_unsupported_schema_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported.*schema"):
            comparison_csv({"schema": "OTHER"})

    def test_real_cli_both_axes_keeps_snapshot_bytes_and_json_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "world.json"
            sample().save(path)
            original = path.read_bytes()
            base = [sys.executable, "-m", "monde.source_pair_changes",
                    "--fixture", str(path), "--source-a", "survey-a",
                    "--source-b", "survey-b"]
            settings = {"cwd": Path(__file__).resolve().parents[1],
                        "env": {**os.environ, "PYTHONPATH": "src"},
                        "capture_output": True, "text": True}
            for args, axis in [
                (["--from-at", EARLY, "--to-at", LATE, "--known-at", KNOWN], "world"),
                (["--at", LATE, "--from-known-at", EARLY,
                  "--to-known-at", KNOWN], "knowledge"),
            ]:
                with self.subTest(axis=axis):
                    csv_run = subprocess.run(base + args + ["--format", "csv"], **settings)
                    self.assertEqual(csv_run.returncode, 0, csv_run.stderr)
                    csv_rows = list(csv.DictReader(io.StringIO(csv_run.stdout)))
                    self.assertEqual([r["comparison_axis"] for r in csv_rows],
                                     [axis, axis])
                    json_run = subprocess.run(base + args, **settings)
                    self.assertEqual(json_run.returncode, 0, json_run.stderr)
                    self.assertEqual(len(json.loads(json_run.stdout)["entities"]), 1)
            bad = subprocess.run(base + ["--format", "xlsx"], **settings)
            self.assertNotEqual(bad.returncode, 0)
            self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
