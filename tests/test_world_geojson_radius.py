"""Executable MONDE Mini radius-map behavior, provenance and saved-state CLI."""
import copy
import json
import math
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
CENTER = [2.3522, 48.8566]
INPUT = {"source_id": "radius-primary", "locator": "fixture://radius",
         "captured_at": K, "valid_from": "2026-01-01T00:00:00Z"}


def world():
    model = WorldMini.read(str(BASE))
    model.append_document(to_document(WorldMini.load_document(str(POINTS)), **INPUT))
    return model


class GeoJsonRadiusTest(unittest.TestCase):
    def test_nearby_entity_and_lineage(self):
        model = world()
        initial = model.export()
        result = model.export_geojson_radius(CENTER, 1, AT, K)
        self.assertEqual(result["type"], "FeatureCollection")
        self.assertEqual(result["monde_radius_query"]["basis"],
                         "SOURCE_REPORTED_POINT_RADIUS_ONLY")
        self.assertEqual(result["monde_radius_query"]["radius_km"], 1)
        self.assertEqual(result["monde_radius_query"]["total_matching_entities"], 1)
        self.assertEqual(len(result["features"]), 1)
        marker = result["features"][0]
        props = marker["properties"]
        self.assertEqual(marker["id"], props["assertion_id"])
        self.assertEqual(props["source_id"], "radius-primary")
        self.assertEqual(props["entity"], "place-001")
        self.assertTrue(props["monde_within_radius"])
        self.assertEqual(props["monde_radius_entity_rank"], 1)
        self.assertAlmostEqual(props["monde_distance_km"], 0, places=8)
        self.assertEqual(props["evidence_id"], model.export()["evidence"][-2]["id"])
        self.assertEqual(props["locator"], "fixture://radius")
        self.assertEqual(props["captured_at"], K)
        self.assertEqual(props["valid_from"], INPUT["valid_from"])
        self.assertEqual(props["knowledge_cutoff"], K)
        self.assertEqual(model.export(), initial)

    def test_competing_outside_source_is_preserved_and_not_called_nearby(self):
        model = world()
        remote = copy.deepcopy(WorldMini.load_document(str(POINTS)))
        remote["features"][0]["geometry"]["coordinates"] = [5.0, 45.0]
        model.append_document(to_document(
            remote, source_id="radius-remote", locator="fixture://remote",
            captured_at=K, valid_from=INPUT["valid_from"]))
        snapshot = model.export()
        data = model.export_geojson_radius(CENTER, 1, AT, K)
        selected = [f for f in data["features"]
                    if f["properties"]["entity"] == "place-001"]
        self.assertEqual(len(selected), 2)
        self.assertEqual(data["monde_radius_query"]["total_matching_entities"], 1)
        self.assertEqual({f["properties"]["source_id"] for f in selected},
                         {"radius-primary", "radius-remote"})
        inside = [f for f in selected if f["properties"]["monde_within_radius"]]
        outside = [f for f in selected if not f["properties"]["monde_within_radius"]]
        self.assertEqual(len(inside), 1)
        self.assertEqual(len(outside), 1)
        self.assertIsNone(outside[0]["properties"]["monde_distance_km"])
        self.assertEqual(outside[0]["geometry"]["coordinates"], [5.0, 45.0])
        self.assertEqual(inside[0]["properties"]["monde_radius_entity_rank"],
                         outside[0]["properties"]["monde_radius_entity_rank"])
        self.assertEqual(model.export(), snapshot)

    def test_zero_radius_empty_cutoff_and_invalid_input(self):
        model = world()
        self.assertEqual(model.export_geojson_radius(CENTER, 0, AT, K)
                         ["monde_radius_query"]["total_matching_entities"], 1)
        earlier = model.export_geojson_radius(CENTER, 5, AT, "2026-01-10T09:59:59Z")
        self.assertEqual(earlier["features"], [])
        self.assertEqual(earlier["monde_radius_query"]["status"], "NO_MATCHES")
        for center, radius in [([181, 0], 1), ([2], 1),
                               (CENTER, -1), (CENTER, float("nan")),
                               (CENTER, float("inf")), (CENTER, True)]:
            with self.subTest(center=center, radius=radius):
                with self.assertRaises(ValueError):
                    model.export_geojson_radius(center, radius, AT, K)

    def test_antimeridian_radius_uses_existing_spherical_search(self):
        model = WorldMini()
        geo = copy.deepcopy(WorldMini.load_document(str(POINTS)))
        geo["features"] = geo["features"][:1]
        geo["features"][0]["geometry"]["coordinates"] = [179.9, 0.0]
        model.append_document(to_document(geo, **INPUT))
        result = model.export_geojson_radius([-179.9, 0], 30, AT, K)
        self.assertEqual(len(result["features"]), 1)
        self.assertTrue(result["features"][0]["properties"]["monde_within_radius"])
        self.assertLess(result["features"][0]["properties"]["monde_distance_km"], 30)

    def test_saved_snapshot_cli_and_invalid_flag_pairs(self):
        with tempfile.TemporaryDirectory() as tmp:
            saved = Path(tmp) / "saved.json"
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            def run(*argv):
                return subprocess.run([sys.executable, "-m", "monde.world", *argv],
                                      cwd=str(ROOT), env=env, text=True,
                                      capture_output=True)
            ingest = run("--fixture", str(BASE),
                         "--ingest-geojson", str(POINTS),
                         "--source-id", INPUT["source_id"],
                         "--source-locator", INPUT["locator"],
                         "--captured-at", K, "--valid-from", INPUT["valid_from"],
                         "--state-out", str(saved))
            self.assertEqual(ingest.returncode, 0, ingest.stderr)
            query = ("--fixture", str(saved), "--export-geojson-radius",
                     "2.3522,48.8566", "--radius-km", "1",
                     "--at", AT, "--known-at", K)
            command = run(*query)
            self.assertEqual(command.returncode, 0, command.stderr)
            result = json.loads(command.stdout)
            self.assertEqual(result["features"][0]["properties"]["entity"], "place-001")
            self.assertEqual(result["monde_radius_query"]["total_matching_entities"], 1)
            invalid = [
                tuple(x for x in query if x not in ("--radius-km", "5")),
                query + ("--entity", "place-001"),
                query + ("--export-bbox", "0,0,1,1"),
                ("--fixture", str(saved), "--export-geojson-radius", "bad",
                 "--radius-km", "5", "--at", AT, "--known-at", K),
                ("--fixture", str(saved), "--search-geo-radius", "2.3522,48.8566",
                 "--at", AT, "--known-at", K),
            ]
            for args in invalid:
                with self.subTest(args=args):
                    self.assertNotEqual(run(*args).returncode, 0)
