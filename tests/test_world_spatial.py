"""Bitemporal spatial query and GeoJSON end-to-end tests."""
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
SOURCE = ROOT / "examples/monde-mini-points.geojson"
BASE = ROOT / "examples/monde-mini.json"
CAPTURED = "2026-01-10T10:00:00Z"
AT = "2026-01-02T00:00:00Z"
OPTIONS = {"source_id": "example-map", "locator": "fixture://example-map/places",
           "captured_at": CAPTURED, "valid_from": "2026-01-01T00:00:00Z"}


def model():
    world = WorldMini.read(str(BASE))
    world.append_document(to_document(WorldMini.load_document(str(SOURCE)), **OPTIONS))
    return world


class SpatialBBoxTests(unittest.TestCase):
    def test_search_keeps_evidence_and_source(self):
        result = model().search_geo_bbox([2.3, 48.8, 2.4, 48.9], AT, CAPTURED)
        self.assertEqual(result["query"], "SOURCE_REPORTED_POINT_BBOX_ONLY")
        self.assertEqual(result["status"], "MATCHES")
        self.assertEqual([x["entity"] for x in result["matches"]], ["place-001"])
        report = result["matches"][0]["matched_reports"][0]
        self.assertEqual(report["value"]["coordinates"], [2.3522, 48.8566])
        self.assertEqual(report["source_id"], "example-map")
        self.assertEqual(report["locator"], OPTIONS["locator"])

    def test_world_and_knowledge_cutoffs(self):
        world = model()
        box = [2.3, 48.8, 2.4, 48.9]
        self.assertEqual(world.search_geo_bbox(box, AT, "2026-01-10T09:59:59Z")
                         ["status"], "NO_MATCHES")
        self.assertEqual(world.search_geo_bbox(
            box, "2025-12-31T23:59:59Z", CAPTURED)["status"], "NO_MATCHES")
        self.assertEqual(world.search_geo_bbox(box, AT, CAPTURED)["status"], "MATCHES")

    def test_different_source_location_stays_visible(self):
        world = model()
        data = copy.deepcopy(WorldMini.load_document(str(SOURCE)))
        data["features"][0]["geometry"]["coordinates"] = [4.5, 45.5]
        world.append_document(to_document(
            data, source_id="other-map", locator="fixture://other-map",
            captured_at=CAPTURED, valid_from=OPTIONS["valid_from"]))
        result = world.search_geo_bbox([2.3, 48.8, 2.4, 48.9], AT, CAPTURED)
        item = next(x for x in result["matches"] if x["entity"] == "place-001")
        self.assertEqual({r["source_id"] for r in item["matched_reports"]},
                         {"example-map"})
        self.assertEqual({r["source_id"] for r in item["other_reports"]},
                         {"other-map"})

    def test_dateline_and_inclusive_boundaries(self):
        world = model()
        data = copy.deepcopy(WorldMini.load_document(str(SOURCE)))
        data["features"][0]["geometry"]["coordinates"] = [179, 11]
        data["features"][1]["geometry"]["coordinates"] = [-179, 12]
        world.append_document(to_document(
            data, source_id="dateline", locator="fixture://dateline",
            captured_at=CAPTURED, valid_from=OPTIONS["valid_from"]))
        crossing = world.search_geo_bbox([178, 10, -178, 13], AT, CAPTURED)
        self.assertEqual([x["entity"] for x in crossing["matches"]],
                         ["place-001", "place-002"])
        boundary = world.search_geo_bbox([179, 11, 179, 11], AT, CAPTURED)
        self.assertEqual([x["entity"] for x in boundary["matches"]], ["place-001"])

    def test_bad_bbox_and_geometry_fail_without_mutation(self):
        world = model()
        original = world.export()
        for box in [[], [1, 2, 3], [0, 91, 1, 92], [181, 0, 182, 1],
                    [0, 5, 2, 4], [True, 0, 1, 1], [float("nan"), 0, 1, 1],
                    ["0", 0, 1, 1], [0, float("inf"), 1, 1]]:
            with self.subTest(box=box), self.assertRaises(ValueError):
                world.search_geo_bbox(box, AT, CAPTURED)
        self.assertEqual(world.export(), original)
        document = world.export()
        point = next(a for a in document["assertions"]
                     if a["entity"] == "place-001" and a["attribute"] == "geo_point")
        point["value"] = {"type": "Polygon", "coordinates": []}
        malformed = WorldMini.from_document(document)
        with self.assertRaisesRegex(ValueError, "Point"):
            malformed.search_geo_bbox([2, 48, 3, 49], AT, CAPTURED)

    def test_subprocess_import_save_reopen_bbox(self):
        with tempfile.TemporaryDirectory() as folder:
            saved = Path(folder) / "world.json"
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            def cli(*args):
                return subprocess.run([sys.executable, "-m", "monde.world", *args],
                                      capture_output=True, text=True, env=env)
            imported = cli("--fixture", str(BASE), "--ingest-geojson", str(SOURCE),
                           "--source-id", OPTIONS["source_id"],
                           "--source-locator", OPTIONS["locator"],
                           "--captured-at", CAPTURED,
                           "--valid-from", OPTIONS["valid_from"],
                           "--state-out", str(saved))
            self.assertEqual(imported.returncode, 0, imported.stderr)
            query = ("--fixture", str(saved), "--search-geo-bbox",
                     "2.3,48.8,2.4,48.9", "--at", AT, "--known-at", CAPTURED)
            got = cli(*query)
            self.assertEqual(got.returncode, 0, got.stderr)
            self.assertEqual([x["entity"] for x in json.loads(got.stdout)["matches"]],
                             ["place-001"])
            self.assertNotEqual(cli(*query, "--entity", "place-001").returncode, 0)
            self.assertNotEqual(cli("--fixture", str(saved), "--search-geo-bbox",
                                    "bad", "--at", AT, "--known-at", CAPTURED).returncode, 0)
