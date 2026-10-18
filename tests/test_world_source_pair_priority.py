"""Prioritize time-changing original source differences, not inferred movement."""
import copy
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
    compare_source_pair, comparison_csv, top_nearest_source_pair_changes,
)
from tests.test_world_source_pair_changes import fixture_world, AT, BEFORE, AFTER
from tests.test_world_source_pair_world_changes import sample, EARLY, LATE, KNOWN


class TemporalPriorityTest(unittest.TestCase):
    def test_absolute_nearest_change_sort_and_tie_break(self):
        doc = {"entities": [
            {"entity": "z", "earlier_to_later_change_km": {"nearest_km": -12.0}},
            {"entity": "unknown", "earlier_to_later_change_km": None},
            {"entity": "b", "earlier_to_later_change_km": {"nearest_km": 5.0}},
            {"entity": "a", "earlier_to_later_change_km": {"nearest_km": 12.0}},
        ]}
        original = copy.deepcopy(doc)
        selected = top_nearest_source_pair_changes(doc, 2)
        self.assertEqual([r["entity"] for r in selected["entities"]], ["a", "z"])
        self.assertEqual(selected["selection"]["eligible_entities"], 3)
        self.assertEqual(selected["selection"]["omitted_not_jointly_reported"], 1)
        self.assertEqual(selected["selection"]["selected_entities"], 2)
        self.assertEqual(doc, original)

    def test_noncomparability_is_never_zero(self):
        doc = {"entities": [
            {"entity": "missing", "earlier_to_later_change_km": None},
            {"entity": "unchanged", "earlier_to_later_change_km": {"nearest_km": 0}},
        ]}
        out = top_nearest_source_pair_changes(doc, 10)
        self.assertEqual([x["entity"] for x in out["entities"]], ["unchanged"])
        self.assertEqual(top_nearest_source_pair_changes(
            {"entities": [doc["entities"][0]]}, 1)["entities"], [])

    def test_invalid_top_n_and_invalid_numeric_change(self):
        for limit in (0, -1, 1.5, True, "2"):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                top_nearest_source_pair_changes({"entities": []}, limit)
        for value in (float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=str(value)), self.assertRaises(ValueError):
                top_nearest_source_pair_changes({"entities": [{
                    "entity": "x",
                    "earlier_to_later_change_km": {"nearest_km": value}}]}, 1)

    def test_original_reports_and_csv_survive_selection(self):
        document = compare_source_pair(
            fixture_world(), "survey-a", "survey-b", AT, BEFORE, AFTER)
        filtered = top_nearest_source_pair_changes(document, 1)
        self.assertEqual(filtered["entities"][0], document["entities"][0])
        rows = list(csv.DictReader(io.StringIO(comparison_csv(filtered))))
        self.assertEqual(len(rows), 2)
        self.assertEqual(json.loads(rows[0]["source_b_assertion_ids"]), ["a-b1"])
        self.assertEqual(json.loads(rows[1]["source_b_evidence_ids"]), ["e-b2"])

    def test_real_cli_both_temporal_axes_json_csv_unchanged_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            examples = [
                ("knowledge", fixture_world(),
                 ["--at", AT, "--from-known-at", BEFORE, "--to-known-at", AFTER]),
                ("world", sample(),
                 ["--from-at", EARLY, "--to-at", LATE, "--known-at", KNOWN]),
            ]
            for axis, world, cutoffs in examples:
                with self.subTest(axis=axis):
                    path = Path(tmp) / (axis + ".json")
                    world.save(path)
                    original = path.read_bytes()
                    cmd = [sys.executable, "-m", "monde.source_pair_changes",
                           "--fixture", str(path), "--source-a", "survey-a",
                           "--source-b", "survey-b", *cutoffs]
                    opts = {"cwd": Path(__file__).resolve().parents[1],
                            "env": {**os.environ, "PYTHONPATH": "src"},
                            "capture_output": True, "text": True}
                    baseline = subprocess.run(cmd, **opts)
                    self.assertEqual(baseline.returncode, 0, baseline.stderr)
                    default = json.loads(baseline.stdout)
                    self.assertNotIn("selection", default)
                    ranked = subprocess.run(
                        cmd + ["--top-nearest-changes", "1"], **opts)
                    self.assertEqual(ranked.returncode, 0, ranked.stderr)
                    selection = json.loads(ranked.stdout)
                    self.assertEqual(selection["schema"], default["schema"])
                    self.assertEqual(selection["entities"], default["entities"][:1])
                    self.assertEqual(selection["selection"]["requested_top"], 1)
                    csv_run = subprocess.run(
                        cmd + ["--top-nearest-changes", "1", "--format", "csv"],
                        **opts)
                    self.assertEqual(csv_run.returncode, 0, csv_run.stderr)
                    rows = list(csv.DictReader(io.StringIO(csv_run.stdout)))
                    self.assertEqual([r["period"] for r in rows], ["earlier", "later"])
                    for invalid in ("0", "-5", "2.4", "nan"):
                        bad = subprocess.run(
                            cmd + ["--top-nearest-changes", invalid], **opts)
                        self.assertNotEqual(bad.returncode, 0)
                    self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
