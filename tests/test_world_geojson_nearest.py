"""Nearest-entity GeoJSON retains temporal source provenance, real CLI included."""
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
BASE = ROOT / "examples/monde-mini.json"
POINTS = ROOT / "examples/monde-mini-points.geojson"
AT = "2026-01-02T00:00:00Z"
K = "2026-01-10T10:00:00Z"
ARGS = {"source_id": "nearest-primary", "locator": "fixture://nearest",
        "captured_at": K, "valid_from": "2026-01-01T00:00:00Z"}


def world():
    obj = WorldMini.read(str(BASE))
    obj.append_document(to_document(WorldMini.load_document(str(POINTS)), **ARGS))
    return obj


class NearestMapTest(unittest.TestCase):
    def test_rank_and_lineage_without_mutation(self):
        obj = world()
        original = obj.export()
        out = obj.export_geojson_nearest([2.3522, 48.8566], 1, AT, K)
        self.assertEqual(out["type"], "FeatureCollection")
        self.assertEqual(out["monde_nearest_query"]["total_matching_entities"], 2)
        self.assertTrue(out["monde_nearest_query"]["has_more"])
        self.assertEqual(len(out["features"]), 1)
        feature = out["features"][0]
        prop = feature["properties"]
        self.assertEqual(prop["entity"], "place-001")
        self.assertEqual(prop["monde_status"], "SOURCE_REPORTED_ONLY")
        self.assertEqual(prop["monde_nearest_entity_rank"], 1)
        self.assertEqual(prop["source_id"], ARGS["source_id"])
        self.assertEqual(feature["id"], prop["assertion_id"])
        self.assertTrue(prop["evidence_id"])
        self.assertAlmostEqual(prop["monde_distance_km"], 0, places=8)
        self.assertEqual(obj.export(), original)

    def test_competing_source_locations_not_silently_dropped(self):
        obj = world()
        point = copy.deepcopy(WorldMini.load_document(str(POINTS)))
        point["features"][0]["geometry"]["coordinates"] = [5, 45]
        obj.append_document(to_document(point, source_id="other",
            locator="fixture://other", captured_at=K, valid_from=ARGS["valid_from"]))
        before = obj.export()
        result = obj.export_geojson_nearest([2.3522, 48.8566], 1, AT, K)
        features = result["features"]
        self.assertEqual(len(features), 2)
        self.assertEqual({f["properties"]["source_id"] for f in features},
                         {"nearest-primary", "other"})
        self.assertEqual({f["properties"]["monde_nearest_entity_rank"] for f in features}, {1})
        self.assertGreater(features[1]["properties"]["monde_distance_km"], 100)
        self.assertEqual(obj.export(), before)

    def test_before_first_knowledge_and_invalid_values(self):
        obj = world()
        empty = obj.export_geojson_nearest(
            [2.3522, 48.8566], 1, AT, "2026-01-10T09:59:59Z")
        self.assertEqual(empty["features"], [])
        self.assertEqual(empty["monde_nearest_query"]["status"], "NO_MATCHES")
        saved = obj.export()
        for center, limit in [([181, 0], 1), ([0], 1), ([0, 0], 0),
                              ([0, 0], True), ([0, 0], 1001)]:
            with self.subTest(center=center, limit=limit):
                with self.assertRaises(ValueError):
                    obj.export_geojson_nearest(center, limit, AT, K)
        self.assertEqual(obj.export(), saved)

    def test_cli_saved_state_and_invalid_options(self):
        with tempfile.TemporaryDirectory() as tmp:
            saved = Path(tmp) / "saved.json"
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            def run(*args):
                return subprocess.run([sys.executable, "-m", "monde.world", *args],
                                      cwd=str(ROOT), env=env, text=True, capture_output=True)
            ingested = run("--fixture", str(BASE), "--ingest-geojson", str(POINTS),
                           "--source-id", ARGS["source_id"],
                           "--source-locator", ARGS["locator"], "--captured-at", K,
                           "--valid-from", ARGS["valid_from"], "--state-out", str(saved))
            self.assertEqual(ingested.returncode, 0, ingested.stderr)
            query = ("--fixture", str(saved), "--export-geojson-nearest",
                     "2.3522,48.8566", "--nearest-limit", "1",
                     "--at", AT, "--known-at", K)
            out = run(*query)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(json.loads(out.stdout)["features"][0]["properties"]["entity"],
                             "place-001")
            for args in [query + ("--entity", "place-001"),
                         query + ("--export-bbox", "0,0,1,1"),
                         tuple(x for x in query if x not in ("--nearest-limit", "1")),
                         ("--fixture", str(saved), "--export-geojson-nearest", "wrong",
                          "--nearest-limit", "1", "--at", AT, "--known-at", K)]:
                self.assertNotEqual(run(*args).returncode, 0)
