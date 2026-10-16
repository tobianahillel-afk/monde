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

if __name__ == "__main__":
    unittest.main()
