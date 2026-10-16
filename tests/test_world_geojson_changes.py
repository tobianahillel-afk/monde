"""WorldMini map changes in knowledge, with independent evidence and real CLI."""
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
K0 = "2026-01-05T00:00:00Z"
K1 = "2026-01-10T10:00:00Z"
K2 = "2026-01-12T10:00:00Z"


def model():
    world = WorldMini()
    features = [
        {"type": "Feature", "id": entity,
         "geometry": {"type": "Point", "coordinates": point},
         "properties": {"label": entity}}
        for entity, point in (("site-a", [2.35, 48.85]),
                              ("site-b", [7.2, 47.5]))
    ]
    world.append_document(to_document(
        {"type": "FeatureCollection", "features": features},
        source_id="survey-1", locator="fixture://survey-1",
        captured_at=K1, valid_from=VALID))
    return world


def correct(world):
    old = world.query("site-a", "geo_point", AT, K1)["reports"][0]
    world.append_document({
        "schema_version": 1,
        "evidence": [{
            "id": "correct-e", "source_id": "survey-1",
            "locator": "fixture://survey-1-correction",
            "captured_at": K2, "source_event_at": None
        }],
        "assertions": [{
            "id": "correct-a", "entity": "site-a", "attribute": "geo_point",
            "value": {"type": "Point", "coordinates": [3.25, 49.1]},
            "evidence_id": "correct-e", "kind": "CLAIM",
            "known_at": K2, "valid_from": VALID, "valid_to": None,
            "supersedes": old["assertion_id"]
        }]
    })
    return old


