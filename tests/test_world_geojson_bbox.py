"""WORK-0016: real viewport map behavior and persisted-state CLI tests."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from monde.geojson import to_document
from monde.world import WorldMini

ROOT = Path(__file__).resolve().parents[1]
AT = "2026-01-02T00:00:00Z"
K = "2026-01-10T10:00:00Z"
POINTS = ROOT / "examples/monde-mini-points.geojson"


def model():
    world = WorldMini.read(str(ROOT / "examples/monde-mini.json"))
    points = WorldMini.load_document(str(POINTS))
    world.append_document(to_document(
        points, source_id="bbox-primary", locator="fixture://primary",
        captured_at=K, valid_from="2026-01-01T00:00:00Z"))
    return world


def add_report(world, lonlat, source="bbox-other"):
    points = copy.deepcopy(WorldMini.load_document(str(POINTS)))
    points["features"] = points["features"][:1]
    points["features"][0]["geometry"]["coordinates"] = list(lonlat)
    world.append_document(to_document(
        points, source_id=source, locator="fixture://" + source,
        captured_at=K, valid_from="2026-01-01T00:00:00Z"))


class ViewportTest(unittest.TestCase):
    def test_conflicting_outside_report_keeps_source_and_evidence(self):
        world = model()
        add_report(world, [5, 45])
        original = world.export()
        data = world.export_geojson_bbox([2.34, 48.84, 2.36, 48.87], AT, K)
        self.assertEqual(data["type"], "FeatureCollection")
        self.assertEqual(data["monde_bbox_query"]["total_matching_entities"], 1)
        self.assertEqual(data["monde_bbox_query"]["total_source_features"], 2)
        self.assertEqual(len(data["features"]), 2)
        near, contrary = data["features"]
        self.assertTrue(near["properties"]["monde_inside_bbox"])
        self.assertFalse(contrary["properties"]["monde_inside_bbox"])
        self.assertEqual(contrary["geometry"]["coordinates"], [5, 45])
        self.assertEqual({f["properties"]["source_id"] for f in data["features"]},
                         {"bbox-primary", "bbox-other"})
        for feature in data["features"]:
            p = feature["properties"]
            self.assertEqual(feature["id"], p["assertion_id"])
            self.assertTrue(p["evidence_id"])
            self.assertEqual(p["knowledge_cutoff"], K)
            self.assertEqual(p["valid_at"], AT)
            self.assertIn("captured_at", p)
            self.assertIn("locator", p)
        self.assertEqual(world.export(), original)

    def test_unknown_and_nonmatching_snapshots(self):
        world = model()
        prior = world.export_geojson_bbox([2, 48, 3, 49], AT,
                                           "2026-01-10T09:59:59Z")
        self.assertEqual(prior["features"], [])
        self.assertEqual(prior["monde_bbox_query"]["status"], "NO_MATCHES")
        elsewhere = world.export_geojson_bbox([10, 48, 11, 49], AT, K)
        self.assertEqual(elsewhere["features"], [])

    def test_antimeridian_and_invalid_bbox(self):
        world = model()
        add_report(world, [-179.9, 0], source="antimeridian")
        data = world.export_geojson_bbox([179.5, -2, -179.5, 2], AT, K)
        self.assertEqual(data["monde_bbox_query"]["total_matching_entities"], 1)
        self.assertEqual(data["features"][0]["properties"]["source_id"], "antimeridian")
        for bbox in ([181, -1, 2, 1], [1, 30, 2, -30], [0, 0, 1],
                     ["0", 0, 1, 2], [float("nan"), 0, 1, 2], [True, 0, 1, 2]):
            with self.subTest(bbox=bbox), self.assertRaises(ValueError):
                world.export_geojson_bbox(bbox, AT, K)

    def test_persisted_cli_and_invalid_arguments(self):
        world = model()
        add_report(world, [5, 45])
        with tempfile.TemporaryDirectory() as directory:
            saved = Path(directory) / "saved.json"
            world.save(saved)
            original = saved.read_bytes()
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            command = (sys.executable, "-m", "monde.world", "--fixture", str(saved))
            flags = ("--export-geojson-bbox", "2.34,48.84,2.36,48.87", "--at", AT, "--known-at", K)
            proc = subprocess.run(command + flags, cwd=ROOT, env=env,
                                  text=True, capture_output=True, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            response = json.loads(proc.stdout)
            self.assertEqual(len(response["features"]), 2)
            self.assertEqual(saved.read_bytes(), original)
            bad = [
                ("--export-geojson-bbox", "2,48,3"),
                ("--export-geojson-bbox", "2,48,3,49", "--at", AT),
                flags + ("--radius-km", "1"),
                flags + ("--export-bbox", "2,48,3,49"),
            ]
            for options in bad:
                r = subprocess.run(command + options, cwd=ROOT, env=env,
                                   text=True, capture_output=True, check=False)
                self.assertNotEqual(r.returncode, 0, options)


LATE = "2026-01-11T10:00:00Z"


def correct_primary_point(world, coords):
    state = world.export()
    source_ids = {e["id"]: e["source_id"] for e in state["evidence"]}
    original = next(a for a in state["assertions"]
                    if a["attribute"] == "geo_point"
                    and source_ids[a["evidence_id"]] == "bbox-primary")
    world.add_evidence({
        "id": "bbox-late-evidence", "source_id": "bbox-primary",
        "locator": "fixture://bbox-correction", "captured_at": LATE,
        "source_event_at": None,
    })
    world.add_assertion({**original, "id": "bbox-late-assertion",
                         "value": {"type": "Point", "coordinates": list(coords)},
                         "known_at": LATE, "evidence_id": "bbox-late-evidence",
                         "supersedes": original["id"]})
    return original["id"]


class ViewportChangeTest(unittest.TestCase):
    def test_departing_correction_keeps_source_evidence_and_geometry(self):
        world = model()
        original = correct_primary_point(world, [5, 45])
        snapshot = world.export()
        result = world.export_geojson_bbox_knowledge_changes(
            [2.34, 48.84, 2.36, 48.87], AT, K, LATE)
        self.assertEqual(result["monde_bbox_changes_query"]["status"], "CHANGES")
        self.assertEqual(result["monde_bbox_changes_query"]["total_matching_entities"], 1)
        self.assertEqual({f["id"] for f in result["features"]},
                         {original, "bbox-late-assertion"})
        by_id = {f["id"]: f for f in result["features"]}
        before, after = by_id[original], by_id["bbox-late-assertion"]
        self.assertTrue(before["properties"]["monde_inside_bbox"])
        self.assertFalse(after["properties"]["monde_inside_bbox"])
        self.assertEqual(after["geometry"]["coordinates"], [5, 45])
        self.assertEqual(before["properties"]["monde_change"], "NO_LONGER_CURRENT")
        self.assertEqual(after["properties"]["monde_change"], "NEWLY_CURRENT")
        for f in result["features"]:
            self.assertTrue(f["properties"]["evidence_id"])
            self.assertTrue(f["properties"]["source_id"])
            self.assertTrue(f["properties"]["locator"])
            self.assertEqual(f["properties"]["monde_change_basis"], "KNOWLEDGE_NOT_PHYSICAL")
        self.assertEqual(world.export(), snapshot)

    def test_unchanged_and_no_matching_source_reports(self):
        world = model()
        bbox = [2.34, 48.84, 2.36, 48.87]
        arrived = world.export_geojson_bbox_knowledge_changes(
            bbox, AT, "2026-01-10T09:59:59Z", K)
        self.assertEqual(len(arrived["features"]), 1)
        unchanged = world.export_geojson_bbox_knowledge_changes(
            bbox, AT, K, LATE)
        self.assertEqual(unchanged["features"], [])
        self.assertEqual(unchanged["monde_bbox_changes_query"]["status"], "NO_CHANGES")
        distant = world.export_geojson_bbox_knowledge_changes(
            [10, 48, 11, 49], AT, K, LATE)
        self.assertEqual(distant["features"], [])

    def test_antimeridian_and_invalid_cutoffs(self):
        world = model()
        add_report(world, [-179.9, 0], source="world-antimeridian")
        delta = world.export_geojson_bbox_knowledge_changes(
            [179.8, -1, -179.8, 1], AT, "2026-01-10T09:59:59Z", K)
        self.assertGreaterEqual(delta["monde_bbox_changes_query"]["total_changed_features"], 1)
        self.assertIn("world-antimeridian",
                      {feature["properties"]["source_id"] for feature in delta["features"]})
        for bbox, earlier, later in [
            ([181, 0, -179, 2], K, LATE), ([0, 3, 1, 2], K, LATE),
            ([float("nan"), 0, 1, 2], K, LATE),
            ([2, 48, 3, 49], LATE, K), ([2, 48, 3, 49], K, K),
        ]:
            with self.subTest(bbox=bbox, earlier=earlier):
                with self.assertRaises(ValueError):
                    world.export_geojson_bbox_knowledge_changes(
                        bbox, AT, earlier, later)

    def test_saved_state_cli_history_and_validation(self):
        world = model()
        correct_primary_point(world, [5, 45])
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "world.json"
            world.save(state)
            original = state.read_bytes()
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            cmd = (sys.executable, "-m", "monde.world", "--fixture", str(state))
            flags = ("--export-geojson-bbox-changes", "2.34,48.84,2.36,48.87",
                     "--at", AT, "--compare-known-at", K, "--known-at", LATE)
            outcome = subprocess.run(cmd + flags, cwd=ROOT, env=env,
                                     text=True, capture_output=True, check=False)
            self.assertEqual(outcome.returncode, 0, outcome.stderr)
            self.assertEqual(len(json.loads(outcome.stdout)["features"]), 2)
            self.assertEqual(state.read_bytes(), original)
            for options in [
                ("--export-geojson-bbox-changes", "2,48,3", "--at", AT,
                 "--compare-known-at", K, "--known-at", LATE),
                ("--export-geojson-bbox-changes", "2,48,3,49", "--at", AT,
                 "--known-at", LATE),
                flags + ("--export-bbox", "2,48,3,49"),
                flags + ("--radius-km", "4"),
            ]:
                bad = subprocess.run(cmd + options, cwd=ROOT, env=env,
                                     text=True, capture_output=True, check=False)
                self.assertNotEqual(bad.returncode, 0, options)

TIME2 = "2026-01-04T00:00:00Z"
CUT = "2026-01-03T00:00:00Z"


def reports_at_two_times():
    world = WorldMini()
    points = WorldMini.load_document(str(POINTS))
    first = copy.deepcopy(points)
    first["features"] = first["features"][:1]
    second = copy.deepcopy(first)
    second["features"][0]["geometry"]["coordinates"] = [5, 45]
    world.append_document(to_document(
        first, source_id="viewport-first", locator="fixture://first",
        captured_at=K, valid_from="2026-01-01T00:00:00Z", valid_to=CUT))
    world.append_document(to_document(
        second, source_id="viewport-second", locator="fixture://second",
        captured_at=K, valid_from=CUT))
    return world


class ViewportWorldTimeTests(unittest.TestCase):
    def test_entering_leaving_reports_not_physical_trajectory(self):
        world = reports_at_two_times()
        snapshot = world.export()
        result = world.export_geojson_bbox_world_changes(
            [2.34, 48.84, 2.36, 48.87], AT, TIME2, K)
        self.assertEqual(result["monde_bbox_world_changes_query"]["total_matching_entities"], 1)
        self.assertEqual(len(result["features"]), 2)
        features = {f["properties"]["source_id"]: f for f in result["features"]}
        self.assertEqual(features["viewport-first"]["properties"]["monde_change"], "NO_LONGER_CURRENT")
        self.assertEqual(features["viewport-second"]["properties"]["monde_change"], "NEWLY_CURRENT")
        self.assertTrue(features["viewport-first"]["properties"]["monde_inside_bbox"])
        self.assertFalse(features["viewport-second"]["properties"]["monde_inside_bbox"])
        self.assertEqual(features["viewport-second"]["geometry"]["coordinates"], [5, 45])
        for f in features.values():
            p = f["properties"]
            self.assertEqual(p["monde_change_basis"], "REPORTED_VALIDITY_NOT_VERIFIED_MOTION")
            self.assertTrue(p["evidence_id"])
            self.assertTrue(p["locator"])
            self.assertEqual(p["knowledge_cutoff"], K)
        self.assertEqual(world.export(), snapshot)

    def test_no_changes_unknowns_antimeridian_and_validation(self):
        world = reports_at_two_times()
        bbox = [2.34, 48.84, 2.36, 48.87]
        self.assertEqual(world.export_geojson_bbox_world_changes(
            bbox, "2026-01-01T10:00:00Z", AT, K)["features"], [])
        self.assertEqual(world.export_geojson_bbox_world_changes(
            bbox, AT, TIME2, "2026-01-10T09:59:59Z")["features"], [])
        self.assertEqual(world.export_geojson_bbox_world_changes(
            [10, 48, 11, 49], AT, TIME2, K)["features"], [])
        dateline = WorldMini()
        points = WorldMini.load_document(str(POINTS))
        points["features"] = points["features"][:1]
        points["features"][0]["geometry"]["coordinates"] = [179.9, 0]
        dateline.append_document(to_document(
            points, source_id="dateline", locator="fixture://dateline",
            captured_at=K, valid_from="2026-01-01T00:00:00Z", valid_to=CUT))
        result = dateline.export_geojson_bbox_world_changes(
            [179.8, -1, -179.8, 1], AT, TIME2, K)
        self.assertEqual(len(result["features"]), 1)
        for bounds, earlier, later in [
            ([181, 0, -179, 1], AT, TIME2),
            ([0, 3, 1, 2], AT, TIME2),
            (bbox, TIME2, AT), (bbox, AT, AT),
            ([float("nan"), 48, 3, 49], AT, TIME2),
        ]:
            with self.subTest(bounds=bounds, earlier=earlier):
                with self.assertRaises(ValueError):
                    world.export_geojson_bbox_world_changes(bounds, earlier, later, K)

    def test_real_saved_state_cli(self):
        world = reports_at_two_times()
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "world.json"
            world.save(state)
            unchanged = state.read_bytes()
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            cmd = (sys.executable, "-m", "monde.world", "--fixture", str(state))
            flags = ("--export-geojson-bbox-world-changes", "2.34,48.84,2.36,48.87",
                     "--compare-at", AT, "--at", TIME2, "--known-at", K)
            ok = subprocess.run(cmd + flags, cwd=ROOT, env=env,
                                text=True, capture_output=True, check=False)
            self.assertEqual(ok.returncode, 0, ok.stderr)
            self.assertEqual(len(json.loads(ok.stdout)["features"]), 2)
            self.assertEqual(unchanged, state.read_bytes())
            for bad in [
                ("--export-geojson-bbox-world-changes", "2,48,3", "--compare-at", AT,
                 "--at", TIME2, "--known-at", K),
                ("--export-geojson-bbox-world-changes", "2,48,3,49", "--at", TIME2,
                 "--known-at", K),
                flags + ("--compare-known-at", AT),
                flags + ("--radius-km", "3"),
            ]:
                result = subprocess.run(cmd + bad, cwd=ROOT, env=env,
                                        text=True, capture_output=True, check=False)
                self.assertNotEqual(result.returncode, 0, bad)



class TileXYZTest(unittest.TestCase):
    def test_tile_reuses_bbox_and_preserves_conflicting_source_provenance(self):
        world = model()
        add_report(world, [5, 45])
        original = world.export()
        tile = world.export_geojson_tile(2, 2, 1, AT, K)
        bbox = tile["monde_tile_query"]["bbox_wgs84"]
        self.assertEqual(tile["features"], world.export_geojson_bbox(bbox, AT, K)["features"])
        self.assertEqual(tile["monde_tile_query"]["scheme"], "XYZ_WEB_MERCATOR")
        self.assertEqual((bbox[0], bbox[2]), (0.0, 90.0))
        self.assertEqual(len(tile["features"]), 2)
        self.assertEqual({f["properties"]["source_id"] for f in tile["features"]},
                         {"bbox-primary", "bbox-other"})
        self.assertTrue(all(f["properties"]["evidence_id"] for f in tile["features"]))
        self.assertEqual(world.export(), original)

    def test_zoom_zero_and_empty_tile(self):
        world = model()
        whole = world.export_geojson_tile(0, 0, 0, AT, K)
        self.assertEqual(whole["monde_tile_query"]["bbox_wgs84"][::2], [-180, 180])
        self.assertTrue(whole["features"])
        outside = world.export_geojson_tile(4, 0, 0, AT, K)
        self.assertEqual(outside["monde_tile_query"]["status"], "NO_MATCHES")
        self.assertEqual(outside["features"], [])

    def test_antimeridian_and_extreme_zoom(self):
        world = WorldMini()
        source = WorldMini.load_document(str(POINTS))
        source["features"] = source["features"][:1]
        source["features"][0]["geometry"]["coordinates"] = [179.9, 0]
        world.append_document(to_document(
            source, source_id="tile-dateline", locator="fixture://tile-dateline",
            captured_at=K, valid_from="2026-01-01T00:00:00Z"))
        west = world.export_geojson_tile(2, 0, 1, AT, K)
        east = world.export_geojson_tile(2, 3, 1, AT, K)
        self.assertEqual(west["features"], [])
        self.assertEqual(len(east["features"]), 1)
        self.assertEqual(east["features"][0]["properties"]["source_id"], "tile-dateline")
        self.assertEqual(world.export_geojson_tile(22, 0, 0, AT, K)["type"],
                         "FeatureCollection")

    def test_rejects_invalid_index_types_and_out_of_range(self):
        world = model()
        for indexes in [(-1, 0, 0), (23, 0, 0), (0, 1, 0),
                        (1, -1, 0), (1, 0, 2), (2, 4, 0),
                        (True, 0, 0), (0, 0.0, 0), (0, 0, "0")]:
            with self.subTest(indexes=indexes), self.assertRaises(ValueError):
                world.export_geojson_tile(*indexes, AT, K)

    def test_saved_state_cli_and_incompatible_flags(self):
        world = model()
        add_report(world, [5, 45])
        with tempfile.TemporaryDirectory() as directory:
            saved = Path(directory) / "world.json"
            world.save(saved)
            unchanged = saved.read_bytes()
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            command = (sys.executable, "-m", "monde.world", "--fixture", str(saved))
            flags = ("--export-geojson-tile", "2,2,1", "--at", AT, "--known-at", K)
            ok = subprocess.run(command + flags, cwd=ROOT, env=env,
                                text=True, capture_output=True, check=False)
            self.assertEqual(ok.returncode, 0, ok.stderr)
            result = json.loads(ok.stdout)
            self.assertEqual(result["monde_tile_query"]["x"], 2)
            self.assertEqual(len(result["features"]), 2)
            self.assertEqual(saved.read_bytes(), unchanged)
            for invalid in [
                ("--export-geojson-tile", "2,4,1", "--at", AT, "--known-at", K),
                ("--export-geojson-tile", "2,2", "--at", AT, "--known-at", K),
                ("--export-geojson-tile", "2,2,1.5", "--at", AT, "--known-at", K),
                ("--export-geojson-tile", "2,2,1", "--at", AT),
                flags + ("--compare-known-at", K),
            ]:
                failure = subprocess.run(command + invalid, cwd=ROOT, env=env,
                                         text=True, capture_output=True, check=False)
                self.assertNotEqual(failure.returncode, 0, invalid)


if __name__ == "__main__":
    unittest.main()
