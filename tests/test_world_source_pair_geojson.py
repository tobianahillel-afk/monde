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
    top_nearest_source_pair_changes, filter_source_pair_direction,
    source_pair_direction, comparison_html,
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


    def test_direction_semantics_and_immutable_input(self):
        rows = [{"entity": key, "earlier_to_later_change_km": delta}
                for key, delta in (
                    ("a", {"nearest_km": -1.0}), ("b", {"nearest_km": 2.0}),
                    ("c", {"nearest_km": 0.0}), ("d", None))]
        document = {"schema": "MONDE_SOURCE_PAIR_CHANGE_V1", "entities": rows}
        frozen = copy.deepcopy(document)
        for direction, target in (
            ("converging", "a"), ("diverging", "b"),
            ("unchanged", "c"), ("incomparable", "d")):
            filtered = filter_source_pair_direction(document, direction)
            self.assertEqual([x["entity"] for x in filtered["entities"]], [target])
            self.assertEqual(filtered["direction_filter"],
                             {"direction": direction, "total_entities": 4,
                              "selected_entities": 1})
        self.assertEqual(document, frozen)
        with self.assertRaises(ValueError):
            filter_source_pair_direction(document, "physical-movement")

    def test_direction_keeps_all_original_points_and_later_ranking(self):
        document = compare_source_pair(fixture_world(), "survey-a", "survey-b",
                                       AT, BEFORE, AFTER)
        frozen = copy.deepcopy(document)
        direction = source_pair_direction(document["entities"][0])
        chosen = filter_source_pair_direction(document, direction)
        self.assertGreater(len(chosen["entities"]), 0)
        geojson = comparison_geojson(chosen)
        self.assertEqual(geojson["monde_comparison"]["direction_filter"]["direction"],
                         direction)
        self.assertEqual({f["properties"]["monde_source_pair"]["direction"]
                          for f in geojson["features"]}, {direction})
        expected = [r["id"] for entity in chosen["entities"]
                    for period in ("earlier", "later")
                    for key in ("source_a_original_reports", "source_b_original_reports")
                    for r in entity[period][key]]
        actual = [f["properties"]["monde_original_assertion_id"]
                  for f in geojson["features"]]
        self.assertCountEqual(actual, expected)
        if direction != "incomparable":
            ranked = top_nearest_source_pair_changes(chosen, 1)
            self.assertEqual(ranked["selection"]["requested_top"], 1)
        self.assertEqual(document, frozen)

    def test_saved_cli_direction_in_json_csv_and_geojson_on_both_axes(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = {"cwd": Path(__file__).resolve().parents[1],
                        "env": {**os.environ, "PYTHONPATH": "src"},
                        "capture_output": True, "text": True}
            for axis, world, cutoffs in (
                ("knowledge", fixture_world(),
                 ["--at", AT, "--from-known-at", BEFORE, "--to-known-at", AFTER]),
                ("world", sample(),
                 ["--from-at", EARLY, "--to-at", LATE, "--known-at", KNOWN])):
                with self.subTest(axis=axis):
                    saved = Path(folder) / (axis + ".json")
                    world.save(saved)
                    untouched = saved.read_bytes()
                    command = [sys.executable, "-m", "monde.source_pair_changes",
                               "--fixture", str(saved), "--source-a", "survey-a",
                               "--source-b", "survey-b", *cutoffs]
                    baseline = subprocess.run(command, **settings)
                    self.assertEqual(baseline.returncode, 0, baseline.stderr)
                    entities = json.loads(baseline.stdout)["entities"]
                    direction = source_pair_direction(entities[0])
                    selected = [e for e in entities
                                if source_pair_direction(e) == direction]
                    command += ["--change-direction", direction]
                    filtered = subprocess.run(command, **settings)
                    self.assertEqual(filtered.returncode, 0, filtered.stderr)
                    self.assertEqual(
                        [e["entity"] for e in json.loads(filtered.stdout)["entities"]],
                        [e["entity"] for e in selected])
                    geo = subprocess.run(command + ["--format", "geojson"], **settings)
                    self.assertEqual(geo.returncode, 0, geo.stderr)
                    projected = json.loads(geo.stdout)
                    self.assertEqual(
                        projected["monde_comparison"]["direction_filter"]["direction"],
                        direction)
                    self.assertEqual({f["properties"]["entity"]
                                      for f in projected["features"]},
                                     {e["entity"] for e in selected})
                    csv_result = subprocess.run(command + ["--format", "csv"], **settings)
                    self.assertEqual(csv_result.returncode, 0, csv_result.stderr)
                    self.assertEqual(len(csv_result.stdout.splitlines()), 1 + 2*len(selected))
                    self.assertEqual(saved.read_bytes(), untouched)


    def test_html_reuses_offline_map_and_preserves_original_two_period_evidence(self):
        for axis, document in (
            ("knowledge", compare_source_pair(
                fixture_world(), "survey-a", "survey-b", AT, BEFORE, AFTER)),
            ("world", compare_source_pair_world_time(
                sample(), "survey-a", "survey-b", EARLY, LATE, KNOWN)),
        ):
            with self.subTest(axis=axis):
                baseline = copy.deepcopy(document)
                html = comparison_html(document)
                self.assertIn('id="comparison-period"', html)
                self.assertIn('"monde_comparison"', html)
                self.assertIn('"axis":"'+axis+'"', html)
                self.assertIn('"monde_comparison_period":"earlier"', html)
                self.assertIn('"monde_comparison_period":"later"', html)
                self.assertIn('"monde_original_assertion_id"', html)
                self.assertIn('survey-a', html)
                self.assertIn('survey-b', html)
                self.assertIn('SOURCE_REPORTED_POINT_BBOX_ONLY', html)
                self.assertIn('Content-Security-Policy', html)
                self.assertEqual(document, baseline)

    def test_html_source_bounds_wrap_antimeridian_not_whole_globe(self):
        doc = compare_source_pair_world_time(
            sample(dateline=True), "survey-a", "survey-b", EARLY, LATE, KNOWN)
        html = comparison_html(doc)
        self.assertIn('"monde_bbox_query"', html)
        # The wrapped envelope has east < west; original +/-179.9 points survive.
        import re
        match = re.search(r'"bbox":\[([-0-9.,]+)\]', html)
        self.assertIsNotNone(match)
        west, south, east, north = map(float, match.group(1).split(","))
        self.assertGreater(west, east)
        self.assertLess(north-south, 20)
        self.assertIn('-179.9', html)
        self.assertIn('179.9', html)

    def test_html_live_saved_cli_preserves_snapshot_and_escapes_untrusted_identifiers(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "world.json"
            fixture_world().save(file)
            before = file.read_bytes()
            command = [sys.executable, "-m", "monde.source_pair_changes",
                       "--fixture", str(file), "--source-a", "survey-a",
                       "--source-b", "survey-b", "--at", AT,
                       "--from-known-at", BEFORE, "--to-known-at", AFTER]
            options = {"cwd": Path(__file__).resolve().parents[1],
                       "env": {**os.environ, "PYTHONPATH": "src"},
                       "capture_output": True, "text": True}
            html = subprocess.run(command + ["--format", "html"], **options)
            self.assertEqual(html.returncode, 0, html.stderr)
            self.assertIn('"monde_comparison_period":"earlier"', html.stdout)
            self.assertIn('source-reported', html.stdout.lower())
            self.assertIn('<svg', html.stdout)
            json_default = subprocess.run(command, **options)
            self.assertEqual(json_default.returncode, 0, json_default.stderr)
            self.assertEqual(json.loads(json_default.stdout)["schema"],
                             "MONDE_SOURCE_PAIR_CHANGE_V1")
            self.assertEqual(file.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