class MapKnowledgeChangeTests(unittest.TestCase):
    def test_initial_knowledge_point_entries_not_world_creation(self):
        world = model()
        result = world.export_geojson_knowledge_changes(AT, K0, K1)
        self.assertEqual(result["type"], "FeatureCollection")
        self.assertEqual([x["properties"]["entity"] for x in result["features"]],
                         ["site-a", "site-b"])
        self.assertEqual({x["properties"]["monde_change"] for x in result["features"]},
                         {"NEWLY_CURRENT"})
        self.assertTrue(all(x["properties"]["monde_change_basis"] ==
                            "KNOWLEDGE_NOT_PHYSICAL" for x in result["features"]))
        self.assertTrue(all(x["properties"]["monde_world"] == "OBSERVED"
                            for x in result["features"]))
        self.assertEqual(world.export_geojson_knowledge_changes(AT, K1, K2)["features"], [])

    def test_correction_emits_old_and_new_geometry_with_complete_provenance(self):
        world = model()
        old = correct(world)
        original = world.export()
        features = world.export_geojson_knowledge_changes(AT, K1, K2)["features"]
        self.assertEqual(len(features), 2)
        by_state = {x["properties"]["monde_change"]: x for x in features}
        self.assertEqual(by_state["NO_LONGER_CURRENT"]["id"], old["assertion_id"])
        self.assertEqual(by_state["NO_LONGER_CURRENT"]["geometry"]["coordinates"],
                         [2.35, 48.85])
        self.assertEqual(by_state["NEWLY_CURRENT"]["id"], "correct-a")
        self.assertEqual(by_state["NEWLY_CURRENT"]["geometry"]["coordinates"],
                         [3.25, 49.1])
        self.assertEqual(by_state["NEWLY_CURRENT"]["properties"]["supersedes"],
                         old["assertion_id"])
        self.assertTrue(all(x["properties"]["source_id"] == "survey-1"
                            for x in features))
        self.assertTrue(all(x["properties"]["evidence_id"] and
                            x["properties"]["locator"].startswith("fixture://")
                            for x in features))
        self.assertTrue(all(x["properties"]["from_known_at"] == K1 and
                            x["properties"]["to_known_at"] == K2 for x in features))
        self.assertEqual(world.export(), original)

    def test_independent_competing_source_remains_unchanged(self):
        world = model()
        extra = {"type": "FeatureCollection", "features": [
            {"type": "Feature", "id": "site-a", "properties": {},
             "geometry": {"type": "Point", "coordinates": [5.0, 45.0]}}]}
        world.append_document(to_document(
            extra, source_id="survey-2", locator="fixture://survey-2",
            captured_at=K1, valid_from=VALID))
        correct(world)
        features = world.export_geojson_knowledge_changes(AT, K1, K2)["features"]
        self.assertEqual(len(features), 2)
        self.assertEqual({x["properties"]["source_id"] for x in features}, {"survey-1"})
        self.assertEqual(len(world.export_geojson(AT, K2)["features"]), 3)

    def test_viewports_select_old_and_new_points_separately(self):
        world = model()
        correct(world)
        prior = world.export_geojson_knowledge_changes(
            AT, K1, K2, [2.3, 48.8, 2.4, 48.9])["features"]
        self.assertEqual([x["properties"]["monde_change"] for x in prior],
                         ["NO_LONGER_CURRENT"])
        current = world.export_geojson_knowledge_changes(
            AT, K1, K2, [3.2, 49.0, 3.3, 49.2])["features"]
        self.assertEqual([x["properties"]["monde_change"] for x in current],
                         ["NEWLY_CURRENT"])
        self.assertEqual(world.export_geojson_knowledge_changes(
            AT, K1, K2, [0, 0, 1, 1])["features"], [])

    def test_no_future_or_invalid_world_time_and_cutoffs(self):
        world = model()
        for before, after in ((K1, K1), (K2, K1)):
            with self.subTest(before=before, after=after), self.assertRaises(ValueError):
                world.export_geojson_knowledge_changes(AT, before, after)
        with self.assertRaises(ValueError):
            world.export_geojson_knowledge_changes(AT, K0, K1, [181, 0, 190, 1])
        self.assertEqual(world.export_geojson_knowledge_changes(
            "2025-12-31T00:00:00Z", K0, K1)["features"], [])

    def test_output_is_a_copy_not_a_mutable_world_reference(self):
        world = model()
        correct(world)
        before = copy.deepcopy(world.export())
        feature = world.export_geojson_knowledge_changes(AT, K1, K2)["features"][0]
        feature["geometry"]["coordinates"][0] = 99
        feature["properties"]["source_id"] = "tampered"
        self.assertEqual(world.export(), before)

    def test_saved_snapshot_actual_python_cli_and_invalid_modes(self):
        world = model()
        correct(world)
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state.json"
            world.save(str(state))
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}

            def run(*args):
                return subprocess.run(
                    [sys.executable, "-m", "monde.world", "--fixture", str(state), *args],
                    env=env, capture_output=True, text=True)

            flags = ("--export-geojson-changes", "--at", AT,
                     "--compare-known-at", K1, "--known-at", K2)
            got = run(*flags)
            self.assertEqual(got.returncode, 0, got.stderr)
            self.assertEqual({x["properties"]["monde_change"]
                              for x in json.loads(got.stdout)["features"]},
                             {"NEWLY_CURRENT", "NO_LONGER_CURRENT"})
            viewport = run(*flags, "--export-bbox", "2.3,48.8,2.4,48.9")
            self.assertEqual(viewport.returncode, 0, viewport.stderr)
            self.assertEqual(len(json.loads(viewport.stdout)["features"]), 1)
            for invalid in (
                ("--export-geojson-changes", "--at", AT, "--known-at", K2),
                ("--export-geojson-changes", "--at", AT,
                 "--compare-known-at", K2, "--known-at", K1),
                ("--export-geojson", "--at", AT, "--known-at", K2,
                 "--compare-known-at", K1),
                ("--export-bbox", "0,0,1,1", "--at", AT, "--known-at", K2),
            ):
                self.assertNotEqual(run(*invalid).returncode, 0, invalid)


if __name__ == "__main__":
    unittest.main()
