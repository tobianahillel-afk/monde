"""Real saved WorldMini source-pair GeoJSON semantics and CLI."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from monde.source_pair_changes import (
    compare_source_pair, compare_source_pair_world_time, comparison_geojson,
    top_nearest_source_pair_changes,
)
from tests.test_world_source_pair_changes import fixture_world, AT, BEFORE, AFTER
from tests.test_world_source_pair_world_changes import sample, EARLY, LATE, KNOWN


class SourcePairGeojsonTest(unittest.TestCase):
    def test_original_knowledge_axis_reports_have_unique_export_ids(self):
        original = compare_source_pair(
            fixture_world(), "survey-a", "survey-b", AT, BEFORE, AFTER)
        before = copy.deepcopy(original)
        out = comparison_geojson(original)
        self.assertEqual(out["type"], "FeatureCollection")
        self.assertEqual(out["monde_comparison"]["comparison_axis"], "knowledge")
        self.assertEqual(out["monde_comparison"]["cutoffs"]["earlier"],
                         {"world_at": AT, "knowledge_at": BEFORE})
        features = out["features"]
        self.assertEqual(len(features), 4)
        self.assertEqual(len(set(f["id"] for f in features)), 4)
        self.assertEqual([
            (f["properties"]["monde_source_pair"]["period"],
             f["properties"]["source_id"],
             f["properties"]["monde_original_assertion_id"])
            for f in features],
            [("earlier", "survey-a", "a-a1"),
             ("earlier", "survey-b", "a-b1"),
             ("later", "survey-a", "a-a1"),
             ("later", "survey-b", "a-b2")])
        self.assertEqual([f["properties"]["evidence_id"] for f in features],
                         ["e-a1", "e-b1", "e-a1", "e-b2"])
        self.assertEqual(original, before)

    def test_unknown_is_null_never_zero_or_fabricated_point(self):
        result = compare_source_pair_world_time(
            sample(old=False), "survey-a", "survey-b", EARLY, LATE, KNOWN)
        features = comparison_geojson(result)["features"]
        self.assertEqual(len(features), 3)
        earlier = [f for f in features if
                   f["properties"]["monde_source_pair"]["period"] == "earlier"]
        self.assertEqual(len(earlier), 1)
        self.assertEqual(earlier[0]["properties"]["source_id"], "survey-a")
        meta = earlier[0]["properties"]["monde_source_pair"]
        self.assertEqual(meta["status"], "NOT_JOINTLY_REPORTED")
        self.assertIsNone(meta["separation"])
        self.assertIsNone(meta["earlier_to_later_change_km"])

    def test_world_axis_preserves_antimeridian_and_original_points(self):
        result = compare_source_pair_world_time(
            sample(dateline=True), "survey-a", "survey-b", EARLY, LATE, KNOWN)
        out = comparison_geojson(result)
        self.assertEqual(out["monde_comparison"]["comparison_axis"], "world")
        self.assertEqual(out["monde_comparison"]["cutoffs"]["earlier"],
                         {"world_at": EARLY, "knowledge_at": KNOWN})
        first = [f for f in out["features"]
                 if f["properties"]["monde_source_pair"]["period"] == "earlier"]
        self.assertIn([-179.9, 0.0],
                      [f["geometry"]["coordinates"] for f in first])
        self.assertIn([179.9, 0.0],
                      [f["geometry"]["coordinates"] for f in first])
        self.assertTrue(all(f["geometry"]["type"] == "Point" for f in out["features"]))
        self.assertLess(first[0]["properties"]["monde_source_pair"]
                        ["separation"]["nearest_km"], 25)

    def test_top_selection_preserves_complete_source_evidence(self):
        doc = compare_source_pair(
            fixture_world(), "survey-a", "survey-b", AT, BEFORE, AFTER)
        selected = top_nearest_source_pair_changes(doc, 1)
        result = comparison_geojson(selected)
        self.assertEqual(result["monde_comparison"]["selection"], selected["selection"])
        self.assertEqual(len(result["features"]), 4)
        self.assertEqual(
            {f["properties"]["entity"] for f in result["features"]}, {"site-1"})
        self.assertIsNone(comparison_geojson(doc)["monde_comparison"]["selection"])
        with self.assertRaisesRegex(ValueError, "unsupported.*schema"):
            comparison_geojson({"schema": "UNKNOWN"})

    def test_persisted_cli_both_axes_default_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            options = {"cwd": Path(__file__).resolve().parents[1],
                       "env": {**os.environ, "PYTHONPATH": "src"},
                       "capture_output": True, "text": True}
            for name, world, times in (
                ("knowledge", fixture_world(),
                 ["--at", AT, "--from-known-at", BEFORE, "--to-known-at", AFTER]),
                ("world", sample(),
                 ["--from-at", EARLY, "--to-at", LATE, "--known-at", KNOWN]),
            ):
                with self.subTest(axis=name):
                    path = Path(folder) / (name + ".json")
                    world.save(path)
                    before = path.read_bytes()
                    command = [sys.executable, "-m", "monde.source_pair_changes",
                               "--fixture", str(path),
                               "--source-a", "survey-a", "--source-b", "survey-b",
                               *times]
                    result = subprocess.run(command + ["--format", "geojson"],
                                            **options)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    geo = json.loads(result.stdout)
                    self.assertEqual(geo["type"], "FeatureCollection")
                    self.assertEqual(geo["monde_comparison"]["comparison_axis"], name)
                    self.assertEqual(len(geo["features"]), 4)
                    ranked = subprocess.run(command +
                        ["--top-nearest-changes", "1", "--format", "geojson"], **options)
                    self.assertEqual(ranked.returncode, 0, ranked.stderr)
                    self.assertEqual(json.loads(ranked.stdout)
                        ["monde_comparison"]["selection"]["selected_entities"], 1)
                    baseline = subprocess.run(command, **options)
                    self.assertEqual(baseline.returncode, 0, baseline.stderr)
                    self.assertNotIn("monde_comparison", json.loads(baseline.stdout))
                    self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
