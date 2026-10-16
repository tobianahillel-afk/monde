"""Bitemporal, source-faithful GeoJSON export, viewport, and real CLI."""
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
KNOWN = "2026-01-10T10:00:00Z"
SOURCE = {"source_id": "map-primary", "locator": "fixture://map-primary",
          "captured_at": KNOWN, "valid_from": "2026-01-01T00:00:00Z"}


def model():
    world = WorldMini.read(str(BASE))
    world.append_document(to_document(WorldMini.load_document(str(POINTS)), **SOURCE))
    return world


class GeoJsonExportTests(unittest.TestCase):
    def test_valid_feature_collection_preserves_lineage(self):
        world = model()
        before = world.export()
        result = world.export_geojson(AT, KNOWN)
        self.assertEqual(set(result), {"type", "features"})
        self.assertEqual(result["type"], "FeatureCollection")
        self.assertEqual([x["properties"]["entity"] for x in result["features"]],
                         ["place-001", "place-002"])
        first = result["features"][0]
        self.assertEqual(first["geometry"], {
            "type": "Point", "coordinates": [2.3522, 48.8566]})
        self.assertEqual(first["properties"]["source_id"], SOURCE["source_id"])
        self.assertEqual(first["properties"]["locator"], SOURCE["locator"])
        self.assertEqual(first["properties"]["monde_world"], "OBSERVED")
        self.assertEqual(first["properties"]["monde_status"], "SOURCE_REPORTED_ONLY")
        self.assertEqual(first["properties"]["knowledge_cutoff"], KNOWN)
        self.assertEqual(first["id"], first["properties"]["assertion_id"])
        self.assertIn("evidence_id", first["properties"])
        self.assertEqual(world.export(), before)

    def test_two_disagreeing_locations_are_two_features_not_a_consensus(self):
        world = model()
        other = copy.deepcopy(WorldMini.load_document(str(POINTS)))
        other["features"][0]["geometry"]["coordinates"] = [7.1, 47.2]
        world.append_document(to_document(
            other, source_id="map-secondary", locator="fixture://map-secondary",
            captured_at=KNOWN, valid_from=SOURCE["valid_from"]))
        features = [f for f in world.export_geojson(AT, KNOWN)["features"]
                    if f["properties"]["entity"] == "place-001"]
        self.assertEqual(len(features), 2)
        self.assertEqual({f["properties"]["source_id"] for f in features},
                         {"map-primary", "map-secondary"})
        self.assertEqual({tuple(f["geometry"]["coordinates"]) for f in features},
                         {(2.3522, 48.8566), (7.1, 47.2)})
        viewport = world.export_geojson(AT, KNOWN, [2.35, 48.85, 2.36, 48.86])["features"]
        self.assertEqual(len(viewport), 1)
        self.assertEqual(viewport[0]["properties"]["source_id"], "map-primary")

    def test_no_future_world_or_knowledge_evidence_leaks(self):
        world = model()
        self.assertEqual(world.export_geojson(AT, "2026-01-10T09:59:59Z")["features"], [])
        self.assertEqual(world.export_geojson("2025-12-31T00:00:00Z", KNOWN)["features"], [])
        self.assertEqual(len(world.export_geojson(AT, KNOWN)["features"]), 2)

    def test_antimeridian_viewport_and_invalid_inputs(self):
        world = model()
        crossing = copy.deepcopy(WorldMini.load_document(str(POINTS)))
        crossing["features"][0]["geometry"]["coordinates"] = [179.9, 0]
        world.append_document(to_document(
            crossing, source_id="dateline", locator="fixture://dateline",
            captured_at=KNOWN, valid_from=SOURCE["valid_from"]))
        visible = world.export_geojson(AT, KNOWN, [179, -1, -179, 1])["features"]
        self.assertEqual(len(visible), 1)
        self.assertEqual(visible[0]["properties"]["source_id"], "dateline")
        for bounds in ([181, -90, 180, 90], [0, 91, 1, 92],
                       [False, 0, 1, 1], [0, 0, 1], ["west", 0, 1, 1]):
            with self.subTest(bounds=bounds), self.assertRaises(ValueError):
                world.export_geojson(AT, KNOWN, bounds)

    def test_mutating_map_output_does_not_change_evidence(self):
        world = model()
        original = world.export()
        result = world.export_geojson(AT, KNOWN)
        result["features"][0]["geometry"]["coordinates"][0] = 99
        result["features"][0]["properties"]["source_id"] = "corrupted"
        self.assertEqual(world.export(), original)

    def test_cli_save_reopen_export_and_invalid_mode(self):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp) / "saved.json"
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}

            def run(*flags):
                return subprocess.run([sys.executable, "-m", "monde.world", *flags],
                                      env=env, capture_output=True, text=True)

            imported = run("--fixture", str(BASE), "--ingest-geojson", str(POINTS),
                           "--source-id", SOURCE["source_id"],
                           "--source-locator", SOURCE["locator"],
                           "--captured-at", KNOWN, "--valid-from", SOURCE["valid_from"],
                           "--state-out", str(state))
            self.assertEqual(imported.returncode, 0, imported.stderr)
            out = run("--fixture", str(state), "--export-geojson",
                      "--at", AT, "--known-at", KNOWN, "--export-bbox", "2.35,48.85,2.36,48.86")
            self.assertEqual(out.returncode, 0, out.stderr)
            payload = json.loads(out.stdout)
            self.assertEqual(payload["type"], "FeatureCollection")
            self.assertEqual([f["properties"]["entity"] for f in payload["features"]],
                             ["place-001"])
            self.assertEqual(json.loads(run("--fixture", str(state),
                                            "--export-geojson", "--at", AT,
                                            "--known-at", KNOWN).stdout)["type"],
                             "FeatureCollection")
            self.assertNotEqual(run("--fixture", str(state), "--export-geojson",
                                    "--export-bbox", "invalid", "--at", AT,
                                    "--known-at", KNOWN).returncode, 0)
            self.assertNotEqual(run("--fixture", str(state), "--attribute", "geo_point",
                                    "--entity", "place-001", "--at", AT,
                                    "--known-at", KNOWN, "--export-bbox",
                                    "0,0,1,1").returncode, 0)
