"""Provenance-retaining bitemporal proximity discovery and real CLI tests."""
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
FIXTURE = ROOT / "examples/monde-mini.json"
POINTS = ROOT / "examples/monde-mini-points.geojson"
AT = "2026-01-02T00:00:00Z"
KNOWN = "2026-01-10T10:00:00Z"
ARGS = {"source_id": "proximity-map", "locator": "fixture://proximity-map",
        "captured_at": KNOWN, "valid_from": "2026-01-01T00:00:00Z"}


def model():
    world = WorldMini.read(str(FIXTURE))
    world.append_document(to_document(WorldMini.load_document(str(POINTS)), **ARGS))
    return world


class ProximityTests(unittest.TestCase):
    def test_nearest_results_preserve_source_lineage(self):
        world = model()
        before = world.export()
        result = world.search_geo_radius([2.3522, 48.8566], 500, AT, KNOWN)
        self.assertEqual(result["query"], "SOURCE_REPORTED_POINT_RADIUS_ONLY")
        self.assertEqual(result["distance_method"], "SPHERICAL_HAVERSINE_APPROX")
        self.assertEqual(result["status"], "MATCHES")
        self.assertEqual(result["matches"][0]["entity"], "place-001")
        first = result["matches"][0]["matched_reports"][0]
        self.assertAlmostEqual(first["distance_km"], 0, places=8)
        self.assertEqual(first["source_id"], ARGS["source_id"])
        self.assertEqual(first["locator"], ARGS["locator"])
        self.assertEqual(first["evidence_id"].startswith("geo-e-"), True)
        self.assertEqual(world.export(), before)

    def test_no_invented_absence_and_two_temporal_cutoffs(self):
        world = model()
        center = [2.3522, 48.8566]
        self.assertEqual(world.search_geo_radius(center, 1, AT, KNOWN)["status"], "MATCHES")
        self.assertEqual(world.search_geo_radius(
            center, 1, AT, "2026-01-10T09:59:59Z")["status"], "NO_MATCHES")
        self.assertEqual(world.search_geo_radius(
            center, 1, "2025-12-31T00:00:00Z", KNOWN)["status"], "NO_MATCHES")
        self.assertEqual(world.search_geo_radius([0, 0], 1, AT, KNOWN)["status"], "NO_MATCHES")

    def test_competing_source_location_remains_visible(self):
        world = model()
        data = copy.deepcopy(WorldMini.load_document(str(POINTS)))
        data["features"][0]["geometry"]["coordinates"] = [5, 45]
        world.append_document(to_document(data, source_id="another-map",
                locator="fixture://another-map", captured_at=KNOWN,
                valid_from="2026-01-01T00:00:00Z"))
        result = world.search_geo_radius([2.3522, 48.8566], 1, AT, KNOWN)
        item = next(x for x in result["matches"] if x["entity"] == "place-001")
        self.assertEqual({r["source_id"] for r in item["matched_reports"]},
                         {"proximity-map"})
        self.assertEqual({r["source_id"] for r in item["other_reports"]},
                         {"another-map"})

    def test_dateline_shortest_path_and_polar_distance(self):
        world = model()
        data = copy.deepcopy(WorldMini.load_document(str(POINTS)))
        data["features"][0]["geometry"]["coordinates"] = [179.9, 0]
        data["features"][1]["geometry"]["coordinates"] = [0, 89.9]
        world.append_document(to_document(data, source_id="edge-map",
                locator="fixture://edges", captured_at=KNOWN,
                valid_from="2026-01-01T00:00:00Z"))
        near_dateline = world.search_geo_radius([-179.9, 0], 25, AT, KNOWN)
        self.assertEqual([i["entity"] for i in near_dateline["matches"]], ["place-001"])
        near_pole = world.search_geo_radius([180, 89.9], 25, AT, KNOWN)
        self.assertEqual([i["entity"] for i in near_pole["matches"]], ["place-002"])

    def test_reject_invalid_radius_and_coordinates_without_mutation(self):
        world = model()
        before = world.export()
        for center, radius in [
            ([0, 0], -1), ([0, 0], float("nan")),
            ([0, 0], float("inf")), ([0, 0], "100"),
            ([181, 0], 1), ([0, 91], 1),
            ([True, 0], 1), ([0], 1), ([0, 0, 0], 1),
        ]:
            with self.subTest(center=center, radius=radius):
                with self.assertRaises(ValueError):
                    world.search_geo_radius(center, radius, AT, KNOWN)
        self.assertEqual(world.export(), before)

    def test_cli_import_persist_reopen_proximity(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "world.json"
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            def run(*args):
                return subprocess.run([sys.executable, "-m", "monde.world", *args],
                                      env=env, capture_output=True, text=True)
            ingest = run("--fixture", str(FIXTURE), "--ingest-geojson", str(POINTS),
                         "--source-id", ARGS["source_id"],
                         "--source-locator", ARGS["locator"],
                         "--captured-at", KNOWN, "--valid-from", ARGS["valid_from"],
                         "--state-out", str(dest))
            self.assertEqual(ingest.returncode, 0, ingest.stderr)
            query = ("--fixture", str(dest), "--search-geo-radius", "2.3522,48.8566",
                     "--radius-km", "1", "--at", AT, "--known-at", KNOWN)
            out = run(*query)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual([m["entity"] for m in json.loads(out.stdout)["matches"]],
                             ["place-001"])
            self.assertNotEqual(run(*query, "--entity", "place-001").returncode, 0)
            self.assertNotEqual(run("--fixture", str(dest), "--search-geo-radius",
                                    "2,48", "--at", AT, "--known-at", KNOWN).returncode, 0)
            self.assertNotEqual(run("--fixture", str(dest), "--search-geo-radius",
                                    "wrong", "--radius-km", "1", "--at", AT,
                                    "--known-at", KNOWN).returncode, 0)

    def test_nearest_n_preserves_source_and_order(self):
        world = model()
        one = world.search_geo_nearest([2.3522, 48.8566], 1, AT, KNOWN)
        self.assertEqual(one["query"], "SOURCE_REPORTED_NEAREST_POINTS_ONLY")
        self.assertEqual(one["total_matches"], 2)
        self.assertTrue(one["has_more"])
        self.assertEqual([m["entity"] for m in one["matches"]], ["place-001"])
        self.assertAlmostEqual(one["matches"][0]["nearest_reported_km"], 0, places=8)
        self.assertEqual(one["matches"][0]["matched_reports"][0]["source_id"], ARGS["source_id"])
        both = world.search_geo_nearest([2.3522, 48.8566], 2, AT, KNOWN)
        self.assertEqual([m["entity"] for m in both["matches"]], ["place-001", "place-002"])
        self.assertFalse(both["has_more"])

    def test_nearest_competing_sources_not_reconciled(self):
        world = model()
        data = copy.deepcopy(WorldMini.load_document(str(POINTS)))
        data["features"][0]["geometry"]["coordinates"] = [5, 45]
        world.append_document(to_document(data, source_id="different-map",
                locator="fixture://different-map", captured_at=KNOWN,
                valid_from=ARGS["valid_from"]))
        result = world.search_geo_nearest([2.3522, 48.8566], 1, AT, KNOWN)
        self.assertEqual(result["matches"][0]["entity"], "place-001")
        self.assertEqual({r["source_id"] for r in result["matches"][0]["other_reports"]},
                         {"different-map"})

    def test_nearest_temporal_and_invalid_limits(self):
        world = model()
        before = world.export()
        self.assertEqual(world.search_geo_nearest(
            [2.3522, 48.8566], 1, AT, "2026-01-10T09:59:59Z")["status"],
            "NO_MATCHES")
        for invalid in [0, -1, True, 1.2, "1", None, 1001]:
            with self.subTest(limit=invalid), self.assertRaises(ValueError):
                world.search_geo_nearest([2.3522, 48.8566], invalid, AT, KNOWN)
        with self.assertRaises(ValueError):
            world.search_geo_nearest([float("nan"), 0], 1, AT, KNOWN)
        self.assertEqual(world.export(), before)

    def test_nearest_cli_persisted_geojson(self):
        with tempfile.TemporaryDirectory() as tmp:
            saved = Path(tmp) / "saved.json"
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            def run(*args):
                return subprocess.run([sys.executable, "-m", "monde.world", *args],
                                      env=env, capture_output=True, text=True)
            ingested = run("--fixture", str(FIXTURE), "--ingest-geojson",
                           str(POINTS), "--source-id", ARGS["source_id"],
                           "--source-locator", ARGS["locator"],
                           "--captured-at", KNOWN, "--valid-from", ARGS["valid_from"],
                           "--state-out", str(saved))
            self.assertEqual(ingested.returncode, 0, ingested.stderr)
            query = ("--fixture", str(saved), "--search-geo-nearest",
                     "2.3522,48.8566", "--nearest-limit", "1",
                     "--at", AT, "--known-at", KNOWN)
            got = run(*query)
            self.assertEqual(got.returncode, 0, got.stderr)
            parsed = json.loads(got.stdout)
            self.assertEqual(parsed["total_matches"], 2)
            self.assertEqual([m["entity"] for m in parsed["matches"]], ["place-001"])
            self.assertNotEqual(run(*query, "--entity", "place-001").returncode, 0)
            self.assertNotEqual(run("--fixture", str(saved), "--search-geo-nearest",
                                    "2.3522,48.8566", "--at", AT,
                                    "--known-at", KNOWN).returncode, 0)
