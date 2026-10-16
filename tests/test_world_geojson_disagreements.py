"""MONDE Mini current source Point disagreement map; API and saved-state CLI."""
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
VALID = "2026-01-01T00:00:00Z"
K1 = "2026-01-10T10:00:00Z"
K2 = "2026-01-12T10:00:00Z"

def add(world, source, coords, known=K1, entity="site-a"):
    world.append_document(to_document({
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "id": entity,
                      "geometry": {"type": "Point", "coordinates": coords},
                      "properties": {}}],
    }, source_id=source, locator="fixture://" + source,
        captured_at=known, valid_from=VALID))

def disputed():
    model = WorldMini()
    add(model, "survey-east", [2.35, 48.85])
    add(model, "survey-west", [7.2, 47.5])
    add(model, "survey-east", [1.2, 45.1], entity="site-b")
    return model

class DisagreementMapTests(unittest.TestCase):
    def test_distinct_source_reports_retained_without_consensus(self):
        model = disputed()
        state = model.export()
        collection = model.export_geojson_disagreements(AT, K1)
        self.assertEqual(collection["type"], "FeatureCollection")
        features = collection["features"]
        self.assertEqual(len(features), 2)
        self.assertEqual({f["properties"]["entity"] for f in features}, {"site-a"})
        self.assertEqual({tuple(f["geometry"]["coordinates"]) for f in features},
                         {(2.35, 48.85), (7.2, 47.5)})
        self.assertEqual({f["properties"]["source_id"] for f in features},
                         {"survey-east", "survey-west"})
        for f in features:
            p = f["properties"]
            self.assertEqual(p["monde_conflicting_source_ids"],
                             ["survey-east", "survey-west"])
            self.assertEqual(p["monde_disagreement_basis"],
                             "DISTINCT_SOURCE_REPORTS_NOT_PHYSICAL_TRUTH")
            self.assertEqual(f["id"], p["assertion_id"])
            self.assertTrue(p["evidence_id"])
            self.assertTrue(p["locator"].startswith("fixture://"))
        self.assertEqual(model.export(), state)

    def test_viewport_does_not_erase_offscreen_conflicting_source(self):
        model = disputed()
        features = model.export_geojson_disagreements(
            AT, K1, [2.3, 48.8, 2.4, 48.9])["features"]
        self.assertEqual(len(features), 1)
        self.assertEqual(features[0]["properties"]["source_id"], "survey-east")
        self.assertEqual(features[0]["properties"]["monde_conflicting_source_ids"],
                         ["survey-east", "survey-west"])
        self.assertEqual(model.export_geojson_disagreements(
            AT, K1, [0, 0, 1, 1])["features"], [])

    def test_time_cutoffs_identical_sources_and_no_known_reports(self):
        model = WorldMini()
        add(model, "one", [2.35, 48.85])
        add(model, "two", [2.35, 48.85], K2)
        self.assertEqual(model.export_geojson_disagreements(AT, K2)["features"], [])
        add(model, "three", [4.0, 48.0], K2)
        self.assertEqual(model.export_geojson_disagreements(AT, K1)["features"], [])
        self.assertEqual(len(model.export_geojson_disagreements(AT, K2)["features"]), 3)
        self.assertEqual(model.export_geojson_disagreements(
            "2025-12-31T00:00:00Z", K2)["features"], [])

    def test_antimeridian_and_output_immutability(self):
        model = WorldMini()
        add(model, "east", [179.9, 0])
        add(model, "west", [-179.9, 0])
        before = copy.deepcopy(model.export())
        got = model.export_geojson_disagreements(AT, K1,
                                                 [179, -1, -179, 1])
        self.assertEqual(len(got["features"]), 2)
        got["features"][0]["geometry"]["coordinates"][0] = 0
        got["features"][0]["properties"]["monde_conflicting_source_ids"].clear()
        self.assertEqual(model.export(), before)

    def test_real_saved_state_cli_and_invalid_modes(self):
        model = disputed()
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp) / "state.json"
            model.save(str(state))
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            def run(*flags):
                return subprocess.run(
                    [sys.executable, "-m", "monde.world", "--fixture", str(state), *flags],
                    env=env, capture_output=True, text=True)
            flags = ("--export-geojson-disagreements", "--at", AT, "--known-at", K1)
            out = run(*flags)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(len(json.loads(out.stdout)["features"]), 2)
            selected = run(*flags, "--export-bbox", "2.3,48.8,2.4,48.9")
            self.assertEqual(selected.returncode, 0, selected.stderr)
            self.assertEqual(len(json.loads(selected.stdout)["features"]), 1)
            for bad in (("--export-geojson-disagreements", "--known-at", K1),
                        (*flags, "--compare-known-at", K1),
                        (*flags, "--export-bbox", "not-a-box"),
                        ("--export-bbox", "0,0,1,1", "--at", AT, "--known-at", K1)):
                self.assertNotEqual(run(*bad).returncode, 0, bad)

if __name__ == "__main__":
    unittest.main()
